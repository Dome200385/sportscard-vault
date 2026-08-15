"""Supabase/Postgres persistence provider for SportsCard Vault V0.14.

The browser never receives SUPABASE_SECRET_KEY. All database access goes through
this trusted FastAPI backend. Tables intentionally mirror the lightweight JSON
shape of the SQLite prototype so the application can switch providers without
changing the public API.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from functools import lru_cache
from uuid import uuid4

from supabase import Client, create_client

from .config import settings


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@lru_cache(maxsize=1)
def client() -> Client:
    if not settings.supabase_ready:
        raise RuntimeError("Supabase is not configured")
    return create_client(settings.supabase_url, settings.supabase_secret_key)


def init_db() -> None:
    # Schema is installed once via supabase/schema_v0_14.sql. A cheap read makes
    # configuration errors visible during Render startup/preflight.
    client().table("card_identities").select("id").limit(1).execute()


def _norm(value):
    if value is None:
        return None
    if isinstance(value, str):
        value = " ".join(value.strip().split())
        return value.upper() if value else None
    if isinstance(value, list):
        return [_norm(v) for v in value]
    return value


def identity_fingerprint(identity: dict) -> str:
    keys = [
        "sport", "league", "season", "release_year", "manufacturer", "brand", "product_line",
        "set_name", "subset_name", "insert_name", "checklist_group", "card_number_normalized",
        "primary_subject_name", "secondary_subject_names", "team_name", "parallel_name", "parallel_family",
        "parallel_color", "variation_name", "variation_code", "refractor_prizm_type", "is_rookie",
        "is_insert", "is_short_print", "is_super_short_print", "is_case_hit", "is_autograph",
        "autograph_type", "is_relic", "relic_type", "is_rpa", "is_booklet", "is_die_cut",
        "is_redemption", "is_serial_numbered", "serial_print_run", "known_print_run",
    ]
    payload = {k: _norm(identity.get(k)) for k in keys}
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _single_data(response):
    data = response.data or []
    return data[0] if data else None


def create_card(identity: dict, instance: dict) -> dict:
    sb = client()
    normalized = identity.get("card_number_normalized") or (identity.get("card_number_printed") or "").strip().upper() or None
    identity = dict(identity)
    identity["card_number_normalized"] = normalized
    fingerprint = identity_fingerprint(identity)
    reused = False

    found = sb.table("card_identities").select("id").eq("identity_fingerprint", fingerprint).limit(1).execute()
    row = _single_data(found)
    if row:
        identity_id = row["id"]
        reused = True
    else:
        identity_id = str(uuid4())
        now = now_iso()
        payload = {
            "id": identity_id,
            "data_json": identity,
            "sport": identity["sport"],
            "season": identity.get("season"),
            "primary_subject_name": identity["primary_subject_name"],
            "card_number_normalized": normalized,
            "product_line": identity.get("product_line"),
            "set_name": identity.get("set_name"),
            "parallel_name": identity.get("parallel_name"),
            "identity_fingerprint": fingerprint,
            "created_at": now,
            "updated_at": now,
        }
        sb.table("card_identities").insert(payload).execute()

    instance_id = str(uuid4())
    now = now_iso()
    sb.table("card_instances").insert({
        "id": instance_id,
        "card_identity_id": identity_id,
        "data_json": instance,
        "created_at": now,
        "updated_at": now,
    }).execute()
    return {
        "card_identity_id": identity_id,
        "instance_id": instance_id,
        "reused_identity": reused,
        "duplicate_count": duplicate_count(identity_id),
    }


def duplicate_count(card_identity_id: str) -> int:
    rows = client().table("card_instances").select("data_json").eq("card_identity_id", card_identity_id).execute().data or []
    total = 0
    for row in rows:
        try:
            total += max(1, int((row.get("data_json") or {}).get("quantity") or 1))
        except Exception:
            total += 1
    return total


def list_collection(q: str | None = None, sport: str | None = None, page: int = 1, page_size: int = 50) -> dict:
    sb = client()
    page = max(page, 1)
    page_size = min(max(page_size, 1), 200)
    query = sb.table("card_identities").select("*", count="exact")
    if sport:
        query = query.ilike("sport", sport)
    if q:
        safe = q.replace(",", " ").strip()
        pattern = f"%{safe}%"
        query = query.or_(
            f"primary_subject_name.ilike.{pattern},card_number_normalized.ilike.{pattern},product_line.ilike.{pattern},set_name.ilike.{pattern},parallel_name.ilike.{pattern}"
        )
    start = (page - 1) * page_size
    response = query.order("created_at", desc=True).range(start, start + page_size - 1).execute()
    rows = response.data or []
    items = []
    for r in rows:
        d = dict(r.get("data_json") or {})
        d["id"] = r["id"]
        # One extra compact count query per page item is acceptable for the
        # current UI (20 rows); later we can replace this with a view/RPC.
        inst = sb.table("card_instances").select("id", count="exact").eq("card_identity_id", r["id"]).limit(1).execute()
        d["instance_rows"] = inst.count or 0
        items.append(d)
    return {"items": items, "page": page, "page_size": page_size, "total": response.count or len(items)}


def get_card(card_id: str) -> dict | None:
    sb = client()
    ident = _single_data(sb.table("card_identities").select("*").eq("id", card_id).limit(1).execute())
    if not ident:
        return None
    instances = sb.table("card_instances").select("*").eq("card_identity_id", card_id).order("created_at").execute().data or []
    comps = sb.table("market_comps").select("*").eq("card_identity_id", card_id).order("created_at", desc=True).execute().data or []
    identity = dict(ident.get("data_json") or {})
    identity["id"] = card_id
    return {
        "identity": identity,
        "instances": [dict(id=r["id"], **(r.get("data_json") or {})) for r in instances],
        "comps": [dict(id=r["id"], **(r.get("data_json") or {})) for r in comps],
    }


def add_comp(card_id: str, comp: dict) -> str:
    sb = client()
    if not _single_data(sb.table("card_identities").select("id").eq("id", card_id).limit(1).execute()):
        raise KeyError(card_id)
    cid = str(uuid4())
    sb.table("market_comps").insert({"id": cid, "card_identity_id": card_id, "data_json": comp, "created_at": now_iso()}).execute()
    return cid



def add_market_snapshot(card_id: str, snapshot: dict) -> str:
    sb=client()
    if not _single_data(sb.table("card_identities").select("id").eq("id",card_id).limit(1).execute()): raise KeyError(card_id)
    sid=str(uuid4()); payload=dict(snapshot); recorded=payload.pop('recorded_at',None) or now_iso()
    sb.table("market_price_snapshots").insert({"id":sid,"card_identity_id":card_id,"data_json":payload,"recorded_at":recorded}).execute()
    return sid

def list_market_snapshots(card_id: str, limit: int = 365) -> list[dict]:
    limit=min(max(int(limit or 365),1),2000)
    rows=client().table("market_price_snapshots").select("*").eq("card_identity_id",card_id).order("recorded_at").limit(limit).execute().data or []
    out=[]
    for r in rows:
        d=dict(r.get('data_json') or {}); d['id']=r['id']; d['recorded_at']=r['recorded_at']; out.append(d)
    return out

def save_scan(front: str, back: str | None, locked_context: dict, output: dict, scan_id: str | None = None) -> str:
    sid = scan_id or str(uuid4())
    client().table("scan_events").insert({
        "id": sid,
        "front_image_path": front,
        "back_image_path": back,
        "locked_context_json": locked_context,
        "raw_structured_output_json": output,
        "final_card_identity_id": None,
        "status": "analyzed",
        "created_at": now_iso(),
        "finalized_at": None,
    }).execute()
    return sid


def _value_of_guess(guess):
    if isinstance(guess, dict) and "value" in guess:
        return guess.get("value")
    return guess


def record_corrections(scan_id: str, identity: dict, instance: dict) -> int:
    sb = client()
    row = _single_data(sb.table("scan_events").select("raw_structured_output_json").eq("id", scan_id).limit(1).execute())
    if not row:
        raise KeyError(scan_id)
    original = row.get("raw_structured_output_json") or {}
    extracted = original.get("extracted", {})
    inst_extracted = original.get("instance_extracted", {})
    inserts = []
    for field, final_value in identity.items():
        suggested = _value_of_guess(extracted.get(field))
        if suggested != final_value:
            inserts.append({
                "id": str(uuid4()), "scan_id": scan_id, "field_name": field,
                "suggested_json": suggested, "final_json": final_value,
                "correction_type": "filled" if suggested in (None, "", []) and final_value not in (None, "", []) else "changed",
                "created_at": now_iso(),
            })
    for field, final_value in instance.items():
        suggested = _value_of_guess(inst_extracted.get(field))
        if suggested != final_value:
            inserts.append({
                "id": str(uuid4()), "scan_id": scan_id, "field_name": f"instance.{field}",
                "suggested_json": suggested, "final_json": final_value,
                "correction_type": "filled" if suggested in (None, "", []) and final_value not in (None, "", []) else "changed",
                "created_at": now_iso(),
            })
    if inserts:
        sb.table("scan_corrections").insert(inserts).execute()
    return len(inserts)


def finalize_scan(scan_id: str, card_identity_id: str, identity: dict | None = None, instance: dict | None = None) -> int:
    corrections = record_corrections(scan_id, identity or {}, instance or {}) if identity is not None else 0
    response = client().table("scan_events").update({
        "final_card_identity_id": card_identity_id, "status": "confirmed", "finalized_at": now_iso()
    }).eq("id", scan_id).execute()
    if not response.data:
        raise KeyError(scan_id)
    return corrections


def list_scans(page: int = 1, page_size: int = 50, status: str | None = None) -> dict:
    sb = client()
    page = max(1, page); page_size = min(max(1, page_size), 200)
    query = sb.table("scan_events").select("*", count="exact")
    if status:
        query = query.eq("status", status)
    start = (page - 1) * page_size
    response = query.order("created_at", desc=True).range(start, start + page_size - 1).execute()
    items = []
    for r in response.data or []:
        raw = r.get("raw_structured_output_json") or {}
        extracted = raw.get("extracted", {})
        items.append({
            "scan_id": r["id"], "status": r["status"], "created_at": r["created_at"], "finalized_at": r.get("finalized_at"),
            "final_card_identity_id": r.get("final_card_identity_id"), "overall_confidence": raw.get("overall_confidence", 0),
            "primary_subject_name": _value_of_guess(extracted.get("primary_subject_name")),
            "product_line": _value_of_guess(extracted.get("product_line")),
            "card_number_printed": _value_of_guess(extracted.get("card_number_printed")),
            "parallel_name": _value_of_guess(extracted.get("parallel_name")),
        })
    return {"items": items, "page": page, "page_size": page_size, "total": response.count or len(items)}


def get_scan(scan_id: str) -> dict | None:
    sb = client()
    row = _single_data(sb.table("scan_events").select("*").eq("id", scan_id).limit(1).execute())
    if not row:
        return None
    corr = sb.table("scan_corrections").select("*").eq("scan_id", scan_id).order("created_at").execute().data or []
    return {
        "scan_id": row["id"], "front_image_path": row.get("front_image_path"), "back_image_path": row.get("back_image_path"),
        "locked_context": row.get("locked_context_json") or {}, "analysis": row.get("raw_structured_output_json") or {},
        "final_card_identity_id": row.get("final_card_identity_id"), "status": row["status"], "created_at": row["created_at"],
        "finalized_at": row.get("finalized_at"),
        "corrections": [{
            "id": c["id"], "field_name": c["field_name"], "suggested": c.get("suggested_json"), "final": c.get("final_json"),
            "correction_type": c["correction_type"], "created_at": c["created_at"]
        } for c in corr],
    }


def correction_stats() -> dict:
    sb = client()
    scans = sb.table("scan_events").select("id,status").execute().data or []
    corr = sb.table("scan_corrections").select("field_name").execute().data or []
    counts = {}
    for c in corr:
        f = c["field_name"]; counts[f] = counts.get(f, 0) + 1
    top = sorted(counts.items(), key=lambda x: (-x[1], x[0]))[:20]
    return {
        "total_scans": len(scans), "confirmed_scans": sum(1 for s in scans if s.get("status") == "confirmed"),
        "total_corrections": len(corr), "top_corrected_fields": [{"field_name": f, "count": n} for f, n in top],
    }


def export_rows() -> list[dict]:
    sb = client()
    identities = sb.table("card_identities").select("id,data_json,created_at").order("created_at").execute().data or []
    instances = sb.table("card_instances").select("id,card_identity_id,data_json").execute().data or []
    by_identity = {}
    for inst in instances:
        by_identity.setdefault(inst["card_identity_id"], []).append(inst)
    out = []
    for ident in identities:
        for inst in by_identity.get(ident["id"], []):
            d = dict(ident.get("data_json") or {})
            d.update({f"owned_{k}": v for k, v in (inst.get("data_json") or {}).items()})
            d["card_identity_id"] = ident["id"]
            d["instance_id"] = inst["id"]
            out.append(d)
    return out
