import csv
import io
import json
import shutil
import asyncio
import logging
import threading
from pathlib import Path
from uuid import uuid4
from datetime import datetime, timezone, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, FileResponse, Response
from PIL import Image, ImageOps
from .config import settings
from . import db
from .schemas import CardCreateRequest, ManualCompIn, ScanResponse, ConfirmScanRequest, AutoConfirmScanRequest, ValuationOut, CardIdentityIn, OwnedInstanceIn
from .pricing import Comp, calculate_valuation
from .recognition import analyze_images
from .catalog import rank_catalog
from .image_storage import persist_image, signed_url, storage_ready, storage_diagnostics
from . import postgres_probe
from .market_providers import (build_fingerprint, provider_status, score_candidate, soldcomps_search, normalize_soldcomps_results, SoldCompsError)

STATIC_INDEX = Path(__file__).resolve().parent.parent / "static" / "index.html"

logger = logging.getLogger("sportscard-vault")

app = FastAPI(title="SportsCard Vault API", version="0.22.6.9", description="Detailed sports-card collection API with editable scan review, correction learning data, transparent comp-based valuation, and an offline-first test UI.")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=False, allow_methods=["*"], allow_headers=["*"])

from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    # V0.15.2: never crash the whole service just because Supabase is
    # temporarily unreachable. The DB facade activates an explicit SQLite
    # diagnostic fallback and exposes the root cause via persistence-check.
    try:
        db.init_db()
    except Exception as exc:
        logger.exception("database initialization failed; activating diagnostic fallback")
        try:
            db.activate_sqlite_fallback(f"Startup DB error: {type(exc).__name__}: {exc}")
        except Exception:
            logger.exception("sqlite fallback initialization also failed")
    # V0.22.4.14: warm a missing legacy market cache in the background after deploy.
    # The service remains responsive while this one-time persisted-comp calculation runs.
    try:
        _ensure_collection_market_cache_warmup()
    except Exception:
        logger.exception("market cache warmup scheduling failed")
    yield

# Assign lifespan after app construction for compatibility with the existing scaffold.
app.router.lifespan_context = lifespan

@app.get("/health")
def health(): return {"status":"ok","version":"0.22.6.9","environment":settings.app_env,"recognition":settings.recognition_provider,"pricing_provider":settings.price_provider,"database_provider":settings.database_provider}


def _serve_test_ui():
    if STATIC_INDEX.exists():
        # V0.22.3: always serve the deployed backend/static dashboard and
        # prevent browsers/CDNs from holding on to an older UI after deploys.
        return FileResponse(
            STATIC_INDEX,
            headers={
                "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
                "Pragma": "no-cache",
                "Expires": "0",
            },
        )
    return {"name":"SportsCard Vault","status":"ok","ui_path":str(STATIC_INDEX)}

@app.get("/", include_in_schema=False)
def test_ui():
    return _serve_test_ui()

@app.get("/scan", include_in_schema=False)
def scan_ui():
    return _serve_test_ui()

@app.get("/app", include_in_schema=False)
def app_ui():
    return _serve_test_ui()

@app.get("/api/v1/system/preflight")
def system_preflight():
    vision_ready = (settings.recognition_provider or "safe").lower() == "openai" and bool(settings.openai_api_key)
    provider = (settings.database_provider or "sqlite").lower()
    sqlite_ephemeral = provider == "sqlite" and str(settings.database_path).startswith("/tmp/")
    status = db.provider_status()
    storage = storage_diagnostics()
    database_persistent = status.get("active_provider") in {"postgres", "supabase-rest"}
    image_persistent = bool(storage.get("bucket_exists"))
    notes = []
    if not vision_ready:
        notes.append("Für echte automatische Kartenerkennung OPENAI_API_KEY setzen und RECOGNITION_PROVIDER=openai konfigurieren.")
    if sqlite_ephemeral:
        notes.append("TESTSPEICHER aktiv: SQLite unter /tmp.")
    if status.get("fallback_active"):
        notes.append("Supabase ist angefordert, aber derzeit nicht erreichbar; SQLite-Diagnosefallback aktiv.")
    if status.get("provider_error"):
        notes.append(status["provider_error"])
    return {
        "ready_for_real_scans": vision_ready,
        "ready_for_mass_collection": vision_ready and database_persistent and image_persistent,
        "recognition_provider": settings.recognition_provider,
        "database_provider": provider,
        "database_active_provider": status.get("active_provider"),
        "database_fallback_active": status.get("fallback_active"),
        "database_path": None if provider == "supabase" else settings.database_path,
        "database_persistent": database_persistent,
        "image_storage_provider": storage.get("provider") if image_persistent else "local-fallback",
        "image_storage_persistent": image_persistent,
        "supabase_configured": settings.supabase_ready,
        "supabase_host": settings.supabase_host,
        "supabase_dns_ok": status.get("supabase_dns_ok"),
        "supabase_bucket": settings.supabase_bucket if settings.supabase_ready else None,
        "pricing_provider": settings.price_provider,
        "vision_key_configured": bool(settings.openai_api_key),
        "vision_model": settings.openai_vision_model,
        "notes": notes,
    }

@app.get("/api/v1/system/persistence-check")
def persistence_check():
    """Non-destructive production-persistence diagnostics (V0.15.13)."""
    requested = (settings.database_provider or "sqlite").lower()
    status = db.provider_status()
    storage = storage_diagnostics()
    errors = []
    if status.get("provider_error"):
        errors.append(status["provider_error"])
    if storage.get("error"):
        errors.append(storage["error"])
    pg_dns_ok, pg_dns_error = postgres_probe.dns_check()
    pg_ok, pg_error, pg_info = postgres_probe.connection_check()
    if pg_dns_error:
        errors.append(pg_dns_error)
    if pg_error:
        errors.append(pg_error)
    checks = {
        "database_provider": requested,
        "database_active_provider": status.get("active_provider"),
        "database_fallback_active": status.get("fallback_active"),
        "database_configured": requested == "sqlite" or bool(settings.supabase_database_url) or settings.supabase_ready,
        "database_persistent": status.get("active_provider") in {"postgres", "supabase-rest"},
        "database_connection": status.get("active_provider") in {"postgres", "supabase-rest"},
        "image_storage_persistent": bool(storage.get("bucket_exists")),
        "supabase_configured": settings.supabase_ready,
        "supabase_url_normalized": settings.supabase_url,
        "supabase_host": settings.supabase_host,
        "supabase_dns_ok": status.get("supabase_dns_ok"),
        "supabase_dns_error": status.get("supabase_dns_error"),
        "supabase_bucket": settings.supabase_bucket if settings.supabase_ready else None,
        "storage_dns_ok": storage.get("dns_ok"),
        "storage_provider": storage.get("provider"),
        "storage_sdk": storage.get("sdk"),
        "storage_postgres_image_fallback_configured": storage.get("postgres_image_fallback_configured"),
        "storage_postgres_image_fallback_ready": storage.get("postgres_image_fallback_ready"),
        "storage_postgres_image_fallback_error": storage.get("postgres_image_fallback_error"),
        "storage_s3_error_preserved": storage.get("s3_error_preserved"),
        "storage_endpoint_trials": storage.get("endpoint_trials"),
        "storage_endpoint_trial_any_usable": storage.get("endpoint_trial_any_usable"),
        "storage_endpoint_trial_winner": storage.get("endpoint_trial_winner"),
        "storage_rest_split_any_ok": storage.get("rest_split_any_ok"),
        "storage_s3_split_any_ok": storage.get("s3_split_any_ok"),
        "storage_rest_split_trial": storage.get("rest_split_trial"),
        "storage_boto3_request_url": storage.get("boto3_request_url"),
        "storage_endpoint_path": storage.get("endpoint_path"),
        "storage_endpoint_path_ok": storage.get("endpoint_path_ok"),
        "storage_access_key_length": storage.get("access_key_length"),
        "storage_secret_key_length": storage.get("secret_key_length"),
        "storage_access_key_has_outer_whitespace": storage.get("access_key_has_outer_whitespace"),
        "storage_secret_key_has_outer_whitespace": storage.get("secret_key_has_outer_whitespace"),
        "storage_head_bucket_ok": storage.get("head_bucket_ok"),
        "storage_head_bucket_status": storage.get("head_bucket_status"),
        "storage_head_bucket_exception": storage.get("head_bucket_exception"),
        "storage_head_bucket_error_code": storage.get("head_bucket_s3_error_code"),
        "storage_head_bucket_error_message": storage.get("head_bucket_s3_error_message"),
        "storage_head_bucket_http_status": storage.get("head_bucket_s3_http_status"),
        "storage_project_ref": storage.get("project_ref"),
        "storage_configured": storage.get("configured"),
        "storage_endpoint": storage.get("endpoint"),
        "storage_region": storage.get("region"),
        "storage_host": storage.get("host"),
        "storage_dns_ok": storage.get("dns_ok"),
        "storage_bucket_exists": storage.get("bucket_exists"),
        "storage_object_access_ok": storage.get("object_access_ok"),
        "storage_bucket_probe_method": storage.get("bucket_probe_method"),
        "storage_s3_error_code": storage.get("s3_error_code"),
        "storage_s3_error_message": storage.get("s3_error_message"),
        "storage_s3_http_status": storage.get("s3_http_status"),
        "storage_s3_request_id": storage.get("s3_request_id"),
        "storage_s3_response_body": storage.get("s3_response_body"),
        "storage_list_objects_status": storage.get("list_objects_status"),
        "storage_raw_http_status": storage.get("raw_http_status"),
        "storage_raw_response_content_type": storage.get("raw_response_content_type"),
        "storage_raw_response_body": storage.get("raw_response_body"),
        "storage_raw_request_id": storage.get("raw_request_id"),
        "storage_write_probe_put_ok": storage.get("write_probe_put_ok"),
        "storage_write_probe_head_ok": storage.get("write_probe_head_ok"),
        "storage_write_probe_delete_ok": storage.get("write_probe_delete_ok"),
        "storage_write_probe_put_status": storage.get("write_probe_put_status"),
        "storage_write_probe_head_status": storage.get("write_probe_head_status"),
        "storage_write_probe_delete_status": storage.get("write_probe_delete_status"),
        "storage_write_probe_error_stage": storage.get("write_probe_error_stage"),
        "storage_write_probe_exception": storage.get("write_probe_exception"),
        "storage_bucket_list_visible": storage.get("bucket_list_visible"),
        "s3_access_key_configured": bool(settings.s3_access_key_id),
        "s3_secret_key_configured": bool(settings.s3_secret_access_key),
        "s3_endpoint_candidate": settings.s3_endpoint,
        "s3_region_candidate": settings.s3_region,
        "s3_ready": settings.s3_ready,
        "postgres_url_configured": bool(settings.supabase_database_url),
        "postgres_host": postgres_probe.host(),
        "postgres_dns_ok": pg_dns_ok,
        "postgres_dns_error": pg_dns_error,
        "postgres_connection_ok": pg_ok,
        "postgres_connection_error": pg_error,
        "postgres_info": pg_info,
    }
    checks["ready_for_mass_collection"] = bool(
        checks["database_persistent"]
        and checks["database_connection"]
        and checks["image_storage_persistent"]
        and checks["storage_bucket_exists"]
        and checks["storage_object_access_ok"]
    )
    checks["errors"] = list(dict.fromkeys(errors))
    return checks

