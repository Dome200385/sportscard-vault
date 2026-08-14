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
        config=Config(
            signature_version="s3v4",
            s3={"addressing_style": "path"},
            # Recent AWS SDKs may add optional checksum headers by default.
            # Supabase S3 implements the core PutObject API but not every
            # optional AWS checksum extension, so only calculate/validate
            # checksums when the protocol explicitly requires them.
            request_checksum_calculation="when_required",
            response_checksum_validation="when_required",
        ),
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


def _client_error_details(exc: Exception) -> dict:
    """Return safe S3 error diagnostics without leaking credentials."""
    try:
        response = getattr(exc, "response", {}) or {}
        err = response.get("Error", {}) or {}
        meta = response.get("ResponseMetadata", {}) or {}
        return {
            "s3_error_code": err.get("Code"),
            "s3_error_message": err.get("Message"),
            "s3_http_status": meta.get("HTTPStatusCode"),
            "s3_request_id": meta.get("RequestId"),
        }
    except Exception:
        return {}


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
            "object_access_ok": False,
            "bucket_probe_method": None,
            "access_key_configured": bool(settings.s3_access_key_id),
            "secret_key_configured": bool(settings.s3_secret_access_key),
            "endpoint_from_env": bool(settings.s3_endpoint_env),
            "region_from_env": bool(settings.s3_region_env),
            "error": dns_error,
        }
        if not dns_ok:
            return out

        client = _s3_client()
        # Supabase documents ListObjectsV2 as a supported S3 operation. Use it
        # as the primary readiness probe because it tests actual object access
        # to the configured bucket, which is exactly what card image storage
        # needs. HeadBucket is intentionally not the sole gate because some S3
        # compatible gateways return an unhelpful 400 for HEAD while object
        # operations work normally.
        try:
            client.list_objects_v2(Bucket=settings.supabase_bucket, MaxKeys=1)
            out["bucket_exists"] = True
            out["object_access_ok"] = True
            out["bucket_probe_method"] = "list_objects_v2"
            out["error"] = None
            return out
        except Exception as exc:
            out.update(_client_error_details(exc))
            first_error = f"ListObjectsV2 fehlgeschlagen: {type(exc).__name__}: {exc}"

        # Secondary diagnostic only: ListBuckets is also implemented by
        # Supabase and can distinguish an unknown bucket from an object-access
        # or request-signing problem. A positive ListBuckets result alone does
        # not mark image storage persistent; object access must work.
        try:
            result = client.list_buckets() or {}
            buckets = result.get("Buckets", []) if isinstance(result, dict) else []
            names = [b.get("Name") for b in buckets if isinstance(b, dict)]
            out["bucket_list_visible"] = settings.supabase_bucket in names
            if out["bucket_list_visible"]:
                out["bucket_exists"] = True
            out["bucket_probe_method"] = "list_objects_v2+list_buckets"
        except Exception as exc2:
            out["bucket_list_visible"] = False
            out["list_buckets_error"] = f"{type(exc2).__name__}: {exc2}"
            for k, v in _client_error_details(exc2).items():
                out.setdefault("list_buckets_" + k, v)

        out["error"] = first_error
        return out

    # Legacy REST fallback kept for compatibility while S3 credentials are not set.
    out = {
        "provider": "supabase-rest" if settings.supabase_ready else "local",
        "configured": bool(settings.supabase_ready),
        "s3_credentials_configured": settings.s3_credentials_ready,
        "s3_endpoint_candidate": settings.s3_endpoint,
        "s3_region_candidate": settings.s3_region,
        "s3_access_key_configured": bool(settings.s3_access_key_id),
        "s3_secret_key_configured": bool(settings.s3_secret_access_key),
        "bucket": settings.supabase_bucket if settings.supabase_ready else None,
        "host": settings.supabase_host,
        "endpoint": settings.supabase_url,
        "region": None,
        "dns_ok": False,
        "bucket_exists": False,
        "object_access_ok": False,
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
        out["object_access_ok"] = out["bucket_exists"]
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
            # Card scans are small images, so use one PutObject request rather
            # than boto3's managed upload/multipart machinery. PutObject is
            # explicitly supported by Supabase S3 and avoids optional AWS
            # multipart/checksum extensions that are unnecessary here.
            with path.open("rb") as fh:
                _s3_client().put_object(
                    Bucket=settings.supabase_bucket,
                    Key=object_path,
                    Body=fh,
                    ContentType=content_type,
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
