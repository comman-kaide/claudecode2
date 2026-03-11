"""
Claude AIエージェントのコアロジック
ツール呼び出し → 実行 → 返答 のループを管理
"""

import json
from datetime import datetime
from typing import Optional
import anthropic

from config.settings import settings
from app.tools.tool_definitions import TOOL_DEFINITIONS
from app.tools import calendar_tools, gmail_tools, search_tools, reminder_tools


SYSTEM_PROMPT = """あなたは優秀な個人秘書AIです。ユーザーのSlackメッセージに対して、
必要に応じてツールを使いながら丁寧にお手伝いします。

## あなたにできること
- 📅 Google Calendarの予定確認・作成・更新・削除
- 📧 Gmailの確認・送信・返信・検索
- 🔍 Web検索・情報収集・調査
- ⏰ リマインダーの設定・管理
- 📊 日報・レポートの生成

## 行動指針
1. **積極的にツールを使う**: ユーザーの要求を実現するために必要なツールを積極的に呼び出してください
2. **確認を取る**: メール送信・予定削除など取り消しが難しい操作は、実行前に確認してください
3. **丁寧な報告**: ツール実行後は結果をわかりやすくまとめて報告してください
4. **日本語で対応**: 基本的に日本語で返答してください
5. **日時の扱い**: 現在時刻は {current_time} です。相対的な日時表現（「明日」「来週月曜」など）は適切に解釈してください

## 注意事項
- Google認証が必要なツールが使えない場合は、ユーザーに `/google-auth` コマンドを案内してください
- エラーが発生した場合は、何が問題かをわかりやすく説明してください
"""


class SecretaryAgent:
    def __init__(self):
        self.client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        self.model = "claude-3-5-sonnet-20241022"

    async def run(
        self,
        user_message: str,
        slack_user_id: str,
        slack_channel: str,
        conversation_history: Optional[list] = None,
    ) -> str:
        """
        メッセージを受け取り、ツールを使いながら返答を生成する
        """
        if conversation_history is None:
            conversation_history = []

        messages = conversation_history + [{"role": "user", "content": user_message}]

        current_time = datetime.now(settings.tz).strftime("%Y年%m月%d日 %H:%M %Z")
        system = SYSTEM_PROMPT.format(current_time=current_time)

        # エージェントループ（最大10ターン）
        for _ in range(10):
            response = self.client.messages.create(
                model=self.model,
                max_tokens=4096,
                system=system,
                tools=TOOL_DEFINITIONS,
                messages=messages,
            )

            # ツール呼び出しがない場合は返答を返す
            if response.stop_reason == "end_turn":
                return self._extract_text(response)

            # ツール呼び出しを処理
            if response.stop_reason == "tool_use":
                # アシスタントの応答をメッセージ履歴に追加
                messages.append({"role": "assistant", "content": response.content})

                # 各ツール呼び出しを実行
                tool_results = []
                for block in response.content:
                    if block.type == "tool_use":
                        tool_result = await self._execute_tool(
                            tool_name=block.name,
                            tool_input=block.input,
                            slack_user_id=slack_user_id,
                            slack_channel=slack_channel,
                        )
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": json.dumps(tool_result, ensure_ascii=False),
                        })

                # ツール結果をメッセージ履歴に追加
                messages.append({"role": "user", "content": tool_results})
            else:
                # 予期しないstop_reason
                return self._extract_text(response)

        return "申し訳ありません。処理が複雑すぎて完了できませんでした。もう少し具体的に指示していただけますか？"

    async def _execute_tool(
        self,
        tool_name: str,
        tool_input: dict,
        slack_user_id: str,
        slack_channel: str,
    ) -> dict:
        """ツールを実行して結果を返す"""
        try:
            # ===== カレンダーツール =====
            if tool_name == "calendar_list_events":
                return calendar_tools.list_events(
                    days_ahead=tool_input.get("days_ahead", 7),
                    max_results=tool_input.get("max_results", 20),
                )
            elif tool_name == "calendar_get_today":
                return calendar_tools.get_today_schedule()
            elif tool_name == "calendar_create_event":
                return calendar_tools.create_event(
                    summary=tool_input["summary"],
                    start_datetime=tool_input["start_datetime"],
                    end_datetime=tool_input["end_datetime"],
                    description=tool_input.get("description", ""),
                    location=tool_input.get("location", ""),
                    attendees=tool_input.get("attendees", []),
                )
            elif tool_name == "calendar_update_event":
                kwargs = {k: v for k, v in tool_input.items() if k != "event_id"}
                return calendar_tools.update_event(tool_input["event_id"], **kwargs)
            elif tool_name == "calendar_delete_event":
                return calendar_tools.delete_event(tool_input["event_id"])

            # ===== Gmailツール =====
            elif tool_name == "gmail_list_emails":
                return gmail_tools.list_emails(
                    max_results=tool_input.get("max_results", 10),
                    query=tool_input.get("query", "is:unread"),
                )
            elif tool_name == "gmail_get_email":
                return gmail_tools.get_email(tool_input["message_id"])
            elif tool_name == "gmail_send_email":
                return gmail_tools.send_email(
                    to=tool_input["to"],
                    subject=tool_input["subject"],
                    body=tool_input["body"],
                    cc=tool_input.get("cc", ""),
                )
            elif tool_name == "gmail_reply_email":
                return gmail_tools.reply_email(
                    message_id=tool_input["message_id"],
                    body=tool_input["body"],
                    reply_all=tool_input.get("reply_all", False),
                )
            elif tool_name == "gmail_search_emails":
                return gmail_tools.search_emails(
                    query=tool_input["query"],
                    max_results=tool_input.get("max_results", 10),
                )

            # ===== Web検索ツール =====
            elif tool_name == "web_search":
                return search_tools.web_search(
                    query=tool_input["query"],
                    max_results=tool_input.get("max_results", 5),
                    search_depth=tool_input.get("search_depth", "basic"),
                )
            elif tool_name == "get_webpage_content":
                return search_tools.get_webpage_content(tool_input["url"])

            # ===== リマインダーツール =====
            elif tool_name == "reminder_set":
                channel = tool_input.get("channel") or slack_channel
                return reminder_tools.set_reminder(
                    slack_user_id=slack_user_id,
                    slack_channel=channel,
                    message=tool_input["message"],
                    remind_at_str=tool_input["remind_at"],
                )
            elif tool_name == "reminder_list":
                return reminder_tools.list_reminders(slack_user_id=slack_user_id)
            elif tool_name == "reminder_cancel":
                return reminder_tools.cancel_reminder(
                    reminder_id=tool_input["reminder_id"],
                    slack_user_id=slack_user_id,
                )

            # ===== レポートツール =====
            elif tool_name == "generate_daily_report":
                # インポートを遅延して循環参照を回避
                from app.report_generator import generate_and_send_daily_report
                channel = tool_input.get("channel") or settings.default_slack_channel
                return await generate_and_send_daily_report(channel)

            else:
                return {"success": False, "error": f"不明なツール: {tool_name}"}

        except Exception as e:
            return {"success": False, "error": f"ツール実行エラー ({tool_name}): {str(e)}"}

    def _extract_text(self, response) -> str:
        """レスポンスからテキストを抽出"""
        text_blocks = [block.text for block in response.content if hasattr(block, "text")]
        return "\n".join(text_blocks) if text_blocks else "処理が完了しました。"
