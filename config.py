import os
from dataclasses import dataclass

@dataclass(frozen=True)
class Settings:
    app_env: str = os.getenv("APP_ENV", "development")
    database_provider: str = os.getenv("DATABASE_PROVIDER", "sqlite")
    database_path: str = os.getenv("DATABASE_PATH", os.getenv("DB_PATH", "data/sportscards.db"))
    upload_dir: str = os.getenv("UPLOAD_DIR", "data/uploads")
    price_provider: str = os.getenv("PRICE_PROVIDER", "manual")
    min_reliable_comps: int = int(os.getenv("MIN_RELIABLE_COMPS", "3"))
    recognition_provider: str = os.getenv("RECOGNITION_PROVIDER", "safe")
    openai_api_key: str | None = os.getenv("OPENAI_API_KEY")
    openai_vision_model: str = os.getenv("OPENAI_VISION_MODEL", "gpt-5.6-terra")

    # Persistent collection/storage (V0.14). Keep these server-side only.
    supabase_url: str | None = os.getenv("SUPABASE_URL")
    supabase_secret_key: str | None = os.getenv("SUPABASE_SECRET_KEY") or os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    supabase_bucket: str = os.getenv("SUPABASE_BUCKET", "card-images")

    @property
    def supabase_ready(self) -> bool:
        return bool(self.supabase_url and self.supabase_secret_key)

settings = Settings()
