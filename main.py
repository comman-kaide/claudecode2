"""
FastAPI メインアプリケーション
"""

import json
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Response
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


# ===== Slack Webhook =====

@app.post("/slack/events")
async def slack_events(request: Request):
    """Slackイベント受信エンドポイント"""
    from app.slack_app import handler
    return await handler.handle(request)


@app.post("/slack/actions")
async def slack_actions(request: Request):
    """Slackアクション受信エンドポイント"""
    from app.slack_app import handler
    return await handler.handle(request)


# ===== Google OAuth =====

@app.get("/oauth/callback")
async def google_oauth_callback(code: str, state: str = None):
    """Google OAuth2コールバック"""
    try:
        from app.utils.google_auth import create_oauth_flow
        flow = create_oauth_flow()
        flow.fetch_token(code=code)
        creds = flow.credentials

        token_data = json.dumps({
            "token": creds.token,
            "refresh_token": creds.refresh_token,
        })

        html = f"""
        <html>
        <body style="font-family: sans-serif; max-width: 600px; margin: 50px auto; padding: 20px;">
            <h2>✅ Google認証が完了しました！</h2>
            <p>以下のJSON文字列をRenderの環境変数 <code>GOOGLE_TOKEN_JSON</code> に設定してください：</p>
            <textarea style="width:100%; height:120px; font-family:monospace; padding:10px;"
                      onclick="this.select()">{token_data}</textarea>
            <p>設定後、RenderでWebサービスを再起動してください。</p>
            <p>このページを閉じてSlackに戻ってください。</p>
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
    """ヘルスチェックエンドポイント（Render用）"""
    from app.utils.google_auth import is_google_authenticated
    return {
        "status": "healthy",
        "google_authenticated": is_google_authenticated(),
        "scheduler_running": True,
    }


@app.get("/")
async def root():
    return {"message": "Secretary AI is running 🤖", "docs": "/docs"}
