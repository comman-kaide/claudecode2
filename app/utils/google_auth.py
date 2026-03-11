import json
import os
from typing import Optional
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import Flow
from config.settings import settings

SCOPES = [
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/gmail.send",
]


def get_google_credentials() -> Optional[Credentials]:
    """環境変数からGoogle認証情報を取得・リフレッシュ"""
    token_json = settings.google_token_json
    if not token_json:
        return None

    try:
        token_data = json.loads(token_json)
        creds = Credentials(
            token=token_data.get("token"),
            refresh_token=token_data.get("refresh_token"),
            token_uri="https://oauth2.googleapis.com/token",
            client_id=settings.google_client_id,
            client_secret=settings.google_client_secret,
            scopes=SCOPES,
        )

        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
            # 更新されたトークンを保存
            updated = {
                "token": creds.token,
                "refresh_token": creds.refresh_token,
            }
            print(f"[Google Auth] Token refreshed. Update GOOGLE_TOKEN_JSON env var to: {json.dumps(updated)}")

        return creds
    except Exception as e:
        print(f"[Google Auth] Error loading credentials: {e}")
        return None


def create_oauth_flow() -> Flow:
    """OAuth2認証フローを作成（PKCEなし）"""
    client_config = {
        "web": {
            "client_id": settings.google_client_id,
            "client_secret": settings.google_client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": [settings.google_redirect_uri],
        }
    }
    flow = Flow.from_client_config(
        client_config,
        scopes=SCOPES,
        redirect_uri=settings.google_redirect_uri,
    )
    # PKCEを無効化（コード検証なしでトークン交換できるようにする）
    flow.code_verifier = None
    return flow


def get_auth_url() -> str:
    """PKCEなしのGoogle認証URLを生成"""
    import urllib.parse
    params = {
        'response_type': 'code',
        'client_id': settings.google_client_id,
        'redirect_uri': settings.google_redirect_uri,
        'scope': ' '.join(SCOPES),
        'access_type': 'offline',
        'prompt': 'consent',
        'state': 'secretary_ai_auth',
    }
    return 'https://accounts.google.com/o/oauth2/v2/auth?' + urllib.parse.urlencode(params)


def is_google_authenticated() -> bool:
    """Google認証済みかチェック"""
    creds = get_google_credentials()
    return creds is not None and creds.valid
