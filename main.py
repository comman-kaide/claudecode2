"""
FastAPI メインアプリケーション（Socket Mode対応）
"""

import json
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse

from config.settings import settings
from app.database import init_db
from app.scheduler import start_scheduler, stop_scheduler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """アプリ起動・終了時の処理"""
    # 起動時
    logger.info("Starting Secretary AI...")
    init_db()
    start_scheduler()

    # Socket Mode起動（xapp-トークンがあれば）
    from app.slack_app import start_socket_mode
    start_socket_mode()

    yield

    # 終了時
    stop_scheduler()
    logger.info("Secretary AI stopped.")


app = FastAPI(
    title="Secretary AI",
    description="Slack × Claude AI 秘書エージェント",
    version="1.0.0",
    lifespan=lifespan,
)


# ===== Slack Webhook（Socket ModeがOFFの場合のフォールバック）=====

@app.post("/slack/events")
async def slack_events(request: Request):
    from app.slack_app import handler
    return await handler.handle(request)


@app.post("/slack/actions")
async def slack_actions(request: Request):
    from app.slack_app import handler
    return await handler.handle(request)


# ===== Google OAuth =====

@app.get("/oauth/callback")
async def google_oauth_callback(code: str, state: str = None):
    """Google OAuth2コールバック"""
    try:
        import httpx
        from config.settings import settings as cfg

        # PKCEなしで直接トークンエンドポイントを叩く
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                "https://oauth2.googleapis.com/token",
                data={
                    "code": code,
                    "client_id": cfg.google_client_id,
                    "client_secret": cfg.google_client_secret,
                    "redirect_uri": cfg.google_redirect_uri,
                    "grant_type": "authorization_code",
                },
            )
        token_resp = resp.json()
        if "error" in token_resp:
            raise Exception(f"{token_resp['error']}: {token_resp.get('error_description', '')}")

        token_data = json.dumps({
            "token": token_resp.get("access_token"),
            "refresh_token": token_resp.get("refresh_token"),
        })

        html = f"""
        <html>
        <body style="font-family: sans-serif; max-width: 600px; margin: 50px auto; padding: 20px;">
            <h2>✅ Google認証が完了しました！</h2>
            <p>以下のJSON文字列をRenderの環境変数 <code>GOOGLE_TOKEN_JSON</code> に設定してください：</p>
            <textarea style="width:100%; height:120px; font-family:monospace; padding:10px;"
                      onclick="this.select()">{token_data}</textarea>
            <p>① 上のテキストを全選択してコピー</p>
            <p>② Render → Environment → <code>GOOGLE_TOKEN_JSON</code> に貼り付け → Save Changes</p>
            <p>③ Renderでサービスを再起動</p>
        </body>
        </html>
        """
        return HTMLResponse(content=html)
    except Exception as e:
        return HTMLResponse(
            content=f"<h2>❌ 認証エラー: {e}</h2>",
            status_code=400,
        )


# ===== ヘルスチェック =====

@app.get("/health")
async def health_check():
    from app.utils.google_auth import is_google_authenticated
    return {
        "status": "healthy",
        "google_authenticated": is_google_authenticated(),
        "scheduler_running": True,
    }


@app.get("/")
async def root():
    return {"message": "Secretary AI is running 🤖", "docs": "/docs"}