@app.get("/api/v1/images/{image_id}/meta", include_in_schema=True)
def image_blob_metadata(image_id: str):
    """Safe metadata-only check for a Postgres image blob."""
    try:
        from .postgres_db import image_blob_meta
        return image_blob_meta(image_id)
    except Exception as exc:
        logger.exception("image blob metadata read failed")
        raise HTTPException(500, detail=f"Image metadata read failed: {type(exc).__name__}")

@app.get("/api/v1/images/{image_id}", include_in_schema=True)
def image_blob(image_id: str, w: int | None = Query(None, ge=96, le=1600)):
    """Serve a persisted image; optionally return a lightweight thumbnail.

    Collection cards use ``?w=480`` so phones do not download multi-megabyte
    originals just to draw a small tile. Card detail still uses the original.
    """
    image_id = (image_id or "").strip()
    if image_id.startswith("pgimg://"):
        image_id = image_id.split("://", 1)[1]
    try:
        from .postgres_db import get_image_blob
        row = get_image_blob(image_id)
    except Exception as exc:
        logger.exception("image blob read failed")
        raise HTTPException(500, detail=f"Image read failed: {type(exc).__name__}")
    if not row:
        raise HTTPException(404, "Image not found")
    raw = bytes(row["data"])
    media_type = row.get("content_type") or "application/octet-stream"
    if w:
        try:
            source = Image.open(io.BytesIO(raw))
            source = ImageOps.exif_transpose(source)
            source.thumbnail((w, int(w * 1.5)), Image.Resampling.LANCZOS)
            if source.mode not in ("RGB", "L"):
                source = source.convert("RGB")
            out = io.BytesIO()
            source.save(out, format="JPEG", quality=80, optimize=True)
            raw = out.getvalue()
            media_type = "image/jpeg"
        except Exception:
            logger.warning("thumbnail generation failed for %s; serving original", image_id, exc_info=True)
    return Response(
        content=raw,
        media_type=media_type,
        headers={
            "Cache-Control": "private, max-age=86400" if w else "private, max-age=3600",
            "X-Image-Storage": "postgres",
            "X-Image-Variant": f"thumb-{w}" if w else "original",
        },
    )

@app.get("/api/v1/collection/summary")
def collection_summary():
    rows=db.export_rows()
    sports={}
    total_instances=0
    graded=0
    rookies=0
    autos=0
    relics=0
    numbered=0
    for row in rows:
        qty=int(row.get("owned_quantity") or 1)
        total_instances += qty
        sport=row.get("sport") or "Unbekannt"
        sports[sport]=sports.get(sport,0)+qty
        graded += qty if row.get("owned_raw_or_graded") == "graded" else 0
        rookies += qty if row.get("is_rookie") else 0
        autos += qty if row.get("is_autograph") else 0
        relics += qty if row.get("is_relic") else 0
        numbered += qty if row.get("is_serial_numbered") else 0
    return {"total_instances":total_instances,"unique_records":len(rows),"sports":sports,"graded":graded,"rookies":rookies,"autographs":autos,"relics":relics,"serial_numbered":numbered}

@app.post("/api/v1/cards/manual")
def create_manual_card(payload: CardCreateRequest):
    return db.create_card(payload.identity.model_dump(), payload.instance.model_dump(mode="json"))

@app.get("/api/v1/collection")
def collection(q: str | None=None, sport: str | None=None, page: int=Query(1,ge=1), page_size: int=Query(50,ge=1,le=200)):
    return db.list_collection(q=q,sport=sport,page=page,page_size=page_size)

@app.get("/api/v1/collection/feed")
def collection_feed(q: str | None=None, page: int=Query(1,ge=1), page_size: int=Query(12,ge=1,le=48)):
    """Compact paged collection feed for the UI.

    V0.22.4 removes the browser-side N+1 pattern where opening the collection
    requested /cards/{id} once for every card before anything could render.
    This endpoint returns only the fields required for tiles in one request.
    """
    listing = db.list_collection(q=q, page=page, page_size=page_size)
    base_items = listing.get("items", []) if isinstance(listing, dict) else []

    def compact(item: dict) -> dict:
        cid = item.get("id") or item.get("card_identity_id")
        card = db.get_card(cid) if cid else None
        identity = (card or {}).get("identity") or item
        instances = (card or {}).get("instances") or []
        first = instances[0] if instances else {}
        return {
            **identity,
            "id": cid or identity.get("id"),
            "instance_count": len(instances) or int(item.get("owned_quantity") or 1),
            "front_image_url": signed_url(first.get("front_image_path")) if first.get("front_image_path") else None,
            "back_image_url": signed_url(first.get("back_image_path")) if first.get("back_image_path") else None,
        }

    if len(base_items) > 1:
        workers = min(6, len(base_items))
        with ThreadPoolExecutor(max_workers=workers) as pool:
            items = list(pool.map(compact, base_items))
    else:
        items = [compact(x) for x in base_items]
    total = listing.get("total") if isinstance(listing, dict) else len(items)
    return {"items": items, "page": page, "page_size": page_size, "total": total, "has_more": page * page_size < int(total or 0)}

@app.get("/api/v1/cards/{card_id}")
def card_detail(card_id: str):
    card=db.get_card(card_id)
    if not card: raise HTTPException(404,"Card not found")
    for inst in card.get("instances", []):
        inst["front_image_url"] = signed_url(inst.get("front_image_path"))
        inst["back_image_url"] = signed_url(inst.get("back_image_path"))
    return card

@app.post("/api/v1/scan/analyze", response_model=ScanResponse)
async def analyze_scan(front_image: UploadFile=File(...), back_image: UploadFile|None=File(None), locked_context: str|None=Form(None)):
    try: locked=json.loads(locked_context) if locked_context else {}
    except json.JSONDecodeError: raise HTTPException(400,"locked_context must be valid JSON")
    scan_dir=Path(settings.upload_dir)/str(uuid4()); scan_dir.mkdir(parents=True,exist_ok=True)
    front_path=scan_dir/("front"+Path(front_image.filename or ".jpg").suffix)
    with front_path.open("wb") as f: shutil.copyfileobj(front_image.file,f)
    back_path=None
    if back_image:
        back_path=scan_dir/("back"+Path(back_image.filename or ".jpg").suffix)
        with back_path.open("wb") as f: shutil.copyfileobj(back_image.file,f)
    # The OpenAI SDK call is synchronous. Running it directly inside this async
    # endpoint blocks Uvicorn's event loop and can prevent Render health checks
    # from answering while a vision request is in flight. On a single-worker
    # service this may drop the browser connection as "Failed to fetch".
    try:
        output = await asyncio.to_thread(
            analyze_images, str(front_path), str(back_path) if back_path else None, locked
        )
    except Exception as exc:
        logger.exception("scan analysis failed")
        raise HTTPException(502, detail=f"Vision analysis failed: {type(exc).__name__}: {str(exc)[:300]}")
    # Second-pass deterministic matching against identities already known to the collection.
    # This improves repeated-set scanning without allowing AI to fabricate an identity.
    known_rows=db.export_rows()
    catalog_matches=rank_catalog(output.get("extracted", {}), known_rows, limit=5)
    if catalog_matches:
        output["catalog_matches"] = catalog_matches
    # Render's local filesystem is ephemeral. In V0.14, when Supabase is enabled,
    # keep local copies only long enough for Vision and immediately persist both
    # card images to the private Supabase Storage bucket.
    image_prefix = str(uuid4())
    try:
        stored_front = persist_image(str(front_path), image_prefix, "front")
        stored_back = persist_image(str(back_path), image_prefix, "back") if back_path else None
    except Exception as exc:
        logger.exception("persistent image upload failed")
        raise HTTPException(502, detail=f"Persistent image upload failed: {type(exc).__name__}: {str(exc)[:300]}")
    sid=db.save_scan(stored_front,stored_back,locked,output)
    return ScanResponse(scan_id=sid,**output)

@app.post("/api/v1/cards/confirm-scan")
def confirm_scan(payload: ConfirmScanRequest):
    # Validate scan before creating a card so invalid IDs cannot orphan records.
    scan=db.get_scan(payload.scan_id)
    if not scan:
        raise HTTPException(404,"Scan not found")
    identity=payload.identity.model_dump()
    user_instance=payload.instance.model_dump(mode="json")
    instance=dict(user_instance)
    instance["front_image_path"] = instance.get("front_image_path") or scan.get("front_image_path")
    instance["back_image_path"] = instance.get("back_image_path") or scan.get("back_image_path")
    created=db.create_card(identity,instance)
    corrections=db.finalize_scan(payload.scan_id,created["card_identity_id"],identity,user_instance)
    return {**created,"corrections_recorded":corrections}



