from __future__ import annotations

import mimetypes
from functools import lru_cache
from pathlib import Path

from .config import settings


@lru_cache(maxsize=1)
def _client():
    if not settings.supabase_ready:
        raise RuntimeError("Supabase is not configured")
    from supabase import create_client
    return create_client(settings.supabase_url, settings.supabase_secret_key)


def storage_ready() -> bool:
    return settings.supabase_ready and (settings.database_provider or "").lower() == "supabase"


def persist_image(local_path: str | None, prefix: str, side: str) -> str | None:
    """Move a scan image from Render's temporary filesystem to Supabase Storage.

    Returns a stable sb:// reference. SQLite/dev mode simply keeps the local path.
    """
    if not local_path:
        return None
    if not storage_ready():
        return local_path
    path = Path(local_path)
    ext = path.suffix.lower() or ".jpg"
    object_path = f"scans/{prefix}/{side}{ext}"
    content_type = mimetypes.guess_type(path.name)[0] or "image/jpeg"
    with path.open("rb") as fh:
        _client().storage.from_(settings.supabase_bucket).upload(
            path=object_path,
            file=fh,
            file_options={"content-type": content_type, "upsert": "false"},
        )
    return f"sb://{settings.supabase_bucket}/{object_path}"


def signed_url(ref: str | None, expires_in: int = 3600) -> str | None:
    if not ref or not ref.startswith("sb://"):
        return None
    _, rest = ref.split("sb://", 1)
    bucket, object_path = rest.split("/", 1)
    result = _client().storage.from_(bucket).create_signed_url(object_path, expires_in)
    if isinstance(result, dict):
        return result.get("signedURL") or result.get("signedUrl")
    return getattr(result, "signed_url", None)
