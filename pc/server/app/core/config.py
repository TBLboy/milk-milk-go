from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


PROJECT_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    app_name: str = "milk-weigh-api"
    app_version: str = "0.1.0"
    data_dir: Path = PROJECT_ROOT / "data"
    database_filename: str = "milk_weigh.sqlite3"
    api_prefix: str = "/api/v1"

    model_config = SettingsConfigDict(env_prefix="MILK_", env_file=".env", extra="ignore")

    @property
    def database_url(self) -> str:
        return f"sqlite:///{(self.data_dir / self.database_filename).as_posix()}"


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    return settings
