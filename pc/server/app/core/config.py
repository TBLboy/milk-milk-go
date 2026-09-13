from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


PROJECT_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    app_name: str = "milk-weigh-api"
    app_version: str = "0.1.0"
    data_dir: Path = PROJECT_ROOT / "data"
    frontend_dir: Path = PROJECT_ROOT / "dist"
    database_filename: str = "milk_weigh.sqlite3"
    api_prefix: str = "/api/v1"
    token_secret: str | None = None
    admin_recovery_secret_hash: str | None = None
    admin_recovery_max_attempts: int = 5
    admin_recovery_lockout_minutes: int = 15
    bug_report_recipient: str = "1218740205@qq.com"
    smtp_host: str = "smtp.qq.com"
    smtp_port: int = 465
    smtp_use_ssl: bool = True
    smtp_username: str | None = None
    smtp_password: str | None = None

    model_config = SettingsConfigDict(env_prefix="MILK_", env_file=".env", extra="ignore")

    @property
    def database_url(self) -> str:
        return f"sqlite:///{(self.data_dir / self.database_filename).as_posix()}"


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    return settings
