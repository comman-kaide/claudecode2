"""
Slackアプリのイベントハンドラー（Socket Mode対応）
"""

import asyncio
import logging
import threading
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from slack_bolt.adapter.fastapi import SlackRequestHandler
from config.settings import settings
from app.agent import SecretaryAgent
from app.database import ConversationHistory, SessionLocal
from app.utils.google_auth import create_oauth_flow, is_google_authenticated

logger = logging.getLogger(__name__)

# Slackアプリの初期化（Socket Mode: signing_secret不要）
slack_app = App(token=settings.slack_bot_token)

# Webhook用ハンドラー（Socket ModeではなくHTTP Webhookの場合に使用）
handler = SlackRequestHandler(slack_app)

agent = SecretaryAgent()

# Socket Modeハンドラー（グローバル）
_socket_handler = None


def start_socket_mode():
    """Socket Modeを別スレッドで起動"""
    global _socket_handler
    if not settings.slack_app_token:
        logger.warning("SLACK_APP_TOKEN not set. Socket Mode disabled.")
        return
    try:
        _socket_handler = SocketModeHandler(slack_app, settings.slack_app_token)
        thread = threading.Thread(target=_socket_handler.start, daemon=True)
        thread.start()
        logger.info("Slack Socket Mode started.")
    except Exception as e:
        logger.error(f"Failed to start Socket Mode: {e}")


def get_slack_client():
    """Slackクライアントを返す（他モジュールから使用）"""
    return slack_app.client


def get_conversation_history(slack_user_id: str, thread_ts: str = None, limit: int = 10) -> list:
    """会話履歴をDBから取得"""
    db = SessionLocal()
    try:
        query = db.query(ConversationHistory).filter(
            ConversationHistory.slack_user_id == slack_user_id
        )
        if thread_ts:
            query = query.filter(ConversationHistory.slack_thread_ts == thread_ts)

        records = query.order_by(ConversationHistory.created_at.desc()).limit(limit).all()
        records.reverse()

        history = []
        for r in records:
            history.append({"role": r.role, "content": r.content})
        return history
    finally:
        db.close()


def save_conversation(slack_user_id: str, thread_ts: str, role: str, content: str):
    """会話をDBに保存"""
    db = SessionLocal()
    try:
        record = ConversationHistory(
            slack_user_id=slack_user_id,
            slack_thread_ts=thread_ts,
            role=role,
            content=content,
        )
        db.add(record)
        db.commit()
    finally:
        db.close()


# ===== Slackイベントハンドラー =====

@slack_app.event("app_mention")
def handle_mention(event, say, client):
    """@メンションを受け取ったときの処理"""
    _handle_message_event(event, say, client)


@slack_app.event("message")
def handle_message(event, say, client):
    """DMメッセージを受け取ったときの処理"""
    # DM (channel_type = "im") のみ処理
    if event.get("channel_type") == "im" and "bot_id" not in event:
        _handle_message_event(event, say, client)


def _handle_message_event(event, say, client):
    """メッセージイベントの共通処理"""
    user_id = event.get("user")
    text = event.get("text", "")
    channel = event.get("channel")
    thread_ts = event.get("thread_ts", event.get("ts"))

    # ボットのメッセージは無視
    if not user_id or event.get("bot_id"):
        return

    # @メンションの除去
    import re
    text = re.sub(r"<@[A-Z0-9]+>", "", text).strip()

    if not text:
        return

    # スラッシュコマンド風の処理
    if text.startswith("/google-auth"):
        _handle_google_auth(say, client, channel, user_id)
        return

    if text.startswith("/help") or text == "ヘルプ":
        _handle_help(say)
        return

    # 処理中インジケーター
    thinking_result = say(text="🤔 考え中...", thread_ts=thread_ts)
    thinking_ts = thinking_result.get("ts")

    # 会話履歴を取得
    history = get_conversation_history(user_id, thread_ts)

    # エージェントを非同期で実行
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        response_text = loop.run_until_complete(
            agent.run(
                user_message=text,
                slack_user_id=user_id,
                slack_channel=channel,
                conversation_history=history,
            )
        )
        loop.close()
    except Exception as e:
        logger.error(f"Agent error: {e}")
        response_text = f"⚠️ エラーが発生しました: {str(e)}"

    # 会話を保存
    save_conversation(user_id, thread_ts, "user", text)
    save_conversation(user_id, thread_ts, "assistant", response_text)

    # 「考え中...」メッセージを削除して返答
    try:
        if thinking_ts:
            client.chat_delete(channel=channel, ts=thinking_ts)
    except Exception:
        pass

    say(text=response_text, thread_ts=thread_ts)


def _handle_google_auth(say, client, channel: str, user_id: str):
    """Google OAuth認証フローを開始"""
    if is_google_authenticated():
        say("✅ すでにGoogle認証済みです！")
        return

    try:
        flow = create_oauth_flow()
        auth_url, _ = flow.authorization_url(
            access_type="offline",
            include_granted_scopes="true",
            prompt="consent",
        )
        say(
            text=f"🔑 Google認証が必要です。\n以下のURLをクリックして認証してください:\n{auth_url}\n\n"
            "認証後、表示されたJSONをRenderの環境変数 `GOOGLE_TOKEN_JSON` に設定してください。"
        )
    except Exception as e:
        say(f"⚠️ 認証URLの生成に失敗しました: {e}")


def _handle_help(say):
    """ヘルプメッセージを送信"""
    help_text = """🤖 *AIエージェント秘書 - 使い方ガイド*

*できること:*
📅 *スケジュール管理*
• 「今日の予定を教えて」
• 「来週月曜10時から会議を追加して」
• 「明日の14時の予定をキャンセルして」

📧 *メール管理*
• 「未読メールを確認して」
• 「○○さんにメールを送って」
• 「会議の件名で届いたメールに返信して」

🔍 *Web検索*
• 「最新のAIニュースを調べて」
• 「○○について調査して」

⏰ *リマインダー*
• 「明日の9時に会議準備リマインドして」
• 「リマインダー一覧を見せて」
• 「リマインダーID:1をキャンセルして」

📊 *日報・レポート*
• 「日報を送って」
• 「今週のまとめを作って」

*設定コマンド:*
• `/google-auth` - Googleアカウント連携
• `/help` - このヘルプを表示"""
    say(help_text)
