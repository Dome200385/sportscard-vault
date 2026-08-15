from __future__ import annotations

import mimetypes
import socket
from datetime import datetime, timezone
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
    """Create the S3 client exactly as Supabase documents it.

    Supabase's hosted S3 API is compatible with standard AWS SDK clients when
    the project endpoint, project region and generated S3 key pair are used
    together with path-style addressing. V0.15.9 deliberately lets botocore
    own request construction and Signature V4 instead of hand-building URLs.
    """
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
            # Supabase requires path-style addressing. Leave payload signing at
            # botocore's default; forcing it can make some S3-compatible
            # gateways reject otherwise valid requests.
            s3={"addressing_style": "path"},
            retries={"max_attempts": 2, "mode": "standard"},
            connect_timeout=10,
            read_timeout=20,
            # Avoid optional SDK checksum behavior that some S3-compatible
            # gateways do not implement for otherwise-valid PutObject calls.
            request_checksum_calculation="when_required",
            response_checksum_validation="when_required",
        ),
    )


def storage_configured() -> bool:
    return settings.s3_ready or settings.supabase_ready


def storage_ready() -> bool:
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
    """Return safe botocore diagnostics without exposing credentials."""
    out: dict = {}
    try:
        response = getattr(exc, "response", {}) or {}
        err = response.get("Error", {}) or {}
        meta = response.get("ResponseMetadata", {}) or {}
        out.update({
            "s3_error_code": err.get("Code"),
            "s3_error_message": err.get("Message"),
            "s3_http_status": meta.get("HTTPStatusCode"),
            "s3_request_id": meta.get("RequestId"),
            "s3_host_id": meta.get("HostId"),
        })
        # Botocore sometimes exposes the raw body in Error fields for
        # non-AWS gateways. Surface only a short, non-secret diagnostic.
        body = err.get("Body") or response.get("Body")
        if isinstance(body, (str, bytes)):
            text = body.decode("utf-8", "replace") if isinstance(body, bytes) else body
            out["s3_response_body"] = text[:800]
    except Exception:
        pass
    return out


def _write_probe(client) -> dict:
    """Write -> HEAD -> delete a tiny object in the real configured bucket."""
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    key = f"_health/render-probe-{stamp}.txt"
    payload = b"sportscard-vault-s3-probe"
    result = {
        "write_probe_key": key,
        "write_probe_put_ok": False,
        "write_probe_head_ok": False,
        "write_probe_delete_ok": False,
    }
    try:
        put = client.put_object(
            Bucket=settings.supabase_bucket,
            Key=key,
            Body=payload,
            ContentType="text/plain",
        )
        result["write_probe_put_status"] = (put.get("ResponseMetadata") or {}).get("HTTPStatusCode")
        result["write_probe_put_ok"] = result["write_probe_put_status"] in {200, 201, 204}
        if not result["write_probe_put_ok"]:
            result["write_probe_error_stage"] = "put"
            return result

        head = client.head_object(Bucket=settings.supabase_bucket, Key=key)
        result["write_probe_head_status"] = (head.get("ResponseMetadata") or {}).get("HTTPStatusCode")
        result["write_probe_head_ok"] = result["write_probe_head_status"] in {200, 204}
        if not result["write_probe_head_ok"]:
            result["write_probe_error_stage"] = "head"
        return result
    except Exception as exc:
        result["write_probe_error_stage"] = result.get("write_probe_error_stage") or (
            "head" if result.get("write_probe_put_ok") else "put"
        )
        result["write_probe_exception"] = f"{type(exc).__name__}: {exc}"
        result.update(_client_error_details(exc))
        return result
    finally:
        try:
            deleted = client.delete_object(Bucket=settings.supabase_bucket, Key=key)
            result["write_probe_delete_status"] = (deleted.get("ResponseMetadata") or {}).get("HTTPStatusCode")
            result["write_probe_delete_ok"] = result["write_probe_delete_status"] in {200, 202, 204}
        except Exception as exc:
            result["write_probe_delete_error"] = f"{type(exc).__name__}: {exc}"
            for k, v in _client_error_details(exc).items():
                result.setdefault("write_probe_delete_" + k, v)


def _safe_presigned_path(client) -> str | None:
    """Show the exact URL path boto3 builds, without credentials/signature."""
    try:
        url = client.generate_presigned_url(
            "list_objects_v2",
            Params={"Bucket": settings.supabase_bucket, "MaxKeys": 1},
            ExpiresIn=60,
        )
        parsed = urlparse(url)
        return f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
    except Exception:
        return None


