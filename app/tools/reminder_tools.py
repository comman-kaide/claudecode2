from datetime import datetime
from typing import Optional
from sqlalchemy.orm import Session
from app.database import Reminder, get_db, SessionLocal
from config.settings import settings
import pytz


def set_reminder(
    slack_user_id: str,
    slack_channel: str,
    message: str,
    remind_at_str: str,
) -> dict:
    """リマインダーを設定する
    
    Args:
        slack_user_id: SlackユーザーID
        slack_channel: 通知先チャンネル
        message: リマインダーメッセージ
        remind_at_str: リマインド日時 (ISO形式 or "YYYY-MM-DD HH:MM")
    """
    try:
        tz = settings.tz

        # 日時パース
        remind_at_local = None
        for fmt in ["%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S"]:
            try:
                remind_at_local = datetime.strptime(remind_at_str, fmt)
                break
            except ValueError:
                continue

        if not remind_at_local:
            return {"success": False, "error": f"日時のフォーマットが不正です: {remind_at_str}"}

        # ローカル時刻をUTCに変換
        remind_at_aware = tz.localize(remind_at_local)
        remind_at_utc = remind_at_aware.astimezone(pytz.utc).replace(tzinfo=None)

        db = SessionLocal()
        try:
            reminder = Reminder(
                slack_user_id=slack_user_id,
                slack_channel=slack_channel,
                message=message,
                remind_at=remind_at_utc,
                is_sent=False,
            )
            db.add(reminder)
            db.commit()
            db.refresh(reminder)

            return {
                "success": True,
                "reminder_id": reminder.id,
                "message": message,
                "remind_at": remind_at_aware.strftime("%Y-%m-%d %H:%M %Z"),
            }
        finally:
            db.close()
    except Exception as e:
        return {"success": False, "error": str(e)}


def list_reminders(slack_user_id: str) -> dict:
    """未送信のリマインダー一覧を取得"""
    try:
        db = SessionLocal()
        try:
            tz = settings.tz
            reminders = (
                db.query(Reminder)
                .filter(Reminder.slack_user_id == slack_user_id, Reminder.is_sent == False)
                .order_by(Reminder.remind_at)
                .all()
            )

            result = []
            for r in reminders:
                remind_at_utc = pytz.utc.localize(r.remind_at)
                remind_at_local = remind_at_utc.astimezone(tz)
                result.append({
                    "id": r.id,
                    "message": r.message,
                    "remind_at": remind_at_local.strftime("%Y-%m-%d %H:%M %Z"),
                    "channel": r.slack_channel,
                })

            return {"success": True, "reminders": result, "count": len(result)}
        finally:
            db.close()
    except Exception as e:
        return {"success": False, "error": str(e)}


def cancel_reminder(reminder_id: int, slack_user_id: str) -> dict:
    """リマインダーをキャンセル"""
    try:
        db = SessionLocal()
        try:
            reminder = (
                db.query(Reminder)
                .filter(Reminder.id == reminder_id, Reminder.slack_user_id == slack_user_id)
                .first()
            )
            if not reminder:
                return {"success": False, "error": f"リマインダー ID:{reminder_id} が見つかりません"}

            db.delete(reminder)
            db.commit()
            return {"success": True, "message": f"リマインダー ID:{reminder_id} をキャンセルしました"}
        finally:
            db.close()
    except Exception as e:
        return {"success": False, "error": str(e)}


def get_pending_reminders() -> list:
    """送信すべきリマインダーを取得（スケジューラー用）"""
    db = SessionLocal()
    try:
        now_utc = datetime.utcnow()
        reminders = (
            db.query(Reminder)
            .filter(Reminder.remind_at <= now_utc, Reminder.is_sent == False)
            .all()
        )
        return reminders
    finally:
        db.close()


def mark_reminder_sent(reminder_id: int):
    """リマインダーを送信済みにする"""
    db = SessionLocal()
    try:
        reminder = db.query(Reminder).filter(Reminder.id == reminder_id).first()
        if reminder:
            reminder.is_sent = True
            db.commit()
    finally:
        db.close()
