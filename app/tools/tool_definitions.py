"""
Claude AIエージェントのツール定義（Anthropic Tool Use API形式）
"""

TOOL_DEFINITIONS = [
    # ===== カレンダーツール =====
    {
        "name": "calendar_list_events",
        "description": "Google Calendarの予定を取得します。今後の予定を確認する際に使用してください。",
        "input_schema": {
            "type": "object",
            "properties": {
                "days_ahead": {
                    "type": "integer",
                    "description": "何日先までの予定を取得するか（デフォルト: 7日）",
                    "default": 7,
                },
                "max_results": {
                    "type": "integer",
                    "description": "最大取得件数（デフォルト: 20）",
                    "default": 20,
                },
            },
        },
    },
    {
        "name": "calendar_get_today",
        "description": "今日のスケジュールを取得します。",
        "input_schema": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "calendar_create_event",
        "description": "Google Calendarに新しい予定を作成します。",
        "input_schema": {
            "type": "object",
            "properties": {
                "summary": {
                    "type": "string",
                    "description": "予定のタイトル",
                },
                "start_datetime": {
                    "type": "string",
                    "description": "開始日時（ISO8601形式: 例 2024-03-15T10:00:00）",
                },
                "end_datetime": {
                    "type": "string",
                    "description": "終了日時（ISO8601形式: 例 2024-03-15T11:00:00）",
                },
                "description": {
                    "type": "string",
                    "description": "予定の詳細・メモ",
                    "default": "",
                },
                "location": {
                    "type": "string",
                    "description": "場所",
                    "default": "",
                },
                "attendees": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "参加者のメールアドレスのリスト",
                    "default": [],
                },
            },
            "required": ["summary", "start_datetime", "end_datetime"],
        },
    },
    {
        "name": "calendar_update_event",
        "description": "Google Calendarの既存の予定を更新します。",
        "input_schema": {
            "type": "object",
            "properties": {
                "event_id": {
                    "type": "string",
                    "description": "更新するイベントのID",
                },
                "summary": {"type": "string", "description": "新しいタイトル"},
                "start_datetime": {"type": "string", "description": "新しい開始日時"},
                "end_datetime": {"type": "string", "description": "新しい終了日時"},
                "description": {"type": "string", "description": "新しい詳細"},
                "location": {"type": "string", "description": "新しい場所"},
            },
            "required": ["event_id"],
        },
    },
    {
        "name": "calendar_delete_event",
        "description": "Google Calendarの予定を削除します。",
        "input_schema": {
            "type": "object",
            "properties": {
                "event_id": {
                    "type": "string",
                    "description": "削除するイベントのID",
                },
            },
            "required": ["event_id"],
        },
    },

    # ===== Gmailツール =====
    {
        "name": "gmail_list_emails",
        "description": "受信メールの一覧を取得します。未読メールの確認や検索に使用します。",
        "input_schema": {
            "type": "object",
            "properties": {
                "max_results": {
                    "type": "integer",
                    "description": "最大取得件数（デフォルト: 10）",
                    "default": 10,
                },
                "query": {
                    "type": "string",
                    "description": "Gmail検索クエリ（例: 'is:unread', 'from:example@gmail.com', 'subject:会議'）",
                    "default": "is:unread",
                },
            },
        },
    },
    {
        "name": "gmail_get_email",
        "description": "特定のメールの本文を取得します。",
        "input_schema": {
            "type": "object",
            "properties": {
                "message_id": {
                    "type": "string",
                    "description": "メールのID",
                },
            },
            "required": ["message_id"],
        },
    },
    {
        "name": "gmail_send_email",
        "description": "メールを送信します。",
        "input_schema": {
            "type": "object",
            "properties": {
                "to": {
                    "type": "string",
                    "description": "送信先メールアドレス（複数の場合はカンマ区切り）",
                },
                "subject": {
                    "type": "string",
                    "description": "件名",
                },
                "body": {
                    "type": "string",
                    "description": "メール本文",
                },
                "cc": {
                    "type": "string",
                    "description": "CCのメールアドレス",
                    "default": "",
                },
            },
            "required": ["to", "subject", "body"],
        },
    },
    {
        "name": "gmail_reply_email",
        "description": "メールに返信します。",
        "input_schema": {
            "type": "object",
            "properties": {
                "message_id": {
                    "type": "string",
                    "description": "返信するメールのID",
                },
                "body": {
                    "type": "string",
                    "description": "返信本文",
                },
                "reply_all": {
                    "type": "boolean",
                    "description": "全員に返信するか",
                    "default": False,
                },
            },
            "required": ["message_id", "body"],
        },
    },
    {
        "name": "gmail_search_emails",
        "description": "メールを検索します。",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "検索クエリ（例: 'from:boss@company.com subject:報告'）",
                },
                "max_results": {
                    "type": "integer",
                    "description": "最大取得件数",
                    "default": 10,
                },
            },
            "required": ["query"],
        },
    },

    # ===== Web検索ツール =====
    {
        "name": "web_search",
        "description": "インターネットでWeb検索を行います。最新情報や調査に使用してください。",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "検索クエリ",
                },
                "max_results": {
                    "type": "integer",
                    "description": "最大結果件数（デフォルト: 5）",
                    "default": 5,
                },
                "search_depth": {
                    "type": "string",
                    "description": "検索深度: 'basic'（高速）または 'advanced'（詳細）",
                    "enum": ["basic", "advanced"],
                    "default": "basic",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "get_webpage_content",
        "description": "特定のURLのWebページ内容を取得します。",
        "input_schema": {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "取得するURLアドレス",
                },
            },
            "required": ["url"],
        },
    },

    # ===== リマインダーツール =====
    {
        "name": "reminder_set",
        "description": "指定した日時にSlackでリマインダーを送信します。",
        "input_schema": {
            "type": "object",
            "properties": {
                "message": {
                    "type": "string",
                    "description": "リマインダーのメッセージ内容",
                },
                "remind_at": {
                    "type": "string",
                    "description": "リマインド日時（形式: 'YYYY-MM-DD HH:MM' 例: '2024-03-15 09:00'）",
                },
                "channel": {
                    "type": "string",
                    "description": "通知先チャンネル（省略時はメッセージを送ったチャンネル）",
                    "default": "",
                },
            },
            "required": ["message", "remind_at"],
        },
    },
    {
        "name": "reminder_list",
        "description": "設定中のリマインダー一覧を表示します。",
        "input_schema": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "reminder_cancel",
        "description": "リマインダーをキャンセルします。",
        "input_schema": {
            "type": "object",
            "properties": {
                "reminder_id": {
                    "type": "integer",
                    "description": "キャンセルするリマインダーのID",
                },
            },
            "required": ["reminder_id"],
        },
    },

    # ===== レポート生成ツール =====
    {
        "name": "generate_daily_report",
        "description": "その日のカレンダーやメールをまとめた日報を生成してSlackに送信します。",
        "input_schema": {
            "type": "object",
            "properties": {
                "channel": {
                    "type": "string",
                    "description": "送信先チャンネル（省略時はデフォルトチャンネル）",
                    "default": "",
                },
            },
        },
    },
]