def _credential_shape() -> dict:
    """Non-secret credential diagnostics; never expose the credential values."""
    access = (settings.s3_access_key_id or "").strip()
    secret = (settings.s3_secret_access_key or "").strip()
    return {
        "access_key_length": len(access),
        "secret_key_length": len(secret),
        "access_key_has_outer_whitespace": bool(settings.s3_access_key_id and settings.s3_access_key_id != access),
        "secret_key_has_outer_whitespace": bool(settings.s3_secret_access_key and settings.s3_secret_access_key != secret),
    }




def _client_for_endpoint(endpoint: str):
    """Create a diagnostic boto3 client for one explicit Supabase S3 endpoint."""
    import boto3
    from botocore.config import Config

    return boto3.client(
        "s3",
        endpoint_url=endpoint,
        region_name=settings.s3_region,
        aws_access_key_id=settings.s3_access_key_id,
        aws_secret_access_key=settings.s3_secret_access_key,
        config=Config(
            signature_version="s3v4",
            s3={"addressing_style": "path"},
            retries={"max_attempts": 1, "mode": "standard"},
            connect_timeout=6,
            read_timeout=10,
            request_checksum_calculation="when_required",
            response_checksum_validation="when_required",
        ),
    )


def _endpoint_trial(label: str, endpoint: str) -> dict:
    """Read-only comparison of an S3 endpoint. Never exposes credentials."""
    parsed = urlparse(endpoint)
    host = parsed.hostname
    dns_ok, dns_error = _dns(host)
    result = {
        "label": label,
        "endpoint": endpoint,
        "host": host,
        "dns_ok": dns_ok,
        "dns_error": dns_error,
        "head_bucket_ok": False,
        "list_objects_ok": False,
    }
    if not dns_ok:
        return result
    try:
        client = _client_for_endpoint(endpoint)
        result["request_url"] = _safe_presigned_path(client)
        try:
            head = client.head_bucket(Bucket=settings.supabase_bucket)
            result["head_bucket_status"] = (head.get("ResponseMetadata") or {}).get("HTTPStatusCode")
            result["head_bucket_ok"] = result["head_bucket_status"] in {200, 204}
        except Exception as exc:
            result["head_bucket_exception"] = f"{type(exc).__name__}: {exc}"
            for k, v in _client_error_details(exc).items():
                result["head_bucket_" + k] = v
        try:
            listing = client.list_objects_v2(Bucket=settings.supabase_bucket, MaxKeys=1)
            result["list_objects_status"] = (listing.get("ResponseMetadata") or {}).get("HTTPStatusCode")
            result["list_objects_ok"] = result["list_objects_status"] in {200, 204}
        except Exception as exc:
            result["list_objects_exception"] = f"{type(exc).__name__}: {exc}"
            for k, v in _client_error_details(exc).items():
                result["list_objects_" + k] = v
        result["usable"] = bool(result["head_bucket_ok"] or result["list_objects_ok"])
    except Exception as exc:
        result["client_exception"] = f"{type(exc).__name__}: {exc}"
    return result



