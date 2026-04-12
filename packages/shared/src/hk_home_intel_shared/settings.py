from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


REPO_ROOT = Path(__file__).resolve().parents[4]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="HHI_",
        extra="ignore",
    )

    app_name: str = Field(default="HK Home Intel")
    app_version: str = Field(default="0.1.0")
    environment: str = Field(default="development")

    api_host: str = Field(default="127.0.0.1")
    api_port: int = Field(default=8000)
    api_v1_prefix: str = Field(default="/api/v1")
    cors_allow_origins: str = Field(
        default="http://127.0.0.1:3000,http://localhost:3000"
    )

    database_url: str = Field(
        default=f"sqlite:///{(REPO_ROOT / 'data' / 'dev' / 'hk_home_intel.db').as_posix()}"
    )

    web_app_url: str = Field(default="http://127.0.0.1:3000")
    data_root: Path = Field(default=REPO_ROOT / "data")
    config_root: Path = Field(default=REPO_ROOT / "configs")
    http_trust_env: bool = Field(default=True)

    @property
    def cors_allow_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_allow_origins.split(",") if origin.strip()]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


def clear_settings_cache() -> None:
    get_settings.cache_clear()
