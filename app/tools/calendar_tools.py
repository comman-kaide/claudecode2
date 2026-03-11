from datetime import datetime, timedelta
from typing import Optional
from googleapiclient.discovery import build
from app.utils.google_auth import get_google_credentials
from config.settings import settings
import pytz


def get_calendar_service():
    creds = get_google_credentials()
    if not creds:
        raise ValueError("Google認証が完了していません。/google-auth コマンドで認証してください。")
    return build("calendar", "v3", credentials=creds)


def list_events(days_ahead: int = 7, max_results: int = 20) -> dict:
    """今後のカレンダーイベントを取得"""
    try:
        service = get_calendar_service()
        tz = settings.tz
        now = datetime.now(tz)
        end = now + timedelta(days=days_ahead)

        events_result = service.events().list(
            calendarId="primary",
            timeMin=now.isoformat(),
            timeMax=end.isoformat(),
            maxResults=max_results,
            singleEvents=True,
            orderBy="startTime",
        ).execute()

        events = events_result.get("items", [])
        result = []
        for event in events:
            start = event["start"].get("dateTime", event["start"].get("date"))
            end_time = event["end"].get("dateTime", event["end"].get("date"))
            result.append({
                "id": event["id"],
                "summary": event.get("summary", "(タイトルなし)"),
                "start": start,
                "end": end_time,
                "location": event.get("location", ""),
                "description": event.get("description", ""),
                "attendees": [a["email"] for a in event.get("attendees", [])],
            })

        return {"success": True, "events": result, "count": len(result)}
    except Exception as e:
        return {"success": False, "error": str(e)}


def create_event(
    summary: str,
    start_datetime: str,
    end_datetime: str,
    description: str = "",
    location: str = "",
    attendees: Optional[list] = None,
) -> dict:
    """カレンダーにイベントを作成"""
    try:
        service = get_calendar_service()
        tz_str = settings.timezone

        event_body = {
            "summary": summary,
            "description": description,
            "location": location,
            "start": {"dateTime": start_datetime, "timeZone": tz_str},
            "end": {"dateTime": end_datetime, "timeZone": tz_str},
        }
        if attendees:
            event_body["attendees"] = [{"email": email} for email in attendees]

        event = service.events().insert(calendarId="primary", body=event_body).execute()
        return {
            "success": True,
            "event_id": event["id"],
            "summary": event["summary"],
            "start": event["start"].get("dateTime"),
            "link": event.get("htmlLink", ""),
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def update_event(event_id: str, **kwargs) -> dict:
    """カレンダーイベントを更新"""
    try:
        service = get_calendar_service()
        event = service.events().get(calendarId="primary", eventId=event_id).execute()

        if "summary" in kwargs:
            event["summary"] = kwargs["summary"]
        if "description" in kwargs:
            event["description"] = kwargs["description"]
        if "location" in kwargs:
            event["location"] = kwargs["location"]
        if "start_datetime" in kwargs:
            event["start"] = {"dateTime": kwargs["start_datetime"], "timeZone": settings.timezone}
        if "end_datetime" in kwargs:
            event["end"] = {"dateTime": kwargs["end_datetime"], "timeZone": settings.timezone}

        updated = service.events().update(
            calendarId="primary", eventId=event_id, body=event
        ).execute()
        return {"success": True, "event_id": updated["id"], "summary": updated["summary"]}
    except Exception as e:
        return {"success": False, "error": str(e)}


def delete_event(event_id: str) -> dict:
    """カレンダーイベントを削除"""
    try:
        service = get_calendar_service()
        service.events().delete(calendarId="primary", eventId=event_id).execute()
        return {"success": True, "message": f"イベント {event_id} を削除しました"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def get_today_schedule() -> dict:
    """今日のスケジュールを取得"""
    try:
        service = get_calendar_service()
        tz = settings.tz
        now = datetime.now(tz)
        start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end_of_day = now.replace(hour=23, minute=59, second=59, microsecond=0)

        events_result = service.events().list(
            calendarId="primary",
            timeMin=start_of_day.isoformat(),
            timeMax=end_of_day.isoformat(),
            singleEvents=True,
            orderBy="startTime",
        ).execute()

        events = events_result.get("items", [])
        result = []
        for event in events:
            start = event["start"].get("dateTime", event["start"].get("date"))
            end_time = event["end"].get("dateTime", event["end"].get("date"))
            result.append({
                "id": event["id"],
                "summary": event.get("summary", "(タイトルなし)"),
                "start": start,
                "end": end_time,
                "location": event.get("location", ""),
            })

        return {
            "success": True,
            "date": now.strftime("%Y-%m-%d"),
            "events": result,
            "count": len(result),
        }
    except Exception as e:
        return {"success": False, "error": str(e)}