def _guess_value(raw):
    if isinstance(raw, dict) and "value" in raw:
        return raw.get("value")
    return raw

def _build_card_from_scan(scan: dict):
    analysis = scan.get("analysis") or {}
    extracted = analysis.get("extracted") or {}
    instance_extracted = analysis.get("instance_extracted") or {}
    identity_data = {}
    for field in CardIdentityIn.model_fields:
        value = _guess_value(extracted.get(field))
        if value is not None:
            identity_data[field] = value
    # Defaults that keep the model strict without forcing manual entry.
    identity_data.setdefault("secondary_subject_names", [])
    for field in ("is_rookie","is_insert","is_short_print","is_super_short_print","is_case_hit","is_autograph","is_relic","is_rpa","is_booklet","is_die_cut","is_redemption","is_serial_numbered"):
        identity_data.setdefault(field, False)
    instance_data = {"quantity": 1, "raw_or_graded": "raw"}
    for field in OwnedInstanceIn.model_fields:
        value = _guess_value(instance_extracted.get(field))
        if value is not None:
            instance_data[field] = value
    instance_data["front_image_path"] = scan.get("front_image_path")
    instance_data["back_image_path"] = scan.get("back_image_path")
    return identity_data, instance_data, analysis

@app.post("/api/v1/cards/confirm-scan-auto")
def confirm_scan_auto(payload: AutoConfirmScanRequest):
    scan = db.get_scan(payload.scan_id)
    if not scan:
        raise HTTPException(404, "Scan not found")
    if scan.get("status") == "confirmed" and scan.get("final_card_identity_id"):
        return {"already_confirmed": True, "card_identity_id": scan["final_card_identity_id"], "scan_id": payload.scan_id}
    identity_data, instance_data, analysis = _build_card_from_scan(scan)
    missing = [f for f in ("sport", "primary_subject_name") if not identity_data.get(f)]
    if missing:
        raise HTTPException(409, detail={"message":"Automatisches Speichern nicht möglich: Pflichtangaben fehlen.","missing_fields":missing})
    critical = {"sport","season","manufacturer","product_line","set_name","card_number_printed","primary_subject_name","parallel_name","variation_name"}
    uncertain = [f for f in (analysis.get("requires_confirmation") or []) if f in critical]
    if uncertain and not payload.allow_uncertain:
        raise HTTPException(409, detail={"message":"Die Karte wurde erkannt, aber kritische Details sind noch unsicher.","requires_confirmation":uncertain,"hint":"Ergebnis prüfen und danach 'Trotzdem speichern' verwenden, falls korrekt."})
    try:
        identity = CardIdentityIn.model_validate(identity_data).model_dump()
        instance = OwnedInstanceIn.model_validate(instance_data).model_dump(mode="json")
    except Exception as exc:
        raise HTTPException(422, detail=f"Erkannte Kartendaten konnten nicht validiert werden: {exc}")
    created = db.create_card(identity, instance)
    corrections = db.finalize_scan(payload.scan_id, created["card_identity_id"], identity, instance)
    return {**created, "scan_id": payload.scan_id, "auto_saved": True, "saved_with_uncertainty": bool(uncertain), "uncertain_fields": uncertain, "corrections_recorded": corrections}

@app.get("/api/v1/scans")
def scan_history(page: int=Query(1,ge=1), page_size: int=Query(50,ge=1,le=200), status: str|None=None):
    return db.list_scans(page=page,page_size=page_size,status=status)

@app.get("/api/v1/scans/{scan_id}")
def scan_detail(scan_id: str):
    item=db.get_scan(scan_id)
    if not item: raise HTTPException(404,"Scan not found")
    return item

@app.get("/api/v1/recognition/correction-stats")
def correction_stats():
    return db.correction_stats()


