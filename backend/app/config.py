import json
import ssl
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Any
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from dotenv import load_dotenv
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

_BACKEND_ROOT = Path(__file__).resolve().parents[1]
_ENV_FILE = _BACKEND_ROOT / ".env"
_ENV_LOCAL_FILE = _BACKEND_ROOT / ".env.local"
# Legacy fallback when .env still lives at repo root
_LEGACY_ENV_FILE = _BACKEND_ROOT.parent / ".env"
if not _ENV_FILE.exists() and _LEGACY_ENV_FILE.exists():
    _ENV_FILE = _LEGACY_ENV_FILE

load_dotenv(_ENV_FILE)
if _ENV_LOCAL_FILE.exists():
    # Local overrides (gitignored); e.g. SYNC_AGENT_PROFILES_ON_STARTUP=true
    load_dotenv(_ENV_LOCAL_FILE, override=True)


def _strip_inline_comment(value: str) -> str:
    """Remove trailing inline comments from .env values (e.g. 'gpt-4o-mini   # note')."""
    if "#" not in value:
        return value.strip()
    return value.split("#", 1)[0].strip()


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(_ENV_FILE),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Primary chat model (Azure OpenAI)
    azure_api_key: str = Field(validation_alias="AZURE_API_KEY")
    azure_openai_base_url: str = Field(validation_alias="AZURE_OPENAI_BASE_URL")
    azure_openai_api_version: str = Field(validation_alias="AZURE_OPENAI_API_VERSION")
    azure_openai_files_api_version: str = Field(
        default="preview",
        validation_alias="AZURE_OPENAI_FILES_API_VERSION",
    )
    azure_openai_deployment: str = Field(validation_alias="AZURE_OPENAI_DEPLOYMENT")

    # Platform utility model (title, compaction)
    utility_model_api_key: str | None = Field(default=None, validation_alias="UTILITY_MODEL_API_KEY")
    utility_model_base_url: str | None = Field(default=None, validation_alias="UTILITY_MODEL_BASE_URL")
    utility_model_api_version: str | None = Field(default=None, validation_alias="UTILITY_MODEL_API_VERSION")
    utility_model_deployment: str | None = Field(default=None, validation_alias="UTILITY_MODEL_DEPLOYMENT")

    # Claude (Phase 1c)
    claude_azure_api_key: str | None = Field(default=None, validation_alias="CLAUDE_AZURE_API_KEY")
    claude_azure_foundry_endpoint: str | None = Field(
        default=None, validation_alias="CLAUDE_AZURE_FOUNDRY_ENDPOINT"
    )
    claude_azure_foundry_model: str | None = Field(
        default=None, validation_alias="CLAUDE_AZURE_FOUNDRY_MODEL"
    )
    claude_enable_thinking: bool = Field(default=False, validation_alias="CLAUDE_ENABLE_THINKING")

    database_url: str = Field(validation_alias="DATABASE_URL")
    redis_url: str = Field(validation_alias="REDIS_URL")
    yl_database_url: str | None = Field(default=None, validation_alias="YL_DATABASE_URL")

    fulfillment_api_base_url: str | None = Field(
        default="https://yl-backend.evolving.team/api/v1",
        validation_alias="FULFILLMENT_API_BASE_URL",
    )
    fulfillment_api_key: str | None = Field(default=None, validation_alias="FULFILLMENT_API_KEY")

    # Fernet key for encrypting MCP credentials at rest in the database
    mcp_secrets_key: str | None = Field(default=None, validation_alias="MCP_SECRETS_KEY")

    # Chat attachments (platform-wide, all agents)
    attachment_max_files_per_message: int = Field(
        default=5, validation_alias="ATTACHMENT_MAX_FILES_PER_MESSAGE"
    )
    attachment_max_bytes_per_file: int = Field(
        default=50 * 1024 * 1024, validation_alias="ATTACHMENT_MAX_BYTES_PER_FILE"
    )
    attachment_max_total_bytes_per_message: int = Field(
        default=50 * 1024 * 1024, validation_alias="ATTACHMENT_MAX_TOTAL_BYTES_PER_MESSAGE"
    )

    # Diagram rendering (agents/napkin-architect)
    plantuml_renderer: str = Field(default="kroki", validation_alias="PLANTUML_RENDERER")
    kroki_url: str = Field(default="https://kroki.io", validation_alias="KROKI_URL")
    plantuml_jar_path: str = Field(
        default="tools/plantuml.jar",
        validation_alias="PLANTUML_JAR_PATH",
    )
    plantuml_render_timeout_seconds: float = Field(
        default=30.0,
        validation_alias="PLANTUML_RENDER_TIMEOUT_SECONDS",
    )

    # Artifact persistence — local disk or Vercel Blob (required on Vercel serverless)
    artifact_storage: str = Field(default="auto", validation_alias="ARTIFACT_STORAGE")
    blob_read_write_token: str | None = Field(
        default=None, validation_alias="BLOB_READ_WRITE_TOKEN"
    )
    blob_store_id: str | None = Field(default=None, validation_alias="BLOB_STORE_ID")
    blob_access: str = Field(default="private", validation_alias="BLOB_ACCESS")

    # Agent profile sync — off by default; run scripts/sync_agent_profiles.py after YAML changes
    sync_agent_profiles_on_startup: bool = Field(
        default=False,
        validation_alias="SYNC_AGENT_PROFILES_ON_STARTUP",
    )

    # Sandbox (agents/slide-studio) — E2B default; local skips Slidev build
    sandbox_provider: str = Field(default="e2b", validation_alias="SANDBOX_PROVIDER")
    e2b_api_key: str | None = Field(default=None, validation_alias="E2B_API_KEY")
    e2b_slidev_template: str | None = Field(default=None, validation_alias="E2B_SLIDEV_TEMPLATE")
    sandbox_timeout_seconds: float = Field(default=180.0, validation_alias="SANDBOX_TIMEOUT_SECONDS")
    sandbox_slidev_export_pdf: bool = Field(default=False, validation_alias="SANDBOX_SLIDEV_EXPORT_PDF")
    sandbox_reuse_session: bool = Field(default=True, validation_alias="SANDBOX_REUSE_SESSION")
    sandbox_slidev_cache: bool = Field(default=True, validation_alias="SANDBOX_SLIDEV_CACHE")
    sandbox_async_build: bool = Field(default=False, validation_alias="SANDBOX_ASYNC_BUILD")

    app_name: str = "agent-platform"
    debug: bool = False
    cors_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["http://localhost:5173", "http://localhost:3000"],
        validation_alias="CORS_ORIGINS",
    )

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: object) -> object:
        if isinstance(value, str):
            stripped = value.strip()
            if stripped.startswith("["):
                return json.loads(stripped)
            return [part.strip() for part in value.split(",") if part.strip()]
        return value

    auth_disabled: bool = Field(default=False, validation_alias="AUTH_DISABLED")
    auth_cookie_name: str = Field(default="ap_session", validation_alias="AUTH_COOKIE_NAME")
    auth_cookie_secure: bool = Field(default=False, validation_alias="AUTH_COOKIE_SECURE")
    auth_cookie_samesite: str = Field(default="lax", validation_alias="AUTH_COOKIE_SAMESITE")
    auth_session_ttl_hours: int = Field(default=168, validation_alias="AUTH_SESSION_TTL_HOURS")

    @field_validator("auth_cookie_samesite", mode="before")
    @classmethod
    def normalize_samesite(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip().lower()
        return value

    @property
    def auth_session_ttl_seconds(self) -> int:
        return max(1, self.auth_session_ttl_hours) * 3600

    @field_validator(
        "azure_openai_deployment",
        "utility_model_deployment",
        "redis_url",
        mode="before",
    )
    @classmethod
    def strip_env_value(cls, value: object) -> object:
        if isinstance(value, str):
            return _strip_inline_comment(value).strip('"').strip("'")
        return value

    @property
    def async_database_url(self) -> str:
        url, _ = self._async_database_url_parts()
        return url

    @property
    def async_database_connect_args(self) -> dict[str, Any]:
        _, connect_args = self._async_database_url_parts()
        return connect_args

    def _async_database_url_parts(self) -> tuple[str, dict[str, Any]]:
        parsed = urlparse(self.database_url)
        scheme = parsed.scheme
        if scheme in ("postgresql", "postgres"):
            scheme = "postgresql+asyncpg"

        connect_args: dict[str, Any] = {"timeout": 15, "command_timeout": 45}
        query: list[tuple[str, str]] = []
        for key, value in parse_qsl(parsed.query, keep_blank_values=True):
            if key == "channel_binding":
                continue
            if key == "sslmode":
                if value in ("require", "verify-ca", "verify-full"):
                    connect_args["ssl"] = ssl.create_default_context()
                continue
            query.append((key, value))

        rebuilt = parsed._replace(scheme=scheme, query=urlencode(query))
        return urlunparse(rebuilt), connect_args

    def utility_api_key(self) -> str:
        return self.utility_model_api_key or self.azure_api_key

    def utility_base_url(self) -> str:
        return self.utility_model_base_url or self.azure_openai_base_url

    def utility_api_version(self) -> str:
        return self.utility_model_api_version or self.azure_openai_api_version

    def utility_deployment(self) -> str:
        return self.utility_model_deployment or self.azure_openai_deployment


@lru_cache
def get_settings() -> Settings:
    return Settings()
