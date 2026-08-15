import csv
import io
import json
import shutil
import asyncio
import logging
from pathlib import Path
from uuid import uuid4
from datetime import datetime, timezone, timedelta
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, FileResponse, Response
from .config import settings
from . import db
from .schemas import CardCreateRequest, ManualCompIn, ScanResponse, ConfirmScanRequest, AutoConfirmScanRequest, ValuationOut, CardIdentityIn, OwnedInstanceIn
from .pricing import Comp, calculate_valuation
from .recognition import analyze_images
from .catalog import rank_catalog
from .image_storage import persist_image, signed_url, storage_ready, storage_diagnostics
from . import postgres_probe
from .market_providers import build_fingerprint, provider_status, score_candidate

STATIC_INDEX = Path(__file__).resolve().parent.parent / "static" / "index.html"

logger = logging.getLogger("sportscard-vault")

app = FastAPI(title="SportsCard Vault API", version="0.19.1", description="Detailed sports-card collection API with editable scan review, correction learning data, transparent comp-based valuation, and an offline-first test UI.")
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
    yield

# Assign lifespan after app construction for compatibility with the existing scaffold.
app.router.lifespan_context = lifespan

@app.get("/health")
def health(): return {"status":"ok","version":"0.19.1","environment":settings.app_env,"recognition":settings.recognition_provider,"pricing_provider":settings.price_provider,"database_provider":settings.database_provider}


