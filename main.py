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

@app.get("/debug/calendars")
async def debug_calendars():
    """利用可能なカレンダー一覧を取得"""
    from app.utils.google_auth import get_google_credentials
    from googleapiclient.discovery import build
    try:
        creds = get_google_credentials()
        service = build("calendar", "v3", credentials=creds)
        calendar_list = service.calendarList().list().execute()
        calendars = []
        for cal in calendar_list.get("items", []):
            calendars.append({
                "id": cal["id"],
                "summary": cal.get("summary", ""),
                "primary": cal.get("primary", False),
                "accessRole": cal.get("accessRole", ""),
            })
        return {"calendars": calendars, "count": len(calendars)}
    except Exception as e:
        import traceback
        return {"error": str(e), "traceback": traceback.format_exc()}


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

@app.get("/debug/gmail")
async def debug_gmail():
    """Gmail接続デバッグ用エンドポイント"""
    from app.utils.google_auth import get_google_credentials
    from app.tools.gmail_tools import list_emails
    import traceback

    result = {"steps": {}}

    # Step1: 認証情報取得
    try:
        creds = get_google_credentials()
        result["steps"]["get_credentials"] = "OK" if creds else "FAILED - creds is None"
        if creds:
            result["steps"]["token_valid"] = str(creds.valid)
            result["steps"]["token_expired"] = str(creds.expired)
    except Exception as e:
        result["steps"]["get_credentials"] = f"ERROR: {e}"
        result["steps"]["traceback"] = traceback.format_exc()
        return result

    # Step2: Gmail API呼び出し
    try:
        email_result = list_emails(max_results=1)
        result["steps"]["gmail_api"] = email_result
    except Exception as e:
        result["steps"]["gmail_api"] = f"ERROR: {e}"
        result["steps"]["traceback"] = traceback.format_exc()

    return result


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
