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
    openai_vision_model: str = os.getenv("OPENAI_VISION_MODEL", "gpt-5.6")
    supabase_url: str | None = os.getenv("SUPABASE_URL")
    supabase_anon_key: str | None = os.getenv("SUPABASE_ANON_KEY")

settings = Settings()