def _rest_storage_split_trial() -> dict:
    """V0.15.12: compare Storage REST authentication with S3.

    Uses the direct Storage hostname so the probe does not depend on the
    project API hostname, which is not resolvable from the current Render
    environment. The probe is read-only and never exposes credentials.
    """
    ref = settings.supabase_project_ref
    secret = (settings.supabase_secret_key or "").strip()
    if not ref:
        return {"configured": False, "reason": "project_ref_missing"}
    if not secret:
        return {"configured": False, "reason": "supabase_secret_missing"}

    import httpx
    from urllib.parse import quote

    base = f"https://{ref}.storage.supabase.co"
    host = urlparse(base).hostname
    dns_ok, dns_error = _dns(host)
    result = {
        "configured": True,
        "base_url": base,
        "host": host,
        "dns_ok": dns_ok,
        "dns_error": dns_error,
        "key_kind": "opaque-secret" if secret.startswith("sb_secret_") else ("legacy-jwt" if secret.startswith("eyJ") else "other"),
        "key_length": len(secret),
        "bucket_get_ok": False,
        "object_list_ok": False,
    }
    if not dns_ok:
        return result

    # New sb_secret_* API keys belong in apikey. Legacy service_role JWTs are
    # also accepted as bearer credentials by Storage. Supplying both mirrors
    # the server-side SDK behavior while keeping the value out of diagnostics.
    headers = {
        "apikey": secret,
        "Authorization": f"Bearer {secret}",
        "User-Agent": "SportsCardVault/0.15.12 Render diagnostic",
    }
    bucket_q = quote(settings.supabase_bucket, safe="")
    bucket_url = f"{base}/storage/v1/bucket/{bucket_q}"
    list_url = f"{base}/storage/v1/object/list/{bucket_q}"
    result["bucket_url"] = bucket_url
    result["list_url"] = list_url

    try:
        with httpx.Client(timeout=12.0, follow_redirects=False) as client:
            try:
                r = client.get(bucket_url, headers=headers)
                result["bucket_get_status"] = r.status_code
                result["bucket_get_content_type"] = r.headers.get("content-type")
                result["bucket_get_request_id"] = r.headers.get("x-request-id") or r.headers.get("sb-request-id")
                result["bucket_get_body"] = (r.text or "")[:500]
                result["bucket_get_ok"] = 200 <= r.status_code < 300
            except Exception as exc:
                result["bucket_get_exception"] = f"{type(exc).__name__}: {exc}"

            try:
                r = client.post(
                    list_url,
                    headers={**headers, "Content-Type": "application/json"},
                    json={"limit": 1, "offset": 0, "prefix": ""},
                )
                result["object_list_status"] = r.status_code
                result["object_list_content_type"] = r.headers.get("content-type")
                result["object_list_request_id"] = r.headers.get("x-request-id") or r.headers.get("sb-request-id")
                result["object_list_body"] = (r.text or "")[:500]
                result["object_list_ok"] = 200 <= r.status_code < 300
            except Exception as exc:
                result["object_list_exception"] = f"{type(exc).__name__}: {exc}"
    except Exception as exc:
        result["client_exception"] = f"{type(exc).__name__}: {exc}"

    result["any_ok"] = bool(result.get("bucket_get_ok") or result.get("object_list_ok"))
    return result

def _postgres_image_fallback_status() -> dict:
    if not settings.supabase_database_url:
        return {"configured": False, "ready": False, "error": "SUPABASE_DATABASE_URL fehlt"}
    try:
        from .postgres_db import image_blob_ready
        ok, error = image_blob_ready()
        return {"configured": True, "ready": bool(ok), "error": error}
    except Exception as exc:
        return {"configured": True, "ready": False, "error": f"{type(exc).__name__}: {exc}"}


