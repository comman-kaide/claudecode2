from pydantic_settings import BaseSettings
from pydantic import Field
from typing import Optional
import pytz


class Settings(BaseSettings):
    # App
    app_env: str = Field(default="development", alias="APP_ENV")
    port: int = Field(default=8000, alias="PORT")

    # Slack
    slack_bot_token: str = Field(alias="SLACK_BOT_TOKEN")
    slack_signing_secret: str = Field(alias="SLACK_SIGNING_SECRET")
    slack_app_token: Optional[str] = Field(default=None, alias="SLACK_APP_TOKEN")

    # Anthropic
    anthropic_api_key: str = Field(alias="ANTHROPIC_API_KEY")

    # Google
    google_client_id: Optional[str] = Field(default=None, alias="GOOGLE_CLIENT_ID")
    google_client_secret: Optional[str] = Field(default=None, alias="GOOGLE_CLIENT_SECRET")
    google_redirect_uri: Optional[str] = Field(default=None, alias="GOOGLE_REDIRECT_URI")
    google_token_json: Optional[str] = Field(default=None, alias="GOOGLE_TOKEN_JSON")

    # Tavily
    tavily_api_key: Optional[str] = Field(default=None, alias="TAVILY_API_KEY")

    # Timezone
    timezone: str = Field(default="Asia/Tokyo", alias="TIMEZONE")

    # Slack defaults
    default_slack_channel: str = Field(default="#general", alias="DEFAULT_SLACK_CHANNEL")

    # Scheduler
    daily_report_time: str = Field(default="18:00", alias="DAILY_REPORT_TIME")

    class Config:
        env_file = ".env"
        populate_by_name = True

    @property
    def tz(self):
        return pytz.timezone(self.timezone)


settings = Settings()
