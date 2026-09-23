from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    job_store: Literal["memory", "none", "postgres"] = Field(default="memory", alias="JOB_STORE")
    database_url: str | None = Field(default=None, alias="DATABASE_URL")

    parse_pipeline_api_keys: str = Field(
        default="test:test_dev_key",
        alias="PARSE_PIPELINE_API_KEYS",
    )

    document_mind_access_key_id: str | None = Field(default=None, alias="DOCUMENT_MIND_ACCESS_KEY_ID")
    document_mind_access_key_secret: str | None = Field(default=None, alias="DOCUMENT_MIND_ACCESS_KEY_SECRET")
    document_mind_endpoint: str = Field(
        default="docmind-api.cn-hangzhou.aliyuncs.com",
        alias="DOCUMENT_MIND_ENDPOINT",
    )
    document_mind_llm_enhancement: bool = Field(default=True, alias="DOCUMENT_MIND_LLM_ENHANCEMENT")
    document_mind_enhancement_mode: str = Field(default="VLM", alias="DOCUMENT_MIND_ENHANCEMENT_MODE")
    document_mind_poll_interval_sec: float = Field(default=5.0, alias="DOCUMENT_MIND_POLL_INTERVAL_SEC")
    document_mind_layout_step_size: int = Field(default=50, alias="DOCUMENT_MIND_LAYOUT_STEP_SIZE")

    host: str = Field(default="0.0.0.0", alias="HOST")
    port: int = Field(default=8091, alias="PORT")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    def api_key_map(self) -> dict[str, str]:
        result: dict[str, str] = {}
        for part in self.parse_pipeline_api_keys.split(","):
            part = part.strip()
            if not part or ":" not in part:
                continue
            caller_id, key = part.split(":", 1)
            result[key.strip()] = caller_id.strip()
        return result

    @property
    def document_mind_configured(self) -> bool:
        return bool(self.document_mind_access_key_id and self.document_mind_access_key_secret)


@lru_cache
def get_settings() -> Settings:
    return Settings()