def storage_diagnostics() -> dict:
    if settings.s3_ready:
        host = urlparse(settings.s3_endpoint or "").hostname
        dns_ok, dns_error = _dns(host)
        out = {
            "provider": "supabase-s3",
            "sdk": "boto3",
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
            "project_ref": settings.supabase_project_ref,
            "error": dns_error,
        }
        # V0.15.11: compare both official Supabase S3 host forms without
        # changing the configured production endpoint. This isolates routing
        # from credentials and request signing.
        ref = settings.supabase_project_ref
        direct_endpoint = (settings.s3_endpoint or "").rstrip("/")
        project_endpoint = f"https://{ref}.supabase.co/storage/v1/s3" if ref else None
        trials = []
        if direct_endpoint:
            trials.append(_endpoint_trial("direct-storage-host", direct_endpoint))
        if project_endpoint and project_endpoint != direct_endpoint:
            trials.append(_endpoint_trial("project-host", project_endpoint))
        out["endpoint_trials"] = trials
        out["endpoint_trial_any_usable"] = any(t.get("usable") for t in trials)
        out["endpoint_trial_winner"] = next((t.get("label") for t in trials if t.get("usable")), None)

        # V0.15.12: independent Storage REST probe with the server secret.
        # This cleanly separates "Storage itself/auth works" from "S3
        # protocol/signing works" without changing production behavior.
        rest_trial = _rest_storage_split_trial()
        out["rest_split_trial"] = rest_trial
        out["rest_split_any_ok"] = bool(rest_trial.get("any_ok"))
        out["s3_split_any_ok"] = bool(out.get("endpoint_trial_any_usable"))

        # V0.15.13: durable fallback through the already-working Postgres
        # connection. This lets scans remain persistent even while Supabase
        # Storage routing returns "Project not specified" / HTTP 400.
        pg_image = _postgres_image_fallback_status()
        out["postgres_image_fallback_configured"] = pg_image.get("configured")
        out["postgres_image_fallback_ready"] = pg_image.get("ready")
        out["postgres_image_fallback_error"] = pg_image.get("error")

        if not dns_ok:
            if pg_image.get("ready"):
                out.update({
                    "provider": "postgres-image-fallback",
                    "sdk": "psycopg",
                    "bucket_exists": True,
                    "object_access_ok": True,
                    "bucket_probe_method": "postgres_image_blob_table",
                    "error": None,
                })
            return out

        client = _s3_client()
        out.update(_credential_shape())
        out["boto3_request_url"] = _safe_presigned_path(client)
        out["endpoint_path"] = urlparse(settings.s3_endpoint or "").path
        out["endpoint_path_ok"] = out["endpoint_path"].rstrip("/") == "/storage/v1/s3"

        # Probe the bucket itself first. This distinguishes bucket routing from
        # ListObjectsV2 query handling and gives Supabase a simpler signed request.
        try:
            head = client.head_bucket(Bucket=settings.supabase_bucket)
            out["head_bucket_status"] = (head.get("ResponseMetadata") or {}).get("HTTPStatusCode")
            out["head_bucket_ok"] = out["head_bucket_status"] in {200, 204}
            if out["head_bucket_ok"]:
                out["bucket_exists"] = True
        except Exception as exc:
            out["head_bucket_ok"] = False
            out["head_bucket_exception"] = f"{type(exc).__name__}: {exc}"
            for k, v in _client_error_details(exc).items():
                out["head_bucket_" + k] = v

        # Primary probe: official SDK + path-style addressing, matching the
        # Supabase S3 authentication documentation exactly.
        try:
            response = client.list_objects_v2(Bucket=settings.supabase_bucket, MaxKeys=1)
            out["bucket_probe_method"] = "boto3_list_objects_v2"
            out["list_objects_status"] = (response.get("ResponseMetadata") or {}).get("HTTPStatusCode")
            out["bucket_exists"] = True
            out["object_access_ok"] = True
            out["error"] = None
        except Exception as exc:
            out["bucket_probe_method"] = "boto3_list_objects_v2"
            out.update(_client_error_details(exc))
            out["error"] = f"Boto3 ListObjectsV2 fehlgeschlagen: {type(exc).__name__}: {exc}"

        # Regardless of listing, try the exact operation the scanner needs.
        probe = _write_probe(client)
        out.update(probe)
        if probe.get("write_probe_put_ok") and probe.get("write_probe_head_ok"):
            out["bucket_exists"] = True
            out["object_access_ok"] = True
            out["bucket_probe_method"] = "boto3_write_head_delete_probe"
            out["error"] = None
        elif out.get("postgres_image_fallback_ready"):
            out["provider"] = "postgres-image-fallback"
            out["sdk"] = "psycopg"
            out["bucket_exists"] = True
            out["object_access_ok"] = True
            out["bucket_probe_method"] = "postgres_image_blob_table"
            out["s3_error_preserved"] = out.get("error")
            out["error"] = None
        return out

    # Legacy REST fallback kept only until S3 credentials are available.
    out = {
        "provider": "supabase-rest" if settings.supabase_ready else "local",
        "sdk": "supabase-py" if settings.supabase_ready else None,
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
    """Persist one scan image, preferring Supabase S3."""
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
            with path.open("rb") as fh:
                _s3_client().put_object(
                    Bucket=settings.supabase_bucket,
                    Key=object_path,
                    Body=fh,
                    ContentType=content_type,
                )
            return f"s3://{settings.supabase_bucket}/{object_path}"
        except Exception:
            # Render currently reaches the Storage host but Supabase returns
            # HTTP 400/"Project not specified". Persist the image in the
            # already-working Postgres database instead of losing it on /tmp.
            if settings.supabase_database_url:
                try:
                    from .postgres_db import persist_image_blob
                    image_id = persist_image_blob(path.read_bytes(), content_type, path.name)
                    return f"pgimg://{image_id}"
                except Exception:
                    pass

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
            if settings.supabase_database_url:
                try:
                    from .postgres_db import persist_image_blob
                    image_id = persist_image_blob(path.read_bytes(), content_type, path.name)
                    return f"pgimg://{image_id}"
                except Exception:
                    pass
            return local_path

    if settings.supabase_database_url:
        try:
            from .postgres_db import persist_image_blob
            image_id = persist_image_blob(path.read_bytes(), content_type, path.name)
            return f"pgimg://{image_id}"
        except Exception:
            pass
    return local_path


def signed_url(ref: str | None, expires_in: int = 3600) -> str | None:
    if not ref:
        return None
    if ref.startswith("pgimg://"):
        image_id = ref.split("://", 1)[1]
        return f"/api/v1/images/{image_id}"
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
                if isinstance(result, dict):
                    return result.get("signedURL") or result.get("signedUrl")
                return getattr(result, "signed_url", None)
            except Exception:
                return None
    return None
