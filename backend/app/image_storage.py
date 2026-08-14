from __future__ import annotations

import mimetypes
import socket
from functools import lru_cache
from pathlib import Path
from urllib.parse import urlparse

from .config import settings


@lru_cache(maxsize=1)
def _rest_client():
    if not settings.supabase_ready:
        raise RuntimeError("Supabase REST Storage is not configured")
    from supabase import create_client
    return create_client(settings.supabase_url, settings.supabase_secret_key)


@lru_cache(maxsize=1)
def _s3_client():
    if not settings.s3_ready:
        raise RuntimeError("Supabase S3 Storage is not configured")
    import boto3
    from botocore.config import Config
    return boto3.client(
        "s3",
        endpoint_url=settings.s3_endpoint,
        region_name=settings.s3_region,
        aws_access_key_id=settings.s3_access_key_id,
        aws_secret_access_key=settings.s3_secret_access_key,
        config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
    )


def storage_configured() -> bool:
    # Prefer S3 because it uses a dedicated Storage endpoint and avoids the
    # project REST hostname DNS issue observed on Render.
    return settings.s3_ready or settings.supabase_ready


def storage_ready() -> bool:
    # Configuration readiness only. Live reachability is exposed by diagnostics.
    return storage_configured()


def _dns(host: str | None, port: int = 443) -> tuple[bool, str | None]:
    if not host:
        return False, "Host fehlt."
    try:
        socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
        return True, None
    except Exception as exc:
        return False, f"DNS-Auflösung fehlgeschlagen: {type(exc).__name__}: {exc}"


def storage_diagnostics() -> dict:
    if settings.s3_ready:
        host = urlparse(settings.s3_endpoint or "").hostname
        dns_ok, dns_error = _dns(host)
        out = {
            "provider": "supabase-s3",
            "configured": True,
            "bucket": settings.supabase_bucket,
            "host": host,
            "endpoint": settings.s3_endpoint,
            "region": settings.s3_region,
            "dns_ok": dns_ok,
            "bucket_exists": False,
            "error": dns_error,
        }
        if not dns_ok:
            return out
        try:
            _s3_client().head_bucket(Bucket=settings.supabase_bucket)
            out["bucket_exists"] = True
            out["error"] = None
        except Exception as exc:
            out["error"] = f"S3-Bucket-Abfrage fehlgeschlagen: {type(exc).__name__}: {exc}"
        return out

    # Legacy REST fallback kept for compatibility while S3 credentials are not set.
    out = {
        "provider": "supabase-rest" if settings.supabase_ready else "local",
        "configured": bool(settings.supabase_ready),
        "bucket": settings.supabase_bucket if settings.supabase_ready else None,
        "host": settings.supabase_host,
        "endpoint": settings.supabase_url,
        "region": None,
        "dns_ok": False,
        "bucket_exists": False,
        "error": None,
    }
    if not settings.supabase_ready:
        out["error"] = "Persistent Image Storage ist nicht konfiguriert."
        return out
    dns_ok, dns_error = _dns(settings.supabase_host)
    out["dns_ok"] = dns_ok
    out["error"] = dns_error
    if not dns_ok:
        return out
    try:
        buckets = _rest_client().storage.list_buckets() or []
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
    """Persist one scan image, preferring Supabase's S3-compatible API.

    Returns an s3:// (or legacy sb://) reference. If cloud storage is not yet
    reachable the scanner remains usable and the local temporary path is kept.
    """
    if not local_path:
        return None
    path = Path(local_path)
    if not path.exists():
        return local_path
    ext = path.suffix.lower() or ".jpg"
    object_path = f"scans/{prefix}/{side}{ext}"
    content_type = mimetypes.guess_type(path.name)[0] or "image/jpeg"

    if settings.s3_ready:
        try:
            _s3_client().upload_file(
                str(path),
                settings.supabase_bucket,
                object_path,
                ExtraArgs={"ContentType": content_type},
            )
            return f"s3://{settings.supabase_bucket}/{object_path}"
        except Exception:
            return local_path

    if settings.supabase_ready:
        try:
            with path.open("rb") as fh:
                _rest_client().storage.from_(settings.supabase_bucket).upload(
                    path=object_path,
                    file=fh,
                    file_options={"content-type": content_type, "upsert": "false"},
                )
            return f"sb://{settings.supabase_bucket}/{object_path}"
        except Exception:
            return local_path

    return local_path


def signed_url(ref: str | None, expires_in: int = 3600) -> str | None:
    if not ref:
        return None

    # S3 can also serve legacy sb:// references because both protocols address
    # the same Supabase Storage objects.
    if ref.startswith(("s3://", "sb://")):
        _, rest = ref.split("://", 1)
        bucket, object_path = rest.split("/", 1)
        if settings.s3_ready:
            try:
                return _s3_client().generate_presigned_url(
                    "get_object",
                    Params={"Bucket": bucket, "Key": object_path},
                    ExpiresIn=expires_in,
                )
            except Exception:
                return None
        if ref.startswith("sb://") and settings.supabase_ready:
            try:
                result = _rest_client().storage.from_(bucket).create_signed_url(object_path, expires_in)
            except Exception:
                return None
            if isinstance(result, dict):
                return result.get("signedURL") or result.get("signedUrl")
            return getattr(result, "signed_url", None)
    return None
