from __future__ import annotations

import mimetypes
import socket
from functools import lru_cache
from pathlib import Path

from .config import settings


@lru_cache(maxsize=1)
def _client():
    if not settings.supabase_ready:
        raise RuntimeError("Supabase is not configured")
    from supabase import create_client
    return create_client(settings.supabase_url, settings.supabase_secret_key)


def storage_configured() -> bool:
    return bool(settings.supabase_ready and (settings.database_provider or "").lower() == "supabase")


def storage_ready() -> bool:
    # Configuration readiness only; persistence-check performs the live test.
    return storage_configured()


def storage_diagnostics() -> dict:
    out = {
        "configured": storage_configured(),
        "bucket": settings.supabase_bucket if settings.supabase_ready else None,
        "host": settings.supabase_host,
        "dns_ok": False,
        "bucket_exists": False,
        "error": None,
    }
    if not storage_configured():
        out["error"] = "Supabase Storage ist nicht vollständig konfiguriert."
        return out
    try:
        socket.getaddrinfo(settings.supabase_host, 443, type=socket.SOCK_STREAM)
        out["dns_ok"] = True
    except Exception as exc:
        out["error"] = f"DNS-Auflösung fehlgeschlagen: {type(exc).__name__}: {exc}"
        return out
    try:
        buckets = _client().storage.list_buckets() or []
        names = []
        for b in buckets:
            if isinstance(b, dict):
                names.append(b.get("name") or b.get("id"))
            else:
                names.append(getattr(b, "name", None) or getattr(b, "id", None))
        out["bucket_exists"] = settings.supabase_bucket in names
        if not out["bucket_exists"]:
            out["error"] = f"Storage-Bucket '{settings.supabase_bucket}' wurde nicht gefunden."
    except Exception as exc:
        out["error"] = f"Storage-Abfrage fehlgeschlagen: {type(exc).__name__}: {exc}"
    return out


def persist_image(local_path: str | None, prefix: str, side: str) -> str | None:
    """Persist a scan image when Supabase is reachable.

    During diagnostics, a failed cloud upload no longer takes down the scanner;
    the local temporary path is returned instead and readiness remains false.
    """
    if not local_path:
        return None
    if not storage_configured():
        return local_path
    path = Path(local_path)
    ext = path.suffix.lower() or ".jpg"
    object_path = f"scans/{prefix}/{side}{ext}"
    content_type = mimetypes.guess_type(path.name)[0] or "image/jpeg"
    try:
        with path.open("rb") as fh:
            _client().storage.from_(settings.supabase_bucket).upload(
                path=object_path,
                file=fh,
                file_options={"content-type": content_type, "upsert": "false"},
            )
        return f"sb://{settings.supabase_bucket}/{object_path}"
    except Exception:
        # Keep scanner usable while connection diagnostics are being fixed.
        return local_path


def signed_url(ref: str | None, expires_in: int = 3600) -> str | None:
    if not ref or not ref.startswith("sb://"):
        return None
    _, rest = ref.split("sb://", 1)
    bucket, object_path = rest.split("/", 1)
    try:
        result = _client().storage.from_(bucket).create_signed_url(object_path, expires_in)
    except Exception:
        return None
    if isinstance(result, dict):
        return result.get("signedURL") or result.get("signedUrl")
    return getattr(result, "signed_url", None)