def _median(values: list[float]) -> float | None:
    vals=sorted(float(v) for v in values)
    if not vals: return None
    n=len(vals)
    return vals[n//2] if n%2 else (vals[n//2-1]+vals[n//2])/2


def _parse_dt(value):
    if value is None: return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    try:
        return datetime.fromisoformat(str(value).replace('Z','+00:00'))
    except Exception:
        return None


def _pct_change(current: float | None, baseline: float | None) -> float | None:
    if current is None or baseline in (None,0): return None
    return round((float(current)-float(baseline))/float(baseline)*100,2)


def _baseline_value(history: list[dict], days: int) -> float | None:
    cutoff=datetime.now(timezone.utc)-timedelta(days=days)
    eligible=[]
    for point in history:
        dt=_parse_dt(point.get('recorded_at'))
        if dt and dt <= cutoff and point.get('value') is not None:
            eligible.append((dt,float(point['value'])))
    if not eligible: return None
    eligible.sort(key=lambda x:x[0])
    return eligible[-1][1]


def _card_market_state(card_id: str, history_limit: int = 5000) -> dict:
    card=db.get_card(card_id)
    if not card: raise KeyError(card_id)
    comps=card.get('comps') or []
    usable=[c for c in comps if c.get('included_in_valuation',True) and c.get('price') is not None]
    comp_values=[float(c['price']) for c in usable]
    comp_median=_median(comp_values)
    comp_currency=next((c.get('currency') for c in usable if c.get('currency')),None)
    history=db.list_market_snapshots(card_id,limit=history_limit)
    latest=history[-1] if history else None
    # Verified sold comps take precedence; otherwise a licensed provider estimate may drive the current value.
    if comp_median is not None:
        current=float(comp_median); currency=comp_currency
        source='verified_comps'; confidence=min(1.0,len(usable)/max(1,settings.min_reliable_comps))
        last_updated=max((_parse_dt(c.get('sold_at') or c.get('created_at')) for c in usable),default=None,key=lambda x:x or datetime.min.replace(tzinfo=timezone.utc))
        if not last_updated and latest: last_updated=_parse_dt(latest.get('recorded_at'))
    elif latest and latest.get('value') is not None:
        current=float(latest['value']); currency=latest.get('currency')
        source=latest.get('source') or latest.get('snapshot_type') or 'provider'; confidence=latest.get('confidence')
        last_updated=_parse_dt(latest.get('recorded_at'))
    else:
        current=None; currency=None; source=None; confidence=None; last_updated=None
    return {
        'card_id':card_id,'current_value':current,'currency':currency,'source':source,'confidence':confidence,
        'last_updated':last_updated.isoformat() if last_updated else None,
        'change_7d_pct':_pct_change(current,_baseline_value(history,7)),
        'change_30d_pct':_pct_change(current,_baseline_value(history,30)),
        'history':history,'comp_count':len(comps),'included_comp_count':len(usable),
        'low':min(comp_values) if comp_values else None,'high':max(comp_values) if comp_values else None,
        'reliable':len(usable)>=settings.min_reliable_comps,
    }


def _record_current_market_snapshot(card_id: str, source: str = 'verified_comps') -> str | None:
    state=_card_market_state(card_id)
    if state['current_value'] is None: return None
    history=state['history']
    latest=history[-1] if history else None
    # Keep a durable time series without creating dozens of identical points on the same day.
    if latest and latest.get('value') is not None and abs(float(latest['value'])-float(state['current_value'])) < 0.005 and (latest.get('source') or '')==source:
        latest_dt=_parse_dt(latest.get('recorded_at'))
        if latest_dt and latest_dt.date()==datetime.now(timezone.utc).date():
            return latest.get('id')
    return db.add_market_snapshot(card_id,{
        'value':state['current_value'],'currency':state['currency'] or 'USD','source':source,
        'confidence':state['confidence'],'snapshot_type':'verified_comps' if source=='verified_comps' else 'provider_estimate',
        'comp_count':state['included_comp_count'],'metadata':{'method':'market_state_snapshot'}
    })

@app.post("/api/v1/cards/{card_id}/comps/manual")
def manual_comp(card_id: str, payload: ManualCompIn):
    try:
        cid=db.add_comp(card_id,payload.model_dump(mode="json"))
        snapshot_id=_record_current_market_snapshot(card_id,"verified_comps")
    except KeyError: raise HTTPException(404,"Card not found")
    return {"comp_id":cid,"market_snapshot_id":snapshot_id}

@app.get("/api/v1/cards/{card_id}/valuation", response_model=ValuationOut)
def valuation(card_id: str):
    card=db.get_card(card_id)
    if not card: raise HTTPException(404,"Card not found")
    comps=[Comp(float(c["price"]),c["currency"],c.get("raw_or_graded","raw"),c.get("included_in_valuation",True)) for c in card["comps"]]
    result=calculate_valuation(comps,settings.min_reliable_comps)
    return ValuationOut(**result.__dict__)


@app.get("/api/v1/cards/{card_id}/market")
def card_market(card_id: str):
    try: state=_card_market_state(card_id)
    except KeyError: raise HTTPException(404,"Card not found")
    card=db.get_card(card_id) or {}
    return {
        "card_id":card_id,"comp_count":state['comp_count'],"included_comp_count":state['included_comp_count'],
        "median":state['current_value'] if state['source']=='verified_comps' else None,
        "current_value":state['current_value'],"low":state['low'],"high":state['high'],
        "currency":state['currency'],"reliable":state['reliable'],"confidence":state['confidence'],
        "source":state['source'],"last_updated":state['last_updated'],
        "change_7d_pct":state['change_7d_pct'],"change_30d_pct":state['change_30d_pct'],
        "min_reliable_comps":settings.min_reliable_comps,"history":state['history'],"comps":card.get('comps') or []
    }

@app.get("/api/v1/cards/{card_id}/market-history")
def card_market_history(card_id: str, limit: int = Query(5000,ge=1,le=10000)):
    try: state=_card_market_state(card_id,history_limit=limit)
    except KeyError: raise HTTPException(404,"Card not found")
    return {k:state[k] for k in ['card_id','current_value','currency','source','confidence','last_updated','change_7d_pct','change_30d_pct','history']}



@app.get("/api/v1/market/providers")
def market_provider_status():
    return {
        "providers": provider_status(),
        "automatic_provider_configured": bool(settings.soldcomps_api_key),
        "policy": "Only completed sold listings are used as automatic comps. Asking prices and AI-invented prices are excluded.",
    }

@app.get("/api/v1/cards/{card_id}/market-fingerprint")
def card_market_fingerprint(card_id: str):
    card=db.get_card(card_id)
    if not card: raise HTTPException(404,"Card not found")
    fp=build_fingerprint(card)
    return {
        "card_id": card_id,
        "fingerprint": fp.as_dict(),
        "matching_threshold": 0.72,
        "hard_identity_fields": ["subject","card_number","parallel_name","raw_or_graded"],
    }


def _ingest_soldcomps_search(card_id: str, card: dict, search: dict) -> dict:
    fp=build_fingerprint(card)
    normalized=normalize_soldcomps_results(fp, search)
    existing_ids={str(c.get('source_item_id')) for c in (card.get('comps') or []) if c.get('source_item_id')}
    added=0; included=0; excluded=0
    for row in normalized.get('matches') or []:
        item=row['item']; item_id=str(item.get('itemId') or '')
        if item_id and item_id in existing_ids:
            continue
        comp={
            'source':'soldcomps_ebay',
            'source_item_id':item_id or None,
            'source_url':item.get('url'),
            'sale_type':item.get('buyingFormat') or 'sold',
            'sold_at':item.get('endedAt'),
            # Use all-in transaction cost when SoldComps supplies it; this keeps
            # shipping treatment consistent across comps.
            'price':row.get('all_in_price'),
            'currency':row.get('currency') or 'USD',
            'shipping_price':item.get('shippingPrice'),
            'all_in_price':row.get('all_in_price'),
            'raw_or_graded':fp.raw_or_graded or 'raw',
            'grading_company':fp.grading_company,
            'grade_numeric':fp.grade_numeric,
            'title_raw':item.get('title'),
            'matched_identity_confidence':row['match'].get('score'),
            'included_in_valuation':bool(row.get('included_in_valuation')),
            'exclusion_reason':row.get('exclusion_reason'),
            'provider_metadata':{
                'thumbnail_url':item.get('thumbnailUrl'),
                'full_res_thumbnail_url':item.get('fullResThumbnailUrl'),
                'condition':item.get('condition'),
                'best_offer_accepted':item.get('bestOfferAccepted'),
                'seller_feedback_score':item.get('sellerFeedbackScore'),
                'match_evidence':row['match'].get('evidence'),
                'query':normalized.get('query'),
            },
        }
        try:
            db.add_comp(card_id,comp)
            added += 1
            if comp['included_in_valuation']: included += 1
            else: excluded += 1
            if item_id: existing_ids.add(item_id)
        except Exception as exc:
            logger.warning("Could not persist SoldComps item %s for card %s: %s", item_id, card_id, exc)
    snapshot_id=_record_current_market_snapshot(card_id,'verified_comps')
    current=_card_market_state(card_id)
    return {
        'query':normalized.get('query'),'raw_results':normalized.get('raw_count',0),
        'identity_matches':normalized.get('matched_count',0),'included_matches':normalized.get('included_count',0),
        'rejected_count':normalized.get('rejected_count',0),'new_comps':added,
        'new_included_comps':included,'new_excluded_outliers':excluded,'snapshot_id':snapshot_id,
        'rejected_preview':normalized.get('rejected_preview',[]),
        'current_market':{k:current[k] for k in ['current_value','currency','source','confidence','last_updated','change_7d_pct','change_30d_pct','included_comp_count','reliable']},
    }


@app.post("/api/v1/cards/{card_id}/market/refresh")
def refresh_card_market(card_id: str):
    card=db.get_card(card_id)
    if not card: raise HTTPException(404,"Card not found")
    fp=build_fingerprint(card)
    if not settings.soldcomps_api_key:
        state=_card_market_state(card_id)
        return {
            "card_id": card_id,"status": "provider_not_configured","fingerprint": fp.as_dict(),
            "providers": provider_status(),"new_verified_comps": 0,"new_provider_estimates": 0,
            "current_market": {k:state[k] for k in ['current_value','currency','source','confidence','last_updated','change_7d_pct','change_30d_pct']},
            "message": "SoldComps ist noch nicht konfiguriert. Es wurden keine Preise erfunden oder aus aktiven Angeboten abgeleitet.",
        }
    try:
        search=soldcomps_search(fp)
        result=_ingest_soldcomps_search(card_id,card,search)
    except SoldCompsError as exc:
        status='quota_exceeded' if exc.code=='quota_exceeded' else 'provider_error'
        return {
            'card_id':card_id,'status':status,'fingerprint':fp.as_dict(),'providers':provider_status(),
            'new_verified_comps':0,'new_provider_estimates':0,
            'provider_http_status':exc.status_code,'provider_error_code':exc.code,
            'message':str(exc),
        }
    return {
        'card_id':card_id,'status':'updated','fingerprint':fp.as_dict(),'providers':provider_status(),
        'new_verified_comps':result['new_comps'],'new_provider_estimates':0,'soldcomps':result,
        'message':f"SoldComps geprüft: {result['raw_results']} Verkäufe, {result['identity_matches']} Identitäts-Matches, {result['new_comps']} neue Comps gespeichert.",
    }

@app.post("/api/v1/market/match-preview")
def market_match_preview(payload: dict):
    card_id=payload.get("card_id")
    candidate=payload.get("candidate") or {}
    if not card_id: raise HTTPException(422,"card_id required")
    card=db.get_card(card_id)
    if not card: raise HTTPException(404,"Card not found")
    fp=build_fingerprint(card)
    return {"card_id":card_id,"fingerprint":fp.as_dict(),"match":score_candidate(fp,candidate)}

def _compute_collection_market_summary():
    """Compute a fresh summary from persisted per-card market data. Used only when a snapshot is created or as a legacy fallback.

    V0.22.4.4 intentionally does *not* read per-card price history here.
    Opening the collection only needs each card's already stored comps/current
    value. Historical snapshots are loaded separately by /collection/market-history.
    No provider/SoldComps request is made.
    """
    items=[]; page=1; page_size=200
    while True:
        listing=db.list_collection(page=page,page_size=page_size)
        batch=listing.get("items",[]) if isinstance(listing,dict) else []
        items.extend(batch)
        if len(batch) < page_size: break
        page += 1
        if page > 100: break

    card_ids=[]
    for item in items:
        cid=item.get("id") or item.get("card_identity_id")
        if cid and cid not in card_ids: card_ids.append(cid)

    cards={}; valued=0; total=0.0; missing=0; comp_count=0; currencies=set(); latest_dates=[]
    for cid in card_ids:
        try:
            card=db.get_card(cid)
            if not card:
                missing += 1
                continue
            comps=card.get("comps") or []
            usable=[c for c in comps if c.get("included_in_valuation",True) and c.get("price") is not None]
            values=[float(c["price"]) for c in usable]
            current=_median(values)
            currency=next((c.get("currency") for c in usable if c.get("currency")),None)
            source="verified_comps" if current is not None else None
            confidence=min(1.0,len(usable)/max(1,settings.min_reliable_comps)) if current is not None else None
            sold_dates=[_parse_dt(c.get("sold_at") or c.get("created_at")) for c in usable]
            sold_dates=[d for d in sold_dates if d]
            last_updated=max(sold_dates).isoformat() if sold_dates else None

            # Provider-only values are uncommon in this installation, but preserve
            # them without loading the full history: request only the latest point.
            if current is None:
                try:
                    hist=db.list_market_snapshots(cid,limit=1)
                except Exception:
                    hist=[]
                latest=hist[-1] if hist else None
                if latest and latest.get("value") is not None:
                    current=float(latest["value"]); currency=latest.get("currency")
                    source=latest.get("source") or latest.get("snapshot_type") or "provider"
                    confidence=latest.get("confidence")
                    last_updated=latest.get("recorded_at")

            state={
                "card_id":cid,"current_value":current,"currency":currency,"source":source,
                "confidence":confidence,"last_updated":last_updated,
                "change_7d_pct":None,"change_30d_pct":None,"history":[],
                "comp_count":len(comps),"included_comp_count":len(usable),
                "low":min(values) if values else None,"high":max(values) if values else None,
                "reliable":len(usable)>=settings.min_reliable_comps,
            }
            cards[cid]=state
            comp_count += len(usable)
            if last_updated: latest_dates.append(last_updated)
            if current is None:
                missing += 1
                continue
            valued += 1; total += float(current)
            if currency: currencies.add(currency)
        except Exception:
            missing += 1
            logger.exception("Deferred lightweight market state failed for %s",cid)

    currency=next(iter(currencies)) if len(currencies)==1 else ("MIXED" if currencies else None)
    considered=len(items)
    return {
        "cards_considered":considered,"valued_cards":valued,"cards_without_comps":missing,
        "included_comp_count":comp_count,"coverage_pct":round((valued/considered*100),1) if considered else 0.0,
        "estimated_collection_value":round(total,2) if valued else None,"currency":currency,
        "change_7d_pct":None,"change_30d_pct":None,
        "last_market_update":max(latest_dates) if latest_dates else None,"cards":cards,
        "method":"lightweight_persisted_comps_no_history_no_provider_calls",
        "status":"valued" if valued else "waiting_for_comps"
    }


def _cached_market_summary_from_snapshot():
    """Return the newest usable precomputed/positioned summary without per-card reads.

    V0.22.4.14 no longer assumes a database-specific ordering for snapshot lists.
    It scans newest-first for a full cache, then newest-first for a legacy positioned
    snapshot. This lets existing V0.22.x snapshots become instant caches immediately.
    """
    try:
        snaps=db.list_collection_market_snapshots(limit=200)
    except Exception:
        return None
    if not snaps:
        return None
    ordered=sorted(snaps,key=lambda x:str(x.get("recorded_at") or ""),reverse=True)

    # Prefer the newest full dashboard cache.
    for snap in ordered:
        meta=snap.get("metadata") or {}
        cached=meta.get("market_summary_cache")
        if isinstance(cached,dict) and isinstance(cached.get("cards"),dict):
            out=dict(cached)
            out["method"]="precomputed_collection_snapshot_cache"
            out["cache_recorded_at"]=snap.get("recorded_at")
            return out

    # Compatibility path: use the newest snapshot that already froze per-card positions.
    latest=None; positions=None
    for snap in ordered:
        pos=(snap.get("metadata") or {}).get("positions")
        if isinstance(pos,dict) and pos:
            latest=snap; positions=pos; break
    if latest is None or not positions:
        return None

    cards={}; currencies=set(); total=0.0
    for cid,pos in positions.items():
        if not isinstance(pos,dict) or pos.get("value") is None:
            continue
        value=float(pos["value"]); currency=pos.get("currency") or latest.get("currency")
        cards[cid]={"card_id":cid,"current_value":value,"currency":currency,"source":"snapshot_cache",
                    "confidence":None,"last_updated":latest.get("recorded_at"),"change_7d_pct":None,"change_30d_pct":None,
                    "history":[],"comp_count":0,"included_comp_count":0,"low":None,"high":None,"reliable":False}
        total += value
        if currency: currencies.add(currency)
    try:
        current_total=int((db.list_collection(page=1,page_size=1) or {}).get("total") or latest.get("total_cards") or len(cards))
    except Exception:
        current_total=int(latest.get("total_cards") or len(cards))
    valued=len(cards)
    currency=latest.get("currency") or (next(iter(currencies)) if len(currencies)==1 else ("MIXED" if currencies else None))
    return {
        "cards_considered":current_total,"valued_cards":valued,"cards_without_comps":max(0,current_total-valued),
        "included_comp_count":int(latest.get("included_comp_count") or 0),
        "coverage_pct":round((valued/current_total*100),1) if current_total else 0.0,
        "estimated_collection_value":round(float(latest.get("value") if latest.get("value") is not None else total),2) if valued else None,
        "currency":currency,"change_7d_pct":None,"change_30d_pct":None,"last_market_update":latest.get("recorded_at"),
        "cards":cards,"method":"legacy_portfolio_snapshot_cache","status":"valued" if valued else "waiting_for_comps",
        "cache_recorded_at":latest.get("recorded_at")
    }


_market_cache_lock = threading.Lock()
_market_cache_building = False
_market_cache_error: str | None = None
_market_cache_started_at: str | None = None

def _build_collection_market_cache_background():
    """Build one durable cache from already persisted comps without provider calls.

    This may take a while on legacy installations, therefore it must never run in the
    normal GET request path. Once written, future collection opens are O(1)-style reads.
    """
    global _market_cache_building, _market_cache_error
    try:
        sid=_record_collection_market_snapshot("market_cache_bootstrap")
        if not sid:
            _market_cache_error="Cache konnte noch nicht aufgebaut werden; es sind keine bewertbaren Marktdaten vorhanden."
        else:
            _market_cache_error=None
            logger.info("collection market cache bootstrap completed: %s",sid)
    except Exception as exc:
        _market_cache_error=f"{type(exc).__name__}: {exc}"
        logger.exception("collection market cache bootstrap failed")
    finally:
        with _market_cache_lock:
            _market_cache_building=False

def _ensure_collection_market_cache_warmup() -> bool:
    """Start at most one background cache build. Returns True while a build is active."""
    global _market_cache_building, _market_cache_started_at
    # Avoid rebuilding if a usable durable cache already exists.
    try:
        if _cached_market_summary_from_snapshot() is not None:
            return False
    except Exception:
        pass
    with _market_cache_lock:
        if _market_cache_building:
            return True
        _market_cache_building=True
        _market_cache_started_at=datetime.now(timezone.utc).isoformat()
        threading.Thread(target=_build_collection_market_cache_background,daemon=True,name="market-cache-bootstrap").start()
        return True


@app.get("/api/v1/collection/market-cache")
def collection_market_cache():
    """V0.22.4.14: instant, strictly read-only collection market cache.

    Normal collection opens never calculate market values, walk card comps, start a
    background job, or call SoldComps/providers. The endpoint only reads an already
    persisted collection snapshot. Expensive cache creation is explicit via
    POST /api/v1/collection/market-cache/rebuild and is also performed after the
    user's explicit collection market refresh.
    """
    try:
        cached=_cached_market_summary_from_snapshot()
    except Exception as exc:
        logger.warning("market-cache snapshot read failed: %s",exc)
        cached=None
    if cached is not None:
        out=dict(cached)
        ai_estimates, ai_summary = _latest_defensive_estimate_payload()
        out["defensive_estimates"]=ai_estimates
        out["defensive_estimate_summary"]=ai_summary
        out["cache_ready"]=True
        out["status"]="valued" if out.get("estimated_collection_value") is not None else out.get("status","cache_ready")
        out["method"]="instant_persisted_snapshot_cache"
        return out
    try:
        listing=db.list_collection(page=1,page_size=1) or {}
        total=int(listing.get("total") or 0) if isinstance(listing,dict) else 0
    except Exception:
        total=0
    return {
        "status":"cache_missing","cache_ready":False,"cards":{},
        "cards_considered":total,"valued_cards":0,"cards_without_comps":total,
        "included_comp_count":0,"coverage_pct":0.0,"estimated_collection_value":None,
        "currency":None,"last_market_update":None,"method":"instant_persisted_snapshot_cache",
        "message":"Noch kein vollständiger Marktcache gespeichert. Einmalig 'Marktcache initialisieren' ausführen oder 'Marktdaten aktualisieren'."
    }

@app.post("/api/v1/collection/market-cache/rebuild")
def rebuild_collection_market_cache():
    """Explicit one-time migration path for legacy persisted comps.

    This may take a while, but it is never invoked while merely opening the collection.
    It uses only already persisted data and makes zero SoldComps/provider requests.
    Once complete, subsequent collection opens use the O(1)-style snapshot cache.
    """
    started=datetime.now(timezone.utc)
    summary=_compute_collection_market_summary()
    value=summary.get("estimated_collection_value")
    currency=summary.get("currency")
    if value is None or not currency or currency == "MIXED":
        return {
            "status":"not_available","cache_ready":False,
            "elapsed_seconds":round((datetime.now(timezone.utc)-started).total_seconds(),2),
            "message":"Aus den gespeicherten Daten konnte noch kein eindeutiger Sammlungswert erzeugt werden.",
            "summary":summary,
        }
    try:
        sid=db.add_collection_market_snapshot({
            "value":value,"currency":currency,"valued_cards":summary.get("valued_cards") or 0,
            "total_cards":summary.get("cards_considered") or 0,"included_comp_count":summary.get("included_comp_count") or 0,
            "metadata":{
                "reason":"manual_cache_rebuild","coverage_pct":summary.get("coverage_pct") or 0,
                "positions":{
                    cid:{"value":round(float(state.get("current_value")),2),"currency":state.get("currency") or currency}
                    for cid,state in (summary.get("cards") or {}).items() if state.get("current_value") is not None
                },
                "market_summary_cache":summary,
            }
        })
    except Exception as exc:
        logger.exception("manual collection market cache rebuild persist failed")
        raise HTTPException(500,f"Market cache persist failed: {type(exc).__name__}: {exc}")
    return {
        "status":"created","cache_ready":True,"snapshot_id":sid,
        "elapsed_seconds":round((datetime.now(timezone.utc)-started).total_seconds(),2),
        "summary":summary,
        "message":"Marktcache aus bereits gespeicherten Daten aufgebaut. Keine Provider-Abfrage ausgeführt.",
    }

@app.get("/api/v1/collection/market-summary")
def collection_market_summary():
    """Compatibility alias for the instant persisted cache.

    V0.22.4.14 deliberately performs no calculation on GET. Older frontends can call
    this route safely without triggering a collection-wide comp scan.
    """
    return collection_market_cache()


def _record_collection_market_snapshot(reason: str = "market_refresh") -> str | None:
    summary=_compute_collection_market_summary()
    prior_ai, prior_ai_summary = _latest_defensive_estimate_payload()
    for cid,state in (summary.get("cards") or {}).items():
        if state.get("current_value") is not None:
            prior_ai.pop(cid,None)
    value=summary.get("estimated_collection_value")
    currency=summary.get("currency")
    if value is None or not currency or currency == "MIXED":
        return None
    try:
        return db.add_collection_market_snapshot({
            "value":value,"currency":currency,"valued_cards":summary.get("valued_cards") or 0,
            "total_cards":summary.get("cards_considered") or 0,"included_comp_count":summary.get("included_comp_count") or 0,
            "metadata":{
                "reason":reason,"coverage_pct":summary.get("coverage_pct") or 0,
                "positions":{
                    cid:{"value":round(float(state.get("current_value")),2),"currency":state.get("currency") or currency}
                    for cid,state in (summary.get("cards") or {}).items() if state.get("current_value") is not None
                },
                # V0.22.4.14: complete precomputed dashboard payload. Normal page loads
                # read this JSON directly instead of scanning every card and comp.
                "market_summary_cache":summary,
                "defensive_estimates":prior_ai,
                "defensive_estimate_summary":prior_ai_summary,
            }
        })
    except Exception:
        return None

@app.post("/api/v1/collection/market/performance-baseline")
def create_collection_performance_baseline():
    """Create one holdings-aware snapshot when V0.22.3 is first used.

    This does not call a market provider and therefore consumes no SoldComps request.
    It only freezes the currently known card values/holdings so later additions and
    removals can be separated from genuine market-price movement.
    """
    try:
        existing=db.list_collection_market_snapshots(limit=20000)
    except Exception:
        existing=[]
    positioned=[p for p in existing if isinstance((p.get("metadata") or {}).get("positions"),dict) and (p.get("metadata") or {}).get("positions")]
    if positioned:
        return {"status":"already_initialized","snapshot_id":positioned[-1].get("id"),"positioned_snapshots":len(positioned)}
    sid=_record_collection_market_snapshot('performance_baseline')
    if not sid:
        return {"status":"not_available","snapshot_id":None,"message":"Noch kein vollständig bewertbarer Sammlungswert vorhanden."}
    return {"status":"created","snapshot_id":sid,"message":"Performance-Basis gespeichert; künftige Zugänge/Abgänge werden getrennt von Marktbewegungen ausgewiesen."}


@app.post("/api/v1/collection/market/coverage-refresh")
def refresh_collection_market_coverage(max_requests: int = Query(20, ge=1, le=50)):
    """Second-pass SoldComps discovery for cards that still have no market value.

    V0.22.5 deliberately does not invent prices and does not touch already-valued
    cards. It uses a broader provider query only to discover candidate sold listings;
    every result must still pass the strict local identity matcher before being
    persisted as a verified comp. This keeps the operation quota-conscious.
    """
    if not settings.soldcomps_api_key:
        return {
            "status":"provider_not_configured","cards_without_value":0,"provider_requests_used":0,
            "message":"SoldComps ist nicht konfiguriert. Es wurden keine Preise erfunden."
        }

    summary=_compute_collection_market_summary()
    states=summary.get("cards") or {}
    unresolved=[cid for cid,state in states.items() if state.get("current_value") is None]

    if not unresolved:
        return {
            "status":"already_complete","cards_without_value":0,"cards_recovered":0,
            "provider_requests_used":0,"new_verified_comps":0,
            "message":"Alle Karten mit vorhandenen Marktdaten sind bereits bewertet."
        }

    # Group identical fallback searches so duplicate/closely related holdings consume
    # one provider request. A broad provider search is safe because ingestion still
    # performs exact player/card/parallel/grade checks locally.
    groups: dict[str, list[tuple[str, dict, dict]]] = {}
    skipped=[]
    for cid in unresolved:
        card=db.get_card(cid)
        if not card:
            skipped.append({"card_id":cid,"reason":"card_not_found"})
            continue
        fp=build_fingerprint(card)
        strategies=fp.soldcomps_queries()
        fallback=next((x for x in strategies if x.get("strategy")=="fallback_broad"),None)
        if not fallback or not fallback.get("query"):
            skipped.append({"card_id":cid,"reason":"insufficient_fingerprint"})
            continue
        groups.setdefault(fallback["query"],[]).append((cid,card,fallback))

    selected_queries=list(groups.keys())[:max_requests]
    deferred_queries=list(groups.keys())[max_requests:]
    search_cache: dict[str,dict]={}; search_errors: dict[str,dict]={}
    max_workers=max(1,min(4,len(selected_queries)))

    def _coverage_search(query: str):
        cid,card,strategy=groups[query][0]
        fp=build_fingerprint(card)
        return soldcomps_search(fp,query_override=query,exact_match=False)

    if selected_queries:
        with ThreadPoolExecutor(max_workers=max_workers,thread_name_prefix="coverage-soldcomps") as pool:
            futures={pool.submit(_coverage_search,q):q for q in selected_queries}
            for fut in as_completed(futures):
                q=futures[fut]
                try: search_cache[q]=fut.result()
                except SoldCompsError as exc:
                    search_errors[q]={"http_status":exc.status_code,"code":exc.code,"message":str(exc)}
                except Exception as exc:
                    search_errors[q]={"message":f"{type(exc).__name__}: {exc}"}

    recovered=0; new_comps=0; details=[]; errors=[]
    for query in selected_queries:
        rows=groups[query]
        if query in search_errors:
            for cid,_card,_strategy in rows:
                errors.append({"card_id":cid,"query":query,**search_errors[query]})
            continue
        provider_result=search_cache.get(query)
        if not provider_result:
            continue
        for cid,card,strategy in rows:
            try:
                before=_card_market_state(cid).get("current_value")
                result=_ingest_soldcomps_search(cid,card,provider_result)
                after=result.get("current_market",{}).get("current_value")
                if before is None and after is not None:
                    recovered += 1
                new_comps += result.get("new_comps") or 0
                details.append({
                    "card_id":cid,"strategy":"fallback_broad","query":query,
                    "raw_results":result.get("raw_results") or 0,
                    "identity_matches":result.get("identity_matches") or 0,
                    "included_matches":result.get("included_matches") or 0,
                    "new_comps":result.get("new_comps") or 0,
                    "recovered":bool(before is None and after is not None),
                })
            except Exception as exc:
                errors.append({"card_id":cid,"query":query,"message":f"{type(exc).__name__}: {exc}"})

    snapshot_id=_record_collection_market_snapshot("coverage_refresh")
    after_summary=_compute_collection_market_summary()
    remaining=max(0,(after_summary.get("cards_considered") or 0)-(after_summary.get("valued_cards") or 0))
    status="updated" if recovered or new_comps else ("partial" if errors else "no_new_matches")
    return {
        "status":status,
        "cards_without_value_before":len(unresolved),
        "cards_recovered":recovered,
        "cards_without_value_after":remaining,
        "provider_requests_used":len(selected_queries),
        "request_budget":max_requests,
        "deferred_query_groups":len(deferred_queries),
        "new_verified_comps":new_comps,
        "collection_snapshot_id":snapshot_id,
        "errors":errors,"skipped":skipped,"details":details,
        "message":(
            f"Abdeckungs-Suche: {len(selected_queries)} zusätzliche SoldComps-Abfragen, "
            f"{recovered} Karten neu bewertet, {new_comps} neue verifizierte Comps. "
            f"{remaining} Karten bleiben ohne Marktwert."
        ),
    }




def _latest_defensive_estimate_payload() -> tuple[dict, dict]:
    """Load the newest persisted defensive estimate bundle from portfolio snapshots."""
    try:
        snaps=db.list_collection_market_snapshots(limit=500)
    except Exception:
        return {}, {}
    ordered=sorted(snaps or [], key=lambda x:str(x.get("recorded_at") or ""), reverse=True)
    for snap in ordered:
        meta=snap.get("metadata") or {}
        estimates=meta.get("defensive_estimates")
        if isinstance(estimates,dict):
            summary=meta.get("defensive_estimate_summary")
            return estimates, (summary if isinstance(summary,dict) else {})
    return {}, {}


def _persist_defensive_estimates(estimates: dict, estimate_summary: dict, market_summary: dict) -> str | None:
    """Persist display-only AI estimates without creating a fake market-history move.

    We reuse collection_market_snapshots as durable JSON storage, but tag the row so the
    portfolio-history endpoint can ignore it. Verified positions remain the only official
    market value and performance source.
    """
    value=market_summary.get("estimated_collection_value")
    currency=market_summary.get("currency")
    if value is None or not currency or currency == "MIXED":
        return None
    clean={}
    cards=market_summary.get("cards") or {}
    for cid,est in (estimates or {}).items():
        if not isinstance(est,dict):
            continue
        if (cards.get(cid) or {}).get("current_value") is not None:
            continue
        clean[cid]=est
    return db.add_collection_market_snapshot({
        "value":value,"currency":currency,
        "valued_cards":market_summary.get("valued_cards") or 0,
        "total_cards":market_summary.get("cards_considered") or 0,
        "included_comp_count":market_summary.get("included_comp_count") or 0,
        "metadata":{
            "reason":"defensive_estimate_store",
            "coverage_pct":market_summary.get("coverage_pct") or 0,
            "positions":{
                cid:{"value":round(float(state.get("current_value")),2),"currency":state.get("currency") or currency}
                for cid,state in cards.items() if state.get("current_value") is not None
            },
            "market_summary_cache":market_summary,
            "defensive_estimates":clean,
            "defensive_estimate_summary":estimate_summary,
        }
    })


@app.api_route("/api/v1/collection/market/defensive-estimates", methods=["GET","POST"])
def defensive_collection_estimates():
    """Conservative, card-specific estimates for cards without verified market value.

    V0.22.6.9 fixes card-specific feature hydration before running the hybrid evidence model:
    1) exact/near verified peers when available,
    2) category anchors (same player/product/set/team/year),
    3) a defensive collection quantile only as last-resort anchor,
    4) explicit positive card features and scarcity adjustments.

    Verified SoldComps always remain authoritative and are never overwritten.
    """
    summary=_compute_collection_market_summary()
    states=summary.get("cards") or {}

    # V0.22.6.9: hydrate recognition fields from the collection row as well as get_card().
    # Some DB providers return a narrower get_card payload; that made different cards
    # appear featureless and inherit the same defensive anchor and estimate.
    collection_items={}
    page=1; page_size=200
    while True:
        listing=db.list_collection(page=page,page_size=page_size)
        batch=listing.get("items",[]) if isinstance(listing,dict) else []
        for item in batch:
            cid=item.get("id") or item.get("card_identity_id")
            if cid: collection_items[cid]=item
        if len(batch)<page_size: break
        page+=1
        if page>100: break

    def hydrated_card(cid):
        base=dict(collection_items.get(cid) or {})
        detail=db.get_card(cid) or {}
        for key,value in detail.items():
            if value not in (None,'',[],{}): base[key]=value
            elif key not in base: base[key]=value
        return base

    valued=[]; missing=[]
    for cid,state in states.items():
        card=hydrated_card(cid)
        row={"card_id":cid,"card":card,"value":state.get("current_value"),"currency":state.get("currency")}
        (valued if state.get("current_value") is not None else missing).append(row)
    if not valued:
        return {"status":"no_verified_basis","estimates":[],"verified_total":summary.get("estimated_collection_value"),"message":"Keine verifizierte Preisbasis für defensive Modellschätzungen vorhanden."}

    import math,re,statistics
    def norm(x): return re.sub(r'[^a-z0-9]+',' ',str(x or '').lower()).strip()
    def toks(x): return set(norm(x).split())
    def q(values, frac):
        vals=sorted(float(v) for v in values if v is not None)
        if not vals:return 0.0
        if len(vals)==1:return vals[0]
        pos=(len(vals)-1)*frac; lo=int(math.floor(pos)); hi=int(math.ceil(pos))
        if lo==hi:return vals[lo]
        return vals[lo]*(hi-pos)+vals[hi]*(pos-lo)
    def med(values):
        vals=[float(v) for v in values if v is not None]
        return statistics.median(vals) if vals else None
    def print_run(c):
        for key in ('known_print_run','serial_print_run'):
            try:
                n=int(c.get(key) or 0)
                if n>0:return n
            except (TypeError,ValueError):pass
        return None
    def scarcity_multiplier(c):
        n=print_run(c)
        if not n:return 1.0, None
        if n<=1:return 1.75,f'/1'
        if n<=5:return 1.55,f'/{n}'
        if n<=10:return 1.38,f'/{n}'
        if n<=25:return 1.25,f'/{n}'
        if n<=50:return 1.16,f'/{n}'
        if n<=99:return 1.10,f'/{n}'
        if n<=199:return 1.05,f'/{n}'
        return 1.02,f'/{n}'

    # Conservative priors are intentionally modest. Empirical collection evidence can
    # override them when at least two valued examples for a feature exist.
    FEATURE_PRIORS={
        'is_rookie':1.12,'is_autograph':1.30,'is_relic':1.16,'is_rpa':1.48,
        'is_insert':1.05,'is_short_print':1.16,'is_super_short_print':1.28,
        'is_case_hit':1.24,'is_serial_numbered':1.06,
    }
    valued_values=[float(v['value']) for v in valued]
    global_med=med(valued_values) or 1.0
    global_q30=max(.50,q(valued_values,.30))
    global_q20=max(.50,q(valued_values,.20))

    def empirical_feature_factor(key):
        on=[float(v['value']) for v in valued if bool((v['card'] or {}).get(key))]
        off=[float(v['value']) for v in valued if not bool((v['card'] or {}).get(key))]
        if len(on)>=2 and len(off)>=2:
            a,b=med(on),med(off)
            if a and b:
                return max(.82,min(1.55,a/b)), 'empirical'
        return FEATURE_PRIORS[key], 'prior'

    feature_factor_cache={k:empirical_feature_factor(k) for k in FEATURE_PRIORS}

    def feature_multiplier(c):
        m=1.0; parts=[]
        for key in FEATURE_PRIORS:
            if bool(c.get(key)):
                f,src=feature_factor_cache[key]
                m*=f; parts.append({'feature':key,'factor':round(f,3),'source':src})
        sf,label=scarcity_multiplier(c)
        if label:
            m*=sf; parts.append({'feature':'print_run','factor':round(sf,3),'source':label})
        return min(m,2.65),parts

    def similarity(a,b):
        score=0.0; reasons=[]
        exact=(('primary_subject_name',12,'same_player'),('product_line',6,'same_product'),('set_name',5,'same_set'),
               ('parallel_name',4,'same_parallel'),('release_year',2.5,'same_year'),('season',2,'same_season'),
               ('manufacturer',1.5,'same_manufacturer'),('team_name',2,'same_team'),('sport',1,'same_sport'))
        for k,w,r in exact:
            av,bv=norm(a.get(k)),norm(b.get(k))
            if av and bv and av==bv:score+=w;reasons.append(r)
        for k,w in (('product_line',1.8),('set_name',1.5),('parallel_name',1.4),('insert_name',1.2)):
            at,bt=toks(a.get(k)),toks(b.get(k))
            if at and bt and at!=bt:
                j=len(at&bt)/len(at|bt);score+=w*j
        for key in FEATURE_PRIORS:
            aa,bb=bool(a.get(key)),bool(b.get(key))
            if aa and bb:score+=1.35
            elif aa!=bb:score-=.55
        ar,br=print_run(a),print_run(b)
        if ar and br:
            ratio=max(ar,br)/max(1,min(ar,br))
            if ratio<=1.25:score+=3;reasons.append('similar_print_run')
            elif ratio<=2:score+=1.5
            elif ratio>=5:score-=1
        an,bn=norm(a.get('card_number_normalized') or a.get('card_number_printed')),norm(b.get('card_number_normalized') or b.get('card_number_printed'))
        if an and bn and an==bn and any(r in reasons for r in ('same_player','same_product','same_set')):
            score+=2;reasons.append('same_card_number')
        return score,reasons

    def category_anchor(c):
        # Blend only evidence actually present in the verified collection.
        groups=[]
        specs=(('primary_subject_name',5.0,'same_player'),('product_line',2.8,'same_product'),('set_name',2.5,'same_set'),
               ('team_name',1.4,'same_team'),('release_year',1.0,'same_year'),('manufacturer',.8,'same_manufacturer'))
        for key,w,label in specs:
            cv=norm(c.get(key))
            if not cv:continue
            vals=[float(v['value']) for v in valued if norm((v['card'] or {}).get(key))==cv]
            if vals:
                groups.append((med(vals),w,label,len(vals)))
        # Defensive baseline prevents sparse category matches from becoming overconfident.
        base_weight=2.0
        total=global_q30*base_weight; weight=base_weight
        for val,w,_,count in groups:
            # shrink single-observation categories slightly
            ww=w*(.72 if count==1 else 1.0)
            total+=val*ww;weight+=ww
        return total/weight,groups

    previous,_=_latest_defensive_estimate_payload()
    fresh=[]; unresolved=[]
    for row in missing:
        c=row['card']; candidates=[]
        for v in valued:
            sc,rs=similarity(c,v['card'])
            candidates.append((sc,float(v['value']),v['card'],rs,v['card_id']))
        candidates.sort(key=lambda x:x[0],reverse=True)
        strong=[p for p in candidates if p[0]>=7.0 and any(r in p[3] for r in ('same_player','same_product','same_set','same_team'))]
        fm,feature_parts=feature_multiplier(c)
        anchor,anchor_groups=category_anchor(c)
        peer_diag=[]
        for p in candidates[:5]:
            pc=p[2] or {}
            peer_diag.append({'card_id':p[4],'player':pc.get('primary_subject_name'),'product_line':pc.get('product_line'),
                'set_name':pc.get('set_name'),'card_number':pc.get('card_number_printed') or pc.get('card_number_normalized'),
                'value':round(float(p[1]),2),'score':round(float(p[0]),2),'reasons':list(p[3] or []),'accepted':p in strong})

        if strong:
            top=strong[0][0]; band=[p for p in strong[:6] if p[0]>=max(7.0,top-3.0)]
            weights=[max(1.0,p[0])**2 for p in band]
            peer_base=sum(p[1]*w for p,w in zip(band,weights))/sum(weights)
            peer_factors=[feature_multiplier(p[2])[0] for p in band]
            peer_factor=sum(f*w for f,w in zip(peer_factors,weights))/sum(weights)
            ratio=max(.60,min(1.70,fm/max(.50,peer_factor)))
            # Blend category anchor and strong-peer base, then shave 12% defensively.
            base=.68*peer_base+.32*anchor
            estimate=base*ratio*.88
            basis='verified_peer_blend'; confidence='mittel' if len(band)>=2 or top>=12 else 'niedrig'; peer_count=len(band)
            sim_score=top
        else:
            # V0.22.6.9: before using a shared category anchor, use weak-but-real peer evidence.
            # This avoids identical prices for structurally different cards while keeping every
            # distinction grounded in already verified collection values.
            soft=[p for p in candidates if p[0]>=2.0][:6]
            if soft:
                soft_weights=[max(.5,p[0]+1.5)**1.7 for p in soft]
                soft_base=sum(p[1]*w for p,w in zip(soft,soft_weights))/sum(soft_weights)
                soft_peer_factors=[feature_multiplier(p[2])[0] for p in soft]
                soft_peer_factor=sum(f*w for f,w in zip(soft_peer_factors,soft_weights))/sum(soft_weights)
                ratio=max(.62,min(1.62,fm/max(.50,soft_peer_factor)))
                # Category evidence remains a stabilizer, but the nearest real peers now drive
                # the majority of the estimate. A defensive haircut stays in place.
                base=.62*soft_base+.38*anchor
                estimate=base*ratio*.82
                ceiling=max(global_med*1.40,global_q30*2.0,14.0)
                estimate=min(estimate,ceiling)
                basis='soft_peer_feature_blend'; confidence='niedrig'; peer_count=len(soft)
                sim_score=soft[0][0]
            else:
                # Last resort only: category evidence plus the card's explicit positive features.
                raw=anchor*fm
                ceiling=max(global_med*1.35,global_q30*1.8,12.0)
                estimate=min(raw*.78,ceiling)
                basis='defensive_feature_anchor'; confidence='niedrig'; peer_count=0
                sim_score=candidates[0][0] if candidates else 0

        estimate=max(.50,estimate)
        spread=.28 if confidence=='mittel' else .42
        low=max(.50,estimate*(1-spread));high=estimate*(1+spread)
        fresh.append({'card_id':row['card_id'],'estimate':round(estimate,2),'low':round(low,2),'high':round(high,2),
            'currency':summary.get('currency') or 'USD','confidence':confidence,'basis':basis,'peer_count':peer_count,
            'anchor_value':round(anchor,2),'feature_multiplier':round(fm,3),'feature_breakdown':feature_parts,
            'similarity_score':round(float(sim_score),2),'peer_diagnostics':peer_diag,
            'anchor_groups':[{'basis':g[2],'value':round(float(g[0]),2),'count':g[3]} for g in anchor_groups],
            'estimated_at':datetime.now(timezone.utc).isoformat(),'method':'hybrid_feature_model_v9'})

    fresh_map={x['card_id']:x for x in fresh}
    # v7 intentionally replaces stale defensive model versions for still-unverified cards.
    merged=dict(fresh_map)
    for cid,state in states.items():
        if state.get('current_value') is not None: merged.pop(cid,None)
    vals=list(merged.values())
    est_sum=sum(float(x.get('estimate') or 0) for x in vals);low_sum=sum(float(x.get('low') or 0) for x in vals);high_sum=sum(float(x.get('high') or 0) for x in vals)
    verified=float(summary.get('estimated_collection_value') or 0)
    estimate_summary={'status':'estimated' if vals else 'insufficient_peer_basis','verified_total':round(verified,2),
        'estimated_missing_mid':round(est_sum,2),'combined_mid':round(verified+est_sum,2),'combined_low':round(verified+low_sum,2),'combined_high':round(verified+high_sum,2),
        'currency':summary.get('currency') or 'USD','estimated_cards':len(vals),'unresolved_cards':len(unresolved),'method':'hybrid_feature_model_v9',
        'message':f'{len(fresh)} kartenspezifische defensive Schätzungen berechnet. Verified SoldComps bleiben immer vorrangig.'}
    try:snapshot_id=_persist_defensive_estimates(merged,estimate_summary,summary)
    except Exception as exc:
        logger.exception('defensive estimate persistence failed');raise HTTPException(500,f'Defensive estimate persist failed: {type(exc).__name__}: {exc}')
    return {**estimate_summary,'estimates':vals,'new_estimates':len(fresh),'snapshot_id':snapshot_id}

@app.post("/api/v1/collection/market/refresh")
def refresh_collection_market():
    items=[]; page=1
    while True:
        listing=db.list_collection(page=page,page_size=200); batch=listing.get('items',[])
        items.extend(batch)
        if len(batch)<200 or page>=100: break
        page+=1
    if not settings.soldcomps_api_key:
        return {
            'status':'provider_not_configured','cards_checked':len(items),'cards_updated':0,
            'providers':provider_status(),
            'message':'SoldComps ist nicht konfiguriert; bestehende verifizierte Comps und Preis-Historie bleiben unverändert.'
        }

    # V0.20.1: SoldComps scrape calls can each take many seconds. Running one
    # request after another made a collection refresh exceed the browser/proxy
    # request window and the UI only showed "Failed to fetch". Group by the
    # exact SoldComps query (so duplicates still consume only one API credit)
    # and fetch the unique queries concurrently. Database ingestion remains
    # sequential afterwards.
    groups: dict[str, list[tuple[str, dict]]] = {}
    details=[]
    for item in items:
        cid=item.get('id') or item.get('card_identity_id')
        if not cid: continue
        card=db.get_card(cid)
        if not card: continue
        fp=build_fingerprint(card); query=fp.soldcomps_query().strip()
        if not query:
            details.append({'card_id':cid,'status':'insufficient_fingerprint'}); continue
        groups.setdefault(query, []).append((cid, card))

    search_cache: dict[str, dict] = {}
    search_errors: dict[str, dict] = {}
    unique_queries=list(groups.keys())
    requests_used=len(unique_queries)
    max_workers=max(1, min(6, len(unique_queries)))

    def _search(query: str):
        cid, card = groups[query][0]
        fp=build_fingerprint(card)
        return soldcomps_search(fp)

    if unique_queries:
        with ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix='soldcomps') as pool:
            futures={pool.submit(_search, q): q for q in unique_queries}
            for fut in as_completed(futures):
                query=futures[fut]
                try:
                    search_cache[query]=fut.result()
                except SoldCompsError as exc:
                    search_errors[query]={'http_status':exc.status_code,'code':exc.code,'message':str(exc)}
                except Exception as exc:
                    search_errors[query]={'message':f'{type(exc).__name__}: {exc}'}

    cards_updated=0; new_comps=0; errors=[]
    for query, card_rows in groups.items():
        if query in search_errors:
            err=search_errors[query]
            for cid, _card in card_rows:
                errors.append({'card_id':cid,'query':query,**err})
            continue
        provider_result=search_cache.get(query)
        if not provider_result:
            for cid, _card in card_rows:
                errors.append({'card_id':cid,'query':query,'message':'Provider returned no usable response'})
            continue
        for cid, card in card_rows:
            try:
                result=_ingest_soldcomps_search(cid,card,provider_result)
                if result['new_comps']>0: cards_updated += 1
                new_comps += result['new_comps']
                details.append({'card_id':cid,'status':'updated',**{k:result[k] for k in ['query','raw_results','identity_matches','new_comps','new_included_comps']}})
            except Exception as exc:
                errors.append({'card_id':cid,'query':query,'message':f'{type(exc).__name__}: {exc}'})

    collection_snapshot_id=_record_collection_market_snapshot('market_refresh')
    return {
        'status':'updated' if not errors else ('partial' if new_comps or cards_updated else 'provider_error'),
        'cards_checked':len(items),'cards_updated':cards_updated,'new_verified_comps':new_comps,
        'provider_requests_used':requests_used,'unique_queries':len(unique_queries),'parallel_workers':max_workers,
        'providers':provider_status(),'errors':errors,'details':details,'collection_snapshot_id':collection_snapshot_id,
        'message':f'SoldComps: {requests_used} API-Abfragen parallel verarbeitet, {new_comps} neue Vergleichsverkäufe gespeichert, {cards_updated} Karten aktualisiert.'
    }


