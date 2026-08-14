import os
from dataclasses import dataclass
from urllib.parse import urlparse


def _clean_env(name: str, default: str | None = None) -> str | None:
    value = os.getenv(name, default)
    if value is None:
        return None
    # Render values occasionally get pasted with whitespace or surrounding quotes.
    value = value.strip().strip('"').strip("'").strip()
    return value or None


def _normalize_supabase_url(value: str | None) -> str | None:
    if not value:
        return None
    value = value.strip().strip('"').strip("'").strip()
    if not value:
        return None
    if not value.startswith(("http://", "https://")):
        value = "https://" + value
    parsed = urlparse(value)
    if not parsed.hostname:
        return value.rstrip("/")
    # The Supabase Python client expects the project base URL only.
    return f"{parsed.scheme or 'https'}://{parsed.hostname}".rstrip("/")


@dataclass(frozen=True)
class Settings:
    app_env: str = _clean_env("APP_ENV", "development") or "development"
    database_provider: str = (_clean_env("DATABASE_PROVIDER", "sqlite") or "sqlite").lower()
    database_path: str = _clean_env("DATABASE_PATH", _clean_env("DB_PATH", "data/sportscards.db")) or "data/sportscards.db"
    upload_dir: str = _clean_env("UPLOAD_DIR", "data/uploads") or "data/uploads"
    price_provider: str = _clean_env("PRICE_PROVIDER", "manual") or "manual"
    min_reliable_comps: int = int(_clean_env("MIN_RELIABLE_COMPS", "3") or "3")
    recognition_provider: str = _clean_env("RECOGNITION_PROVIDER", "safe") or "safe"
    openai_api_key: str | None = _clean_env("OPENAI_API_KEY")
    openai_vision_model: str = _clean_env("OPENAI_VISION_MODEL", "gpt-5.6-terra") or "gpt-5.6-terra"

    # Persistent collection/storage. Keep these server-side only.
    supabase_url: str | None = _normalize_supabase_url(_clean_env("SUPABASE_URL"))
    supabase_secret_key: str | None = _clean_env("SUPABASE_SECRET_KEY") or _clean_env("SUPABASE_SERVICE_ROLE_KEY")
    supabase_bucket: str = _clean_env("SUPABASE_BUCKET", "card-images") or "card-images"
    # Optional native Postgres connection string. On IPv4-only hosts, use
    # Supabase Supavisor Session pooler rather than the direct IPv6 endpoint.
    supabase_database_url: str | None = _clean_env("SUPABASE_DATABASE_URL")

    @property
    def supabase_ready(self) -> bool:
        return bool(self.supabase_url and self.supabase_secret_key)

    @property
    def supabase_host(self) -> str | None:
        if not self.supabase_url:
            return None
        return urlparse(self.supabase_url).hostname

settings = Settings()