def _serve_test_ui():
    if STATIC_INDEX.exists():
        return FileResponse(STATIC_INDEX)
    return {"name":"SportsCard Vault","status":"ok"}

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
def image_blob(image_id: str):
    """Serve an image persisted in Postgres fallback storage."""
    # Accept a copied pgimg:// reference as well as the bare UUID.
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
    return Response(
        content=bytes(row["data"]),
        media_type=row.get("content_type") or "application/octet-stream",
        headers={"Cache-Control": "private, max-age=3600", "X-Image-Storage": "postgres"},
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


def _card_market_state(card_id: str, history_limit: int = 365) -> dict:
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
    # Avoid duplicate snapshots when the value/source did not actually change within the same update cycle.
    if latest and latest.get('value') is not None and abs(float(latest['value'])-float(state['current_value'])) < 0.005 and (latest.get('source') or '')==source:
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
def card_market_history(card_id: str, limit: int = Query(365,ge=1,le=2000)):
    try: state=_card_market_state(card_id,history_limit=limit)
    except KeyError: raise HTTPException(404,"Card not found")
    return {k:state[k] for k in ['card_id','current_value','currency','source','confidence','last_updated','change_7d_pct','change_30d_pct','history']}



@app.get("/api/v1/market/providers")
def market_provider_status():
    return {
        "providers": provider_status(),
        "automatic_provider_configured": False,
        "policy": "No AI-invented prices. Provider estimates and verified sold comps remain separate.",
    }

@app.get("/api/v1/cards/{card_id}/market-fingerprint")
def card_market_fingerprint(card_id: str):
    card=db.get_card(card_id)
    if not card: raise HTTPException(404,"Card not found")
    fp=build_fingerprint(card)
    return {
        "card_id": card_id,
        "fingerprint": fp.as_dict(),
        "matching_threshold": 0.82,
        "hard_identity_fields": ["subject","card_number","parallel_name"],
    }

@app.post("/api/v1/cards/{card_id}/market/refresh")
def refresh_card_market(card_id: str):
    card=db.get_card(card_id)
    if not card: raise HTTPException(404,"Card not found")
    fp=build_fingerprint(card)
    state=_card_market_state(card_id)
    return {
        "card_id": card_id,
        "status": "provider_not_configured",
        "fingerprint": fp.as_dict(),
        "providers": provider_status(),
        "new_verified_comps": 0,
        "new_provider_estimates": 0,
        "current_market": {k:state[k] for k in ['current_value','currency','source','confidence','last_updated','change_7d_pct','change_30d_pct']},
        "message": "Automatische Marktquelle ist vorbereitet, aber noch nicht aktiviert. Es wurden keine Preise erfunden oder aus aktiven Angeboten abgeleitet.",
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

@app.get("/api/v1/collection/market-summary")
def collection_market_summary():
    items=[]; page=1; page_size=200
    while True:
        listing=db.list_collection(page=page,page_size=page_size)
        batch=listing.get("items",[]) if isinstance(listing,dict) else []
        items.extend(batch)
        if len(batch) < page_size: break
        page += 1
        if page > 100: break
    valued=0; total=0.0; currencies=set(); missing=0; comp_count=0; cards={}
    current_by_card={}; base7_by_card={}; base30_by_card={}; latest_dates=[]
    for item in items:
        cid=item.get("id") or item.get("card_identity_id")
        if not cid: continue
        try: state=_card_market_state(cid,history_limit=365)
        except KeyError: continue
        cards[cid]={k:state[k] for k in ['current_value','currency','source','confidence','last_updated','change_7d_pct','change_30d_pct','included_comp_count','reliable']}
        cards[cid]['history_points']=len(state['history'])
        comp_count += state['included_comp_count']
        if state['last_updated']: latest_dates.append(state['last_updated'])
        if state['current_value'] is None:
            missing += 1; continue
        current=float(state['current_value']); total += current; valued += 1
        if state['currency']: currencies.add(state['currency'])
        current_by_card[cid]=current
        base7=_baseline_value(state['history'],7); base30=_baseline_value(state['history'],30)
        if base7 is not None: base7_by_card[cid]=base7
        if base30 is not None: base30_by_card[cid]=base30
    currency=next(iter(currencies)) if len(currencies)==1 else ("MIXED" if currencies else None)
    considered=len(items)
    base7_total=sum(base7_by_card.values()) if base7_by_card and set(current_by_card).issubset(set(base7_by_card)) else None
    base30_total=sum(base30_by_card.values()) if base30_by_card and set(current_by_card).issubset(set(base30_by_card)) else None
    return {
        "cards_considered":considered,"valued_cards":valued,"cards_without_comps":missing,
        "included_comp_count":comp_count,"coverage_pct":round((valued/considered*100),1) if considered else 0.0,
        "estimated_collection_value":round(total,2) if valued else None,"currency":currency,
        "change_7d_pct":_pct_change(total,base7_total),"change_30d_pct":_pct_change(total,base30_total),
        "last_market_update":max(latest_dates) if latest_dates else None,"cards":cards,
        "method":"sum_of_current_verified_comp_medians_or_provider_snapshots","status":"valued" if valued else "waiting_for_comps"
    }

@app.post("/api/v1/collection/market/refresh")
def refresh_collection_market():
    items=[]; page=1
    while True:
        listing=db.list_collection(page=page,page_size=200); batch=listing.get('items',[])
        items.extend(batch)
        if len(batch)<200 or page>=100: break
        page+=1
    return {
        'status':'provider_not_configured','cards_checked':len(items),'cards_updated':0,
        'providers':provider_status(),
        'message':'Sammlung geprüft. Noch keine automatische Marktquelle aktiviert; bestehende verifizierte Comps und Preis-Historie bleiben unverändert.'
    }

@app.get("/api/v1/export/csv")
def export_csv():
    rows=db.export_rows()
    fields=sorted({k for r in rows for k in r.keys()}) if rows else ["card_identity_id","instance_id"]
    stream=io.StringIO(); writer=csv.DictWriter(stream,fieldnames=fields,extrasaction="ignore"); writer.writeheader()
    for row in rows:
        writer.writerow({k:(json.dumps(v,ensure_ascii=False) if isinstance(v,(list,dict)) else v) for k,v in row.items()})
    data=stream.getvalue().encode("utf-8-sig")
    return StreamingResponse(iter([data]),media_type="text/csv",headers={"Content-Disposition":"attachment; filename=sportscard_collection.csv"})
