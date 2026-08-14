import csv
import io
import json
import shutil
import asyncio
import logging
from pathlib import Path
from uuid import uuid4
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, FileResponse
from .config import settings
from . import db
from .schemas import CardCreateRequest, ManualCompIn, ScanResponse, ConfirmScanRequest, ValuationOut
from .pricing import Comp, calculate_valuation
from .recognition import analyze_images
from .catalog import rank_catalog

STATIC_INDEX = Path(__file__).resolve().parent.parent / "static" / "index.html"

logger = logging.getLogger("sportscard-vault")

app = FastAPI(title="SportsCard Vault API", version="0.12.0", description="Detailed sports-card collection API with editable scan review, correction learning data, transparent comp-based valuation, and an offline-first test UI.")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=False, allow_methods=["*"], allow_headers=["*"])

from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_db()
    yield

# Assign lifespan after app construction for compatibility with the existing scaffold.
app.router.lifespan_context = lifespan

@app.get("/health")
def health(): return {"status":"ok","version":"0.12.0","environment":settings.app_env,"recognition":settings.recognition_provider,"pricing_provider":settings.price_provider,"database_provider":settings.database_provider}


@app.get("/", include_in_schema=False)
def test_ui():
    if STATIC_INDEX.exists():
        return FileResponse(STATIC_INDEX)
    return {"name":"SportsCard Vault","status":"ok"}

@app.get("/api/v1/system/preflight")
def system_preflight():
    vision_ready = (settings.recognition_provider or "safe").lower() == "openai" and bool(settings.openai_api_key)
    return {
        "ready_for_real_scans": vision_ready,
        "recognition_provider": settings.recognition_provider,
        "database_provider": settings.database_provider,
        "pricing_provider": settings.price_provider,
        "vision_key_configured": bool(settings.openai_api_key),
        "vision_model": settings.openai_vision_model,
        "notes": [] if vision_ready else ["Für echte automatische Kartenerkennung OPENAI_API_KEY setzen und RECOGNITION_PROVIDER=openai konfigurieren."],
    }

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
    sid=db.save_scan(str(front_path),str(back_path) if back_path else None,locked,output)
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

@app.post("/api/v1/cards/{card_id}/comps/manual")
def manual_comp(card_id: str, payload: ManualCompIn):
    try: cid=db.add_comp(card_id,payload.model_dump(mode="json"))
    except KeyError: raise HTTPException(404,"Card not found")
    return {"comp_id":cid}

@app.get("/api/v1/cards/{card_id}/valuation", response_model=ValuationOut)
def valuation(card_id: str):
    card=db.get_card(card_id)
    if not card: raise HTTPException(404,"Card not found")
    comps=[Comp(float(c["price"]),c["currency"],c.get("raw_or_graded","raw"),c.get("included_in_valuation",True)) for c in card["comps"]]
    result=calculate_valuation(comps,settings.min_reliable_comps)
    return ValuationOut(**result.__dict__)

@app.get("/api/v1/export/csv")
def export_csv():
    rows=db.export_rows()
    fields=sorted({k for r in rows for k in r.keys()}) if rows else ["card_identity_id","instance_id"]
    stream=io.StringIO(); writer=csv.DictWriter(stream,fieldnames=fields,extrasaction="ignore"); writer.writeheader()
    for row in rows:
        writer.writerow({k:(json.dumps(v,ensure_ascii=False) if isinstance(v,(list,dict)) else v) for k,v in row.items()})
    data=stream.getvalue().encode("utf-8-sig")
    return StreamingResponse(iter([data]),media_type="text/csv",headers={"Content-Disposition":"attachment; filename=sportscard_collection.csv"})
