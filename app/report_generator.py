"""
日報・レポート生成モジュール
"""

import anthropic
from datetime import datetime
from config.settings import settings
from app.tools import calendar_tools, gmail_tools


async def generate_morning_briefing(channel: str = "") -> dict:
    """毎朝8時の予定・ToDoリスト通知を生成してSlackに送信"""
    try:
        if not channel:
            channel = settings.default_slack_channel

        from app.slack_app import get_slack_client
        slack_client = get_slack_client()

        # データ収集
        today_events = calendar_tools.get_today_schedule()
        unread_emails = gmail_tools.list_emails(max_results=20, query="is:unread")

        # 朝のブリーフィング生成
        report = await _generate_morning_briefing_with_claude(today_events, unread_emails)

        # Slackに送信
        slack_client.chat_postMessage(
            channel=channel,
            text=report,
            mrkdwn=True,
        )

        return {"success": True, "message": f"朝のブリーフィングを {channel} に送信しました"}
    except Exception as e:
        return {"success": False, "error": str(e)}


async def _generate_morning_briefing_with_claude(today_events: dict, unread_emails: dict) -> str:
    """Claudeを使って朝のブリーフィング（予定＋ToDoリスト）を生成"""
    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

    today_str = datetime.now(settings.tz).strftime("%Y年%m月%d日（%a）")

    # イベント情報を整理
    events_text = "（本日の予定なし）"
    if today_events.get("success") and today_events.get("events"):
        events_list = []
        for e in today_events["events"]:
            start = e['start']
            # ISO形式の時刻を見やすく変換
            if start and "T" in str(start):
                try:
                    dt = datetime.fromisoformat(start)
                    start = dt.strftime("%H:%M")
                except Exception:
                    pass
            end = e['end']
            if end and "T" in str(end):
                try:
                    dt = datetime.fromisoformat(end)
                    end = dt.strftime("%H:%M")
                except Exception:
                    pass
            cal_name = e.get('calendar', '')
            cal_label = f" [{cal_name}]" if cal_name else ""
            events_list.append(f"- {start}〜{end}: {e['summary']}{cal_label}")
        events_text = "\n".join(events_list)

    # メール情報を整理
    emails_text = "（未読メールなし）"
    if unread_emails.get("success") and unread_emails.get("emails"):
        email_list = []
        for em in unread_emails["emails"][:10]:
            email_list.append(f"- {em['from']} / {em['subject']}")
        emails_text = "\n".join(email_list)

    prompt = f"""以下の情報をもとに、{today_str} の朝のブリーフィングをSlack用Markdown形式で作成してください。
絵文字を使って見やすくしてください。

## 今日のカレンダー
{events_text}

## 未読メール ({unread_emails.get('count', 0)}件)
{emails_text}

## 出力形式（必ずこの構成で）

🌅 *{today_str} おはようございます！*

📅 *今日のスケジュール*
（カレンダーの予定を時系列で箇条書き。予定がなければ「本日は予定なし」）

📋 *今日のToDoリスト*
（カレンダーの予定・未読メールから、今日やるべきことを3〜7項目に整理。
例: 会議の準備、返信が必要なメール、締め切りタスクなど。
具体的かつ実行可能なタスクとして記載すること）

📧 *要確認メール*
（未読メールのうち対応が必要そうなものをピックアップ。なければ省略）

💡 *一言*
（今日を乗り切るための短い一言）
"""

    response = client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=2000,
        messages=[{"role": "user", "content": prompt}],
    )

    return response.content[0].text


async def generate_and_send_daily_report(channel: str = "") -> dict:
    """日報を生成してSlackに送信する（夕方用）"""
    try:
        if not channel:
            channel = settings.default_slack_channel

        from app.slack_app import get_slack_client
        slack_client = get_slack_client()

        # データ収集
        today_events = calendar_tools.get_today_schedule()
        unread_emails = gmail_tools.list_emails(max_results=20, query="is:unread")

        # レポート生成
        report = await _generate_report_with_claude(today_events, unread_emails)

        # Slackに送信
        slack_client.chat_postMessage(
            channel=channel,
            text=report,
            mrkdwn=True,
        )

        # DBに保存
        from app.database import DailyReport, SessionLocal
        db = SessionLocal()
        try:
            dr = DailyReport(
                date=datetime.now(settings.tz).strftime("%Y-%m-%d"),
                content=report,
                slack_channel=channel,
            )
            db.add(dr)
            db.commit()
        finally:
            db.close()

        return {"success": True, "message": f"日報を {channel} に送信しました"}
    except Exception as e:
        return {"success": False, "error": str(e)}


async def _generate_report_with_claude(today_events: dict, unread_emails: dict) -> str:
    """Claudeを使って夕方の日報を生成"""
    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

    today_str = datetime.now(settings.tz).strftime("%Y年%m月%d日（%a）")

    events_text = "（なし）"
    if today_events.get("success") and today_events.get("events"):
        events_list = []
        for e in today_events["events"]:
            events_list.append(f"- {e['start']} 〜 {e['end']}: {e['summary']}")
        events_text = "\n".join(events_list)

    emails_text = "（未読メールなし）"
    if unread_emails.get("success") and unread_emails.get("emails"):
        email_list = []
        for em in unread_emails["emails"][:10]:
            email_list.append(f"- 差出人: {em['from']} / 件名: {em['subject']}")
        emails_text = "\n".join(email_list)

    prompt = f"""以下の情報をもとに、{today_str} の日報をSlack用にMarkdown形式で作成してください。
絵文字を使って見やすくしてください。

## 今日のカレンダー
{events_text}

## 未読メール ({unread_emails.get('count', 0)}件)
{emails_text}

日報の形式：
- タイトル（日付入り）
- 今日のスケジュールのサマリー
- 要対応メールのピックアップ
- 明日の準備事項（カレンダーから予測）
- 一言メッセージ
"""

    response = client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=2000,
        messages=[{"role": "user", "content": prompt}],
    )

    return response.content[0].text