@app.delete("/api/v1/card-instances/{instance_id}")
def delete_card_instance(instance_id: str):
    """Delete one owned physical card. If it was the last instance, its identity and cascaded market data are removed too."""
    try:
        result=db.delete_card_instance(instance_id)
    except KeyError:
        raise HTTPException(404,"Card instance not found")
    snapshot_id=_record_collection_market_snapshot('manual_delete')
    return {"status":"deleted","collection_snapshot_id":snapshot_id,**result}

@app.get("/api/v1/collection/market-history")
def collection_market_history(limit_per_card: int = Query(5000,ge=1,le=10000)):
    # V0.22: portfolio snapshots are immutable and survive later manual card deletion.
    # For installations upgraded from V0.21 we also build a legacy aggregate from
    # card histories so already collected historical data remains visible.
    durable=[]
    try:
        durable=db.list_collection_market_snapshots(limit=20000)
        durable=[p for p in (durable or []) if (p.get("metadata") or {}).get("reason") != "defensive_estimate_store"]
    except Exception:
        durable=[]
    if durable:
        points=sorted(({**p,"source":"portfolio_snapshot"} for p in durable if p.get("recorded_at")), key=lambda p:str(p.get("recorded_at")))
        return {"history":points,"points":len(points),"cards":None,"durable_points":len(points),"method":"durable_portfolio_snapshots_fast_path"}

    listing=[]; page=1
    while True:
        batch=db.list_collection(page=page,page_size=200).get("items",[])
        listing.extend(batch)
        if len(batch)<200 or page>=100: break
        page+=1
    histories={}
    history_ids=[item.get("id") or item.get("card_identity_id") for item in listing]
    history_ids=[cid for cid in history_ids if cid]
    def _load_history(cid):
        return cid,db.list_market_snapshots(cid,limit=limit_per_card)
    if len(history_ids)>1:
        with ThreadPoolExecutor(max_workers=min(8,len(history_ids))) as pool:
            histories=dict(pool.map(_load_history,history_ids))
    else:
        histories=dict(_load_history(cid) for cid in history_ids)
    moments=sorted({str(p.get("recorded_at")) for h in histories.values() for p in h if p.get("recorded_at") and p.get("value") is not None})
    legacy=[]; latest={}; cursors={cid:0 for cid in histories}
    for moment in moments:
        for cid,h in histories.items():
            idx=cursors[cid]
            while idx < len(h) and str(h[idx].get("recorded_at")) <= moment:
                if h[idx].get("value") is not None: latest[cid]=h[idx]
                idx+=1
            cursors[cid]=idx
        vals=[float(v["value"]) for v in latest.values() if v.get("value") is not None]
        currencies={v.get("currency") for v in latest.values() if v.get("currency")}
        if vals:
            legacy.append({"recorded_at":moment,"value":round(sum(vals),2),"currency":next(iter(currencies)) if len(currencies)==1 else "MIXED","valued_cards":len(vals),"source":"legacy_card_aggregate"})

    # Merge by timestamp; durable snapshots take precedence for the same moment.
    merged={str(p.get('recorded_at')):p for p in legacy if p.get('recorded_at')}
    for p in durable:
        if p.get('recorded_at'):
            merged[str(p.get('recorded_at'))]={**p,"source":"portfolio_snapshot"}
    points=sorted(merged.values(), key=lambda p:str(p.get('recorded_at')))
    return {"history":points,"points":len(points),"cards":len(histories),"durable_points":len(durable),"method":"durable_portfolio_snapshots_plus_legacy_backfill"}

@app.get("/api/v1/export/csv")
def export_csv():
    rows=db.export_rows()
    fields=sorted({k for r in rows for k in r.keys()}) if rows else ["card_identity_id","instance_id"]
    stream=io.StringIO(); writer=csv.DictWriter(stream,fieldnames=fields,extrasaction="ignore"); writer.writeheader()
    for row in rows:
        writer.writerow({k:(json.dumps(v,ensure_ascii=False) if isinstance(v,(list,dict)) else v) for k,v in row.items()})
    data=stream.getvalue().encode("utf-8-sig")
    return StreamingResponse(iter([data]),media_type="text/csv",headers={"Content-Disposition":"attachment; filename=sportscard_collection.csv"})
