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


def _first_env(*names: str) -> str | None:
    for name in names:
        value = _clean_env(name)
        if value:
            return value
    return None


def _project_ref(supabase_url: str | None) -> str | None:
    if not supabase_url:
        return None
    host = urlparse(supabase_url).hostname or ""
    suffix = ".supabase.co"
    if host.endswith(suffix):
        ref = host[:-len(suffix)]
        if ref and "." not in ref:
            return ref
    return None


def _region_from_database_url(database_url: str | None) -> str | None:
    if not database_url:
        return None
    host = urlparse(database_url).hostname or ""
    # Supavisor hosts are typically aws-<n>-eu-west-3.pooler.supabase.com.
    parts = host.split(".")[0].split("-")
    for i, part in enumerate(parts):
        if part in {"eu", "us", "ap", "sa", "ca", "me", "af"} and i + 2 < len(parts):
            candidate = "-".join(parts[i:i+3])
            if parts[i+2].isdigit():
                return candidate
    return None


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

    # Live sold-market provider (V0.20.0). Server-side only.
    soldcomps_api_key: str | None = _clean_env("SOLDCOMPS_API_KEY")
    soldcomps_api_base: str = _clean_env("SOLDCOMPS_API_BASE", "https://api.sold-comps.com") or "https://api.sold-comps.com"
    soldcomps_ebay_site: str = _clean_env("SOLDCOMPS_EBAY_SITE", "ebay.com") or "ebay.com"
    soldcomps_days: int = int(_clean_env("SOLDCOMPS_DAYS", "90") or "90")
    soldcomps_count: int = int(_clean_env("SOLDCOMPS_COUNT", "120") or "120")
    soldcomps_timeout_seconds: float = float(_clean_env("SOLDCOMPS_TIMEOUT_SECONDS", "30") or "30")

    # Persistent collection/storage. Keep these server-side only.
    supabase_url: str | None = _normalize_supabase_url(_clean_env("SUPABASE_URL"))
    supabase_secret_key: str | None = _clean_env("SUPABASE_SECRET_KEY") or _clean_env("SUPABASE_SERVICE_ROLE_KEY")
    supabase_bucket: str = _clean_env("SUPABASE_BUCKET", "card-images") or "card-images"
    # Optional native Postgres connection string. On IPv4-only hosts, use
    # Supabase Supavisor Session pooler rather than the direct IPv6 endpoint.
    supabase_database_url: str | None = _clean_env("SUPABASE_DATABASE_URL")

    # Supabase Storage S3 compatibility (V0.15.6). Server-side secrets only.
    # Accept both our explicit names and common S3/AWS aliases so a dashboard
    # naming mismatch cannot silently disable persistent image storage.
    s3_endpoint_env: str | None = _first_env("SUPABASE_S3_ENDPOINT", "S3_ENDPOINT", "S3_ENDPOINT_URL", "S3FS_ENDPOINT_URL")
    s3_region_env: str | None = _first_env("SUPABASE_S3_REGION", "S3_REGION", "AWS_DEFAULT_REGION", "AWS_REGION", "S3FS_REGION")
    s3_access_key_id: str | None = _first_env("SUPABASE_S3_ACCESS_KEY_ID", "S3_ACCESS_KEY_ID", "AWS_ACCESS_KEY_ID", "S3FS_ACCESS_KEY_ID")
    s3_secret_access_key: str | None = _first_env("SUPABASE_S3_SECRET_ACCESS_KEY", "S3_SECRET_ACCESS_KEY", "AWS_SECRET_ACCESS_KEY", "S3FS_SECRET_ACCESS_KEY")

    @property
    def supabase_project_ref(self) -> str | None:
        return _project_ref(self.supabase_url)

    @property
    def s3_endpoint(self) -> str | None:
        if self.s3_endpoint_env:
            value = self.s3_endpoint_env.rstrip("/")
            # If the dashboard value is only the project base URL, turn it into
            # the actual S3 protocol endpoint.
            parsed = urlparse(value if value.startswith(("http://", "https://")) else "https://" + value)
            host = parsed.hostname or ""
            if host.endswith(".supabase.co") and "/storage/v1/s3" not in parsed.path:
                ref = host.split(".")[0]
                # Prefer Supabase's direct storage hostname; it avoids the project
                # REST hostname DNS issue observed on Render.
                return f"https://{ref}.storage.supabase.co/storage/v1/s3"
            return value
        if self.supabase_project_ref:
            return f"https://{self.supabase_project_ref}.storage.supabase.co/storage/v1/s3"
        return None

    @property
    def s3_region(self) -> str | None:
        return self.s3_region_env or _region_from_database_url(self.supabase_database_url)

    @property
    def s3_credentials_ready(self) -> bool:
        return bool(self.s3_access_key_id and self.s3_secret_access_key)

    @property
    def s3_ready(self) -> bool:
        return bool(self.s3_endpoint and self.s3_region and self.s3_credentials_ready and self.supabase_bucket)

    @property
    def supabase_ready(self) -> bool:
        return bool(self.supabase_url and self.supabase_secret_key)

    @property
    def supabase_host(self) -> str | None:
        if not self.supabase_url:
            return None
        return urlparse(self.supabase_url).hostname

settings = Settings()
