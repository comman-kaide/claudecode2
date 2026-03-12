import base64
import re
import traceback
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional
from googleapiclient.discovery import build
from app.utils.google_auth import get_google_credentials

# kaide@comman.co.jp 送信時に自動付与する署名
SIGNATURE_KAIDE = """

※メール簡素化推進中、導入文・締め文は省略していただいて結構です。
＊-----------------------------------------------------------------＊
生成AIで未来につながるgood value をつくる
株式会社カンマン 代表取締役  貝出　康
E-mail kaide@comman.co.jp  iPhone:090-3181-7682
→facebook  http://www.facebook.com/yasushi.kaide
→twitter　  http://twitter.com/comman　
＊-----------------------------------------------------------------＊
★生成AI研修/ブランディング/各種ホームページ制作//システム開発
Comman,inc/株式会社カンマン URL http://www.comman.co.jp
〒770-0943 徳島市中昭和町2丁目39-5 tel:088-611-2333　fax:088-611-2332
＊-----------------------------------------------------------------＊"""

# 署名を付与するメールアドレスとその署名のマッピング
SIGNATURES = {
    "kaide@comman.co.jp": SIGNATURE_KAIDE,
}


def _get_sender_email() -> str:
    """送信者のメールアドレスをGmail APIから取得"""
    try:
        service = get_gmail_service()
        profile = service.users().getProfile(userId="me").execute()
        return profile.get("emailAddress", "")
    except Exception:
        return ""


def _append_signature(body: str) -> str:
    """送信者のメールアドレスに対応する署名を本文に付加"""
    sender = _get_sender_email()
    signature = SIGNATURES.get(sender, "")
    if signature:
        return body + signature
    return body


def get_gmail_service():
    creds = get_google_credentials()
    if not creds:
        raise ValueError("Google認証が完了していません。/google-auth コマンドで認証してください。")
    return build("gmail", "v1", credentials=creds)


def list_emails(max_results: int = 10, query: str = "is:unread", include_body: bool = False) -> dict:
    """メール一覧を取得"""
    try:
        service = get_gmail_service()
        result = service.users().messages().list(
            userId="me", q=query, maxResults=max_results
        ).execute()

        messages = result.get("messages", [])
        emails = []
        for msg in messages:
            msg_data = service.users().messages().get(
                userId="me", id=msg["id"], format="full"
            ).execute()

            headers = {h["name"]: h["value"] for h in msg_data["payload"].get("headers", [])}
            body = ""
            if include_body:
                body = _extract_body(msg_data["payload"])

            emails.append({
                "id": msg["id"],
                "thread_id": msg_data.get("threadId"),
                "subject": headers.get("Subject", "(件名なし)"),
                "from": headers.get("From", ""),
                "to": headers.get("To", ""),
                "date": headers.get("Date", ""),
                "snippet": msg_data.get("snippet", ""),
                "body": body[:2000] if body else "",
                "labels": msg_data.get("labelIds", []),
            })

        return {"success": True, "emails": emails, "count": len(emails)}
    except Exception as e:
        return {"success": False, "error": str(e), "traceback": traceback.format_exc()}


def get_email(message_id: str) -> dict:
    """特定のメールを取得（本文含む）"""
    try:
        service = get_gmail_service()
        msg_data = service.users().messages().get(
            userId="me", id=message_id, format="full"
        ).execute()

        headers = {h["name"]: h["value"] for h in msg_data["payload"].get("headers", [])}
        body = _extract_body(msg_data["payload"])

        return {
            "success": True,
            "id": message_id,
            "subject": headers.get("Subject", "(件名なし)"),
            "from": headers.get("From", ""),
            "to": headers.get("To", ""),
            "cc": headers.get("Cc", ""),
            "date": headers.get("Date", ""),
            "body": body[:5000],
            "labels": msg_data.get("labelIds", []),
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def send_email(to: str, subject: str, body: str, cc: str = "", is_html: bool = False) -> dict:
    """メールを送信（署名を自動付与）"""
    try:
        service = get_gmail_service()

        # 署名を自動付与
        body_with_signature = _append_signature(body)

        message = MIMEMultipart("alternative")
        message["to"] = to
        message["subject"] = subject
        if cc:
            message["cc"] = cc

        if is_html:
            message.attach(MIMEText(body_with_signature, "html"))
        else:
            message.attach(MIMEText(body_with_signature, "plain"))

        raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
        sent = service.users().messages().send(userId="me", body={"raw": raw}).execute()

        return {
            "success": True,
            "message_id": sent["id"],
            "message": f"メールを {to} に送信しました（署名付き）",
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def reply_email(message_id: str, body: str, reply_all: bool = False) -> dict:
    """メールに返信（署名を自動付与）"""
    try:
        service = get_gmail_service()
        original = service.users().messages().get(
            userId="me", id=message_id, format="full"
        ).execute()

        headers = {h["name"]: h["value"] for h in original["payload"].get("headers", [])}
        subject = headers.get("Subject", "")
        if not subject.startswith("Re:"):
            subject = f"Re: {subject}"

        to = headers.get("Reply-To", headers.get("From", ""))
        thread_id = original.get("threadId")

        # 署名を自動付与
        body_with_signature = _append_signature(body)

        message = MIMEText(body_with_signature, "plain")
        message["to"] = to
        message["subject"] = subject
        message["In-Reply-To"] = headers.get("Message-ID", "")
        message["References"] = headers.get("Message-ID", "")

        if reply_all:
            cc_list = []
            if headers.get("Cc"):
                cc_list.append(headers["Cc"])
            if headers.get("To"):
                cc_list.append(headers["To"])
            if cc_list:
                message["cc"] = ", ".join(cc_list)

        raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
        sent = service.users().messages().send(
            userId="me", body={"raw": raw, "threadId": thread_id}
        ).execute()

        return {"success": True, "message_id": sent["id"], "message": "返信を送信しました（署名付き）"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def mark_as_read(message_id: str) -> dict:
    """メールを既読にする"""
    try:
        service = get_gmail_service()
        service.users().messages().modify(
            userId="me",
            id=message_id,
            body={"removeLabelIds": ["UNREAD"]},
        ).execute()
        return {"success": True, "message": "既読にしました"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def search_emails(query: str, max_results: int = 10) -> dict:
    """メールを検索"""
    return list_emails(max_results=max_results, query=query, include_body=False)


def _extract_body(payload: dict) -> str:
    """メール本文を抽出"""
    body = ""
    if "parts" in payload:
        for part in payload["parts"]:
            if part["mimeType"] == "text/plain":
                data = part["body"].get("data", "")
                if data:
                    body = base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")
                    break
            elif part["mimeType"] == "text/html" and not body:
                data = part["body"].get("data", "")
                if data:
                    html = base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")
                    body = re.sub(r"<[^>]+>", "", html)
    else:
        data = payload.get("body", {}).get("data", "")
        if data:
            body = base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")
    return body.strip()
