"""
APSchedulerによるバックグラウンドタスク管理
- リマインダーの定期チェック・送信
- 毎朝8時: 今日の予定＋ToDoリスト通知
- 毎夕(設定時刻): 日報送信
"""

import asyncio
import logging
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from config.settings import settings
from app.tools.reminder_tools import get_pending_reminders, mark_reminder_sent

logger = logging.getLogger(__name__)

scheduler = BackgroundScheduler(timezone=settings.tz)


def start_scheduler():
    """スケジューラーを起動"""
    # リマインダーチェック: 1分ごと
    scheduler.add_job(
        check_and_send_reminders,
        IntervalTrigger(minutes=1),
        id="reminder_check",
        replace_existing=True,
    )

    # 毎朝8時: 予定・ToDoリスト通知
    scheduler.add_job(
        send_morning_briefing,
        CronTrigger(hour=8, minute=0, timezone=settings.tz),
        id="morning_briefing",
        replace_existing=True,
    )

    # 夕方の日報自動送信
    report_time = settings.daily_report_time.split(":")
    hour, minute = int(report_time[0]), int(report_time[1])
    scheduler.add_job(
        send_scheduled_daily_report,
        CronTrigger(hour=hour, minute=minute, timezone=settings.tz),
        id="daily_report",
        replace_existing=True,
    )

    # Renderスリープ対策: 10分ごとに自己pingしてサービスを起こし続ける
    scheduler.add_job(
        keep_alive_ping,
        IntervalTrigger(minutes=10),
        id="keep_alive",
        replace_existing=True,
    )

    scheduler.start()
    logger.info("Scheduler started.")
    logger.info("Morning briefing: 08:00 JST")
    logger.info(f"Daily report: {settings.daily_report_time} JST")
    logger.info("Keep-alive ping: every 10 minutes")


def stop_scheduler():
    """スケジューラーを停止"""
    if scheduler.running:
        scheduler.shutdown()
        logger.info("Scheduler stopped")


def keep_alive_ping():
    """Renderのスリープを防ぐための自己ping"""
    try:
        import urllib.request
        from config.settings import settings
        # Renderのサービス自身にpingする（環境変数からURL取得、なければスキップ）
        render_url = getattr(settings, 'render_external_url', None)
        if not render_url:
            render_url = "https://secretary-ai-ve06.onrender.com"
        urllib.request.urlopen(f"{render_url}/health", timeout=10)
        logger.debug("Keep-alive ping sent")
    except Exception as e:
        logger.debug(f"Keep-alive ping failed (non-critical): {e}")


def check_and_send_reminders():
    """未送信のリマインダーをチェックして送信"""
    try:
        reminders = get_pending_reminders()
        if not reminders:
            return

        from app.slack_app import get_slack_client
        slack_client = get_slack_client()

        for reminder in reminders:
            try:
                message = f"⏰ *リマインダー*\n{reminder.message}"
                slack_client.chat_postMessage(
                    channel=reminder.slack_channel,
                    text=message,
                    mrkdwn=True,
                )
                mark_reminder_sent(reminder.id)
                logger.info(f"Reminder {reminder.id} sent to {reminder.slack_channel}")
            except Exception as e:
                logger.error(f"Failed to send reminder {reminder.id}: {e}")
    except Exception as e:
        logger.error(f"Error in check_and_send_reminders: {e}")


def send_morning_briefing():
    """毎朝8時: 今日の予定・ToDoリスト通知を送信"""
    try:
        from app.report_generator import generate_morning_briefing

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(
            generate_morning_briefing(settings.default_slack_channel)
        )
        loop.close()

        if result.get("success"):
            logger.info("Morning briefing sent successfully")
        else:
            logger.error(f"Morning briefing failed: {result.get('error')}")
    except Exception as e:
        logger.error(f"Error in send_morning_briefing: {e}")


def send_scheduled_daily_report():
    """スケジュールされた夕方の日報を送信"""
    try:
        from app.report_generator import generate_and_send_daily_report

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(
            generate_and_send_daily_report(settings.default_slack_channel)
        )
        loop.close()

        if result.get("success"):
            logger.info("Daily report sent successfully")
        else:
            logger.error(f"Daily report failed: {result.get('error')}")
    except Exception as e:
        logger.error(f"Error in send_scheduled_daily_report: {e}")
