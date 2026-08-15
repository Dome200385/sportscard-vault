"""Native Postgres persistence provider for SportsCard Vault V0.15.4.

Uses SUPABASE_DATABASE_URL (prefer Supavisor Session pooler on Render) and keeps
all card/scanner data in the project's persistent Postgres database. This path
intentionally does not depend on the Supabase REST hostname, which is not
resolving from the current Render environment.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from uuid import UUID, uuid4

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from .config import settings

APP_OWNER_ID = UUID("00000000-0000-0000-0000-000000000001")


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def connect():
    if not settings.supabase_database_url:
        raise RuntimeError("SUPABASE_DATABASE_URL ist nicht konfiguriert")
    return psycopg.connect(settings.supabase_database_url, connect_timeout=8, row_factory=dict_row)


MIGRATION_SQL = r'''
create extension if not exists "pgcrypto";

alter table if exists public.card_identities add column if not exists data_json jsonb not null default '{}'::jsonb;
alter table if exists public.card_identities add column if not exists identity_fingerprint text;
create unique index if not exists uq_card_identities_identity_fingerprint on public.card_identities(identity_fingerprint) where identity_fingerprint is not null;

alter table if exists public.card_instances add column if not exists data_json jsonb not null default '{}'::jsonb;
alter table if exists public.market_comps add column if not exists data_json jsonb not null default '{}'::jsonb;

alter table if exists public.scan_events add column if not exists locked_context_json jsonb not null default '{}'::jsonb;
alter table if exists public.scan_events add column if not exists raw_structured_output_json jsonb;
alter table if exists public.scan_events add column if not exists status text not null default 'analyzed';
alter table if exists public.scan_events add column if not exists finalized_at timestamptz;

create table if not exists public.scan_corrections (
  id uuid primary key default gen_random_uuid(),
  scan_id uuid not null references public.scan_events(id) on delete cascade,
  field_name text not null,
  suggested_json jsonb,
  final_json jsonb,
  correction_type text not null,
  created_at timestamptz not null default now()
);
create index if not exists idx_scan_corrections_scan on public.scan_corrections(scan_id);

create table if not exists public.card_image_blobs (
  id uuid primary key default gen_random_uuid(),
  content_type text not null default 'image/jpeg',
  original_name text,
  data bytea not null,
  byte_size integer not null,
  sha256 text not null,
  created_at timestamptz not null default now()
);
create index if not exists idx_card_image_blobs_sha256 on public.card_image_blobs(sha256);

create table if not exists public.market_price_snapshots (
  id uuid primary key default gen_random_uuid(),
  card_identity_id uuid not null references public.card_identities(id) on delete cascade,
  value numeric(14,2) not null,
  currency text not null,
  source text not null,
  confidence numeric(5,4),
  snapshot_type text not null default 'verified_comps',
  comp_count integer not null default 0,
  metadata_json jsonb not null default '{}'::jsonb,
  recorded_at timestamptz not null default now()
);
create index if not exists idx_market_price_snapshots_card_time on public.market_price_snapshots(card_identity_id, recorded_at desc);
'''


def init_db() -> None:
    """Make the legacy schema compatible, then verify a real read."""
    with connect() as con:
        with con.cursor() as cur:
            cur.execute(MIGRATION_SQL)
            cur.execute("select id from public.card_identities limit 1")
        con.commit()


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


def _identity_columns(identity: dict, fingerprint: str) -> dict:
    return {
        "owner_user_id": APP_OWNER_ID,
        "sport": identity.get("sport") or "Unknown",
        "league": identity.get("league"),
        "season": identity.get("season"),
        "release_year": identity.get("release_year"),
        "manufacturer": identity.get("manufacturer"),
        "brand": identity.get("brand"),
        "product_line": identity.get("product_line"),
        "set_name": identity.get("set_name"),
        "subset_name": identity.get("subset_name"),
        "insert_name": identity.get("insert_name"),
        "card_number_printed": identity.get("card_number_printed"),
        "card_number_normalized": identity.get("card_number_normalized"),
        "primary_subject_name": identity.get("primary_subject_name") or "Unknown",
        "secondary_subject_names": Jsonb(identity.get("secondary_subject_names") or []),
        "team_name": identity.get("team_name"),
        "parallel_name": identity.get("parallel_name"),
        "variation_name": identity.get("variation_name"),
        "is_rookie": bool(identity.get("is_rookie")),
        "rookie_label_text": identity.get("rookie_label_text"),
        "is_insert": bool(identity.get("is_insert")),
        "is_short_print": bool(identity.get("is_short_print")),
        "is_super_short_print": bool(identity.get("is_super_short_print")),
        "is_case_hit": bool(identity.get("is_case_hit")),
        "is_autograph": bool(identity.get("is_autograph")),
        "autograph_type": identity.get("autograph_type"),
        "is_relic": bool(identity.get("is_relic")),
        "relic_type": identity.get("relic_type"),
        "is_rpa": bool(identity.get("is_rpa")),
        "is_serial_numbered": bool(identity.get("is_serial_numbered")),
        "serial_print_run": identity.get("serial_print_run"),
        "known_print_run": identity.get("known_print_run"),
        "recognition_status": "user_confirmed",
        "overall_confidence": identity.get("overall_confidence"),
        "field_confidences": Jsonb(identity.get("field_confidences") or {}),
        "uncertain_fields": Jsonb(identity.get("uncertain_fields") or []),
        "user_corrections": Jsonb(identity.get("user_corrections") or {}),
        "data_json": Jsonb(identity),
        "identity_fingerprint": fingerprint,
    }


def _instance_columns(instance: dict, identity_id: str) -> dict:
    return {
        "owner_user_id": APP_OWNER_ID,
        "card_identity_id": identity_id,
        "quantity": max(1, int(instance.get("quantity") or 1)),
        "raw_or_graded": instance.get("raw_or_graded") or "raw",
        "raw_condition": instance.get("raw_condition"),
        "grading_company": instance.get("grading_company"),
        "grade_numeric": instance.get("grade_numeric"),
        "grade_label": instance.get("grade_label"),
        "subgrades": Jsonb(instance.get("subgrades") or {}),
        "cert_number": instance.get("cert_number"),
        "serial_number_actual": instance.get("serial_number_actual"),
        "autograph_grade": instance.get("autograph_grade"),
        "acquired_date": instance.get("acquired_date"),
        "acquired_price": instance.get("acquired_price"),
        "acquired_currency": instance.get("acquired_currency"),
        "acquired_from": instance.get("acquired_from"),
        "storage_location": instance.get("storage_location"),
        "personal_tags": Jsonb(instance.get("personal_tags") or []),
        "notes": instance.get("notes"),
        "front_image_path": instance.get("front_image_path"),
        "back_image_path": instance.get("back_image_path"),
        "for_sale": bool(instance.get("for_sale")),
        "asking_price": instance.get("asking_price"),
        "favorite": bool(instance.get("favorite")),
        "data_json": Jsonb(instance),
    }


def _insert(cur, table: str, payload: dict, returning: str = "id"):
    cols = list(payload)
    sql = f"insert into public.{table} ({','.join(cols)}) values ({','.join(['%s']*len(cols))}) returning {returning}"
    cur.execute(sql, list(payload.values()))
    return cur.fetchone()[returning]


def create_card(identity: dict, instance: dict) -> dict:
    identity = dict(identity)
    normalized = identity.get("card_number_normalized") or (identity.get("card_number_printed") or "").strip().upper() or None
    identity["card_number_normalized"] = normalized
    fp = identity_fingerprint(identity)
    with connect() as con:
        with con.cursor() as cur:
            cur.execute("select id from public.card_identities where identity_fingerprint=%s limit 1", (fp,))
            found = cur.fetchone()
            reused = bool(found)
            if found:
                identity_id = str(found["id"])
            else:
                payload = _identity_columns(identity, fp)
                identity_id = str(_insert(cur, "card_identities", payload))
            instance_id = str(_insert(cur, "card_instances", _instance_columns(instance, identity_id)))
        con.commit()
    return {"card_identity_id": identity_id, "instance_id": instance_id, "reused_identity": reused, "duplicate_count": duplicate_count(identity_id)}


def duplicate_count(card_identity_id: str) -> int:
    with connect() as con, con.cursor() as cur:
        cur.execute("select coalesce(sum(quantity),0) as n from public.card_instances where card_identity_id=%s", (card_identity_id,))
        return int(cur.fetchone()["n"] or 0)


def list_collection(q: str | None = None, sport: str | None = None, page: int = 1, page_size: int = 50) -> dict:
    page=max(page,1); page_size=min(max(page_size,1),200); offset=(page-1)*page_size
    where=[]; params=[]
    if sport:
        where.append("lower(sport)=lower(%s)"); params.append(sport)
    if q:
        where.append("(primary_subject_name ilike %s or card_number_normalized ilike %s or product_line ilike %s or set_name ilike %s or parallel_name ilike %s)")
        params.extend([f"%{q}%"]*5)
    clause = " where " + " and ".join(where) if where else ""
    with connect() as con, con.cursor() as cur:
        cur.execute(f"select count(*) as n from public.card_identities{clause}", params)
        total=int(cur.fetchone()["n"])
        cur.execute(f"select id,data_json from public.card_identities{clause} order by created_at desc limit %s offset %s", params+[page_size,offset])
        rows=cur.fetchall()
        items=[]
        for r in rows:
            d=dict(r["data_json"] or {}); d["id"]=str(r["id"])
            cur.execute("select count(*) as n from public.card_instances where card_identity_id=%s", (r["id"],))
            d["instance_rows"]=int(cur.fetchone()["n"])
            items.append(d)
    return {"items":items,"page":page,"page_size":page_size,"total":total}


def get_card(card_id: str) -> dict | None:
    with connect() as con, con.cursor() as cur:
        cur.execute("select id,data_json from public.card_identities where id=%s limit 1", (card_id,)); ident=cur.fetchone()
        if not ident: return None
        cur.execute("select id,data_json from public.card_instances where card_identity_id=%s order by created_at", (card_id,)); inst=cur.fetchall()
        cur.execute("select id,data_json from public.market_comps where card_identity_id=%s order by created_at desc", (card_id,)); comps=cur.fetchall()
    identity=dict(ident["data_json"] or {}); identity["id"]=str(ident["id"])
    return {"identity":identity,"instances":[dict(id=str(r["id"]), **(r["data_json"] or {})) for r in inst],"comps":[dict(id=str(r["id"]), **(r["data_json"] or {})) for r in comps]}


def add_comp(card_id: str, comp: dict) -> str:
    with connect() as con, con.cursor() as cur:
        cur.execute("select 1 from public.card_identities where id=%s", (card_id,))
        if not cur.fetchone(): raise KeyError(card_id)
        payload={
            "owner_user_id":APP_OWNER_ID,"card_identity_id":card_id,"source":comp.get("source") or "manual",
            "source_item_id":comp.get("source_item_id"),"source_url":comp.get("source_url"),"sale_type":comp.get("sale_type"),
            "sold_at":comp.get("sold_at"),"price":comp.get("price"),"currency":comp.get("currency") or "USD",
            "shipping_price":comp.get("shipping_price"),"all_in_price":comp.get("all_in_price"),"raw_or_graded":comp.get("raw_or_graded"),
            "grading_company":comp.get("grading_company"),"grade_numeric":comp.get("grade_numeric"),"title_raw":comp.get("title_raw"),
            "matched_identity_confidence":comp.get("matched_identity_confidence"),"included_in_valuation":comp.get("included_in_valuation",True),
            "exclusion_reason":comp.get("exclusion_reason"),"data_json":Jsonb(comp),
        }
        cid=str(_insert(cur,"market_comps",payload)); con.commit(); return cid



def add_market_snapshot(card_id: str, snapshot: dict) -> str:
    sid=str(uuid4())
    with connect() as con, con.cursor() as cur:
        cur.execute("select 1 from public.card_identities where id=%s", (card_id,))
        if not cur.fetchone():
            raise KeyError(card_id)
        cur.execute(
            "insert into public.market_price_snapshots "
            "(id,card_identity_id,value,currency,source,confidence,snapshot_type,comp_count,metadata_json,recorded_at) "
            "values (%s,%s,%s,%s,%s,%s,%s,%s,%s,coalesce(%s::timestamptz,now()))",
            (sid,card_id,float(snapshot['value']),snapshot.get('currency') or 'USD',snapshot.get('source') or 'unknown',
             snapshot.get('confidence'),snapshot.get('snapshot_type') or 'verified_comps',int(snapshot.get('comp_count') or 0),
             Jsonb(snapshot.get('metadata') or {}),snapshot.get('recorded_at'))
        )
        con.commit()
    return sid


def list_market_snapshots(card_id: str, limit: int = 365) -> list[dict]:
    limit=min(max(int(limit or 365),1),2000)
    with connect() as con, con.cursor() as cur:
        cur.execute(
            "select id,value,currency,source,confidence,snapshot_type,comp_count,metadata_json,recorded_at "
            "from public.market_price_snapshots where card_identity_id=%s order by recorded_at asc limit %s",
            (card_id,limit)
        )
        rows=cur.fetchall()
    return [{
        'id':str(r['id']),'value':float(r['value']),'currency':r['currency'],'source':r['source'],
        'confidence':float(r['confidence']) if r['confidence'] is not None else None,'snapshot_type':r['snapshot_type'],
        'comp_count':int(r['comp_count'] or 0),'metadata':r['metadata_json'] or {},'recorded_at':r['recorded_at']
    } for r in rows]

def save_scan(front: str, back: str | None, locked_context: dict, output: dict, scan_id: str | None = None) -> str:
    sid=scan_id or str(uuid4())
    with connect() as con, con.cursor() as cur:
        cur.execute("""insert into public.scan_events
            (id,owner_user_id,front_image_path,back_image_path,model_name,raw_structured_output,locked_context_json,raw_structured_output_json,status)
            values (%s,%s,%s,%s,%s,%s,%s,%s,'analyzed')""",
            (sid,APP_OWNER_ID,front,back,settings.openai_vision_model,Jsonb(output),Jsonb(locked_context),Jsonb(output)))
        con.commit()
    return sid


def _value_of_guess(guess):
    return guess.get("value") if isinstance(guess,dict) and "value" in guess else guess


def record_corrections(scan_id: str, identity: dict, instance: dict) -> int:
    with connect() as con, con.cursor() as cur:
        cur.execute("select raw_structured_output_json from public.scan_events where id=%s", (scan_id,)); row=cur.fetchone()
        if not row: raise KeyError(scan_id)
        original=row["raw_structured_output_json"] or {}; extracted=original.get("extracted",{}); inst_extracted=original.get("instance_extracted",{})
        inserts=[]
        for field, final_value in identity.items():
            suggested=_value_of_guess(extracted.get(field))
            if suggested != final_value: inserts.append((field,suggested,final_value,"filled" if suggested in (None,"",[]) and final_value not in (None,"",[]) else "changed"))
        for field, final_value in instance.items():
            suggested=_value_of_guess(inst_extracted.get(field))
            if suggested != final_value: inserts.append((f"instance.{field}",suggested,final_value,"filled" if suggested in (None,"",[]) and final_value not in (None,"",[]) else "changed"))
        for field,suggested,final,ctype in inserts:
            cur.execute("insert into public.scan_corrections (id,scan_id,field_name,suggested_json,final_json,correction_type) values (%s,%s,%s,%s,%s,%s)",
                        (str(uuid4()),scan_id,field,Jsonb(suggested),Jsonb(final),ctype))
        con.commit(); return len(inserts)


def finalize_scan(scan_id: str, card_identity_id: str, identity: dict | None = None, instance: dict | None = None) -> int:
    corrections=record_corrections(scan_id,identity or {},instance or {}) if identity is not None else 0
    with connect() as con, con.cursor() as cur:
        cur.execute("update public.scan_events set final_card_identity_id=%s,status='confirmed',finalized_at=now() where id=%s returning id",(card_identity_id,scan_id))
        if not cur.fetchone(): raise KeyError(scan_id)
        con.commit()
    return corrections


def list_scans(page: int=1,page_size: int=50,status: str|None=None)->dict:
    page=max(1,page); page_size=min(max(1,page_size),200); offset=(page-1)*page_size
    clause=" where status=%s" if status else ""; params=[status] if status else []
    with connect() as con, con.cursor() as cur:
        cur.execute(f"select count(*) as n from public.scan_events{clause}",params); total=int(cur.fetchone()["n"])
        cur.execute(f"select * from public.scan_events{clause} order by created_at desc limit %s offset %s",params+[page_size,offset]); rows=cur.fetchall()
    items=[]
    for r in rows:
        raw=r["raw_structured_output_json"] or {}; ex=raw.get("extracted",{})
        items.append({"scan_id":str(r["id"]),"status":r["status"],"created_at":r["created_at"],"finalized_at":r["finalized_at"],"final_card_identity_id":str(r["final_card_identity_id"]) if r["final_card_identity_id"] else None,"overall_confidence":raw.get("overall_confidence",0),"primary_subject_name":_value_of_guess(ex.get("primary_subject_name")),"product_line":_value_of_guess(ex.get("product_line")),"card_number_printed":_value_of_guess(ex.get("card_number_printed")),"parallel_name":_value_of_guess(ex.get("parallel_name"))})
    return {"items":items,"page":page,"page_size":page_size,"total":total}


def get_scan(scan_id: str)->dict|None:
    with connect() as con, con.cursor() as cur:
        cur.execute("select * from public.scan_events where id=%s",(scan_id,)); r=cur.fetchone()
        if not r: return None
        cur.execute("select * from public.scan_corrections where scan_id=%s order by created_at",(scan_id,)); corr=cur.fetchall()
    return {"scan_id":str(r["id"]),"front_image_path":r["front_image_path"],"back_image_path":r["back_image_path"],"locked_context":r["locked_context_json"] or {},"analysis":r["raw_structured_output_json"] or {},"final_card_identity_id":str(r["final_card_identity_id"]) if r["final_card_identity_id"] else None,"status":r["status"],"created_at":r["created_at"],"finalized_at":r["finalized_at"],"corrections":[{"id":str(c["id"]),"field_name":c["field_name"],"suggested":c["suggested_json"],"final":c["final_json"],"correction_type":c["correction_type"],"created_at":c["created_at"]} for c in corr]}


def correction_stats()->dict:
    with connect() as con, con.cursor() as cur:
        cur.execute("select count(*) n, count(*) filter (where status='confirmed') confirmed from public.scan_events"); s=cur.fetchone()
        cur.execute("select field_name,count(*) n from public.scan_corrections group by field_name order by n desc,field_name limit 20"); rows=cur.fetchall()
        cur.execute("select count(*) n from public.scan_corrections"); n=int(cur.fetchone()["n"])
    return {"total_scans":int(s["n"]),"confirmed_scans":int(s["confirmed"]),"total_corrections":n,"top_corrected_fields":[{"field_name":r["field_name"],"count":int(r["n"])} for r in rows]}


def export_rows()->list[dict]:
    with connect() as con, con.cursor() as cur:
        cur.execute("select id,data_json,created_at from public.card_identities order by created_at"); ids=cur.fetchall()
        cur.execute("select id,card_identity_id,data_json from public.card_instances"); instances=cur.fetchall()
    by={}
    for i in instances: by.setdefault(i["card_identity_id"],[]).append(i)
    out=[]
    for ident in ids:
        for inst in by.get(ident["id"],[]):
            d=dict(ident["data_json"] or {}); d.update({f"owned_{k}":v for k,v in (inst["data_json"] or {}).items()}); d["card_identity_id"]=str(ident["id"]); d["instance_id"]=str(inst["id"]); out.append(d)
    return out


def persist_image_blob(data: bytes, content_type: str = "image/jpeg", original_name: str | None = None) -> str:
    """Persist every upload as a fresh blob and verify it through a new connection.

    V0.15.15 deliberately disables SHA-based blob reuse. A scan must never inherit
    an older pgimg id whose row may have been created by a previous broken build.
    The UUID is generated application-side, inserted explicitly, committed, and
    then re-read using a UUID-typed predicate.
    """
    digest = hashlib.sha256(data).hexdigest()
    image_uuid = uuid4()
    with connect() as con:
        with con.cursor() as cur:
            cur.execute(
                "insert into public.card_image_blobs "
                "(id, content_type, original_name, data, byte_size, sha256) "
                "values (%s,%s,%s,%s,%s,%s) returning id",
                (image_uuid, content_type or "application/octet-stream", original_name, data, len(data), digest),
            )
            returned = cur.fetchone()
            if not returned or str(returned["id"]) != str(image_uuid):
                raise RuntimeError("Postgres image insert did not return the requested UUID")
        con.commit()

    check = get_image_blob(str(image_uuid))
    if not check:
        raise RuntimeError(f"Postgres image write verification failed: row {image_uuid} not readable")
    if int(check.get("byte_size") or -1) != len(data):
        raise RuntimeError(f"Postgres image write verification failed: byte size mismatch for {image_uuid}")
    if str(check.get("sha256") or "") != digest:
        raise RuntimeError(f"Postgres image write verification failed: sha256 mismatch for {image_uuid}")
    return str(image_uuid)


def get_image_blob(image_id: str) -> dict | None:
    image_id = (image_id or "").strip()
    if image_id.startswith("pgimg://"):
        image_id = image_id.split("://", 1)[1]
    try:
        image_uuid = UUID(image_id)
    except Exception:
        return None
    with connect() as con, con.cursor() as cur:
        cur.execute(
            "select id, content_type, original_name, data, byte_size, sha256, created_at "
            "from public.card_image_blobs where id=%s limit 1",
            (image_uuid,),
        )
        row = cur.fetchone()
        return dict(row) if row else None


def image_blob_meta(image_id: str) -> dict:
    """Safe diagnostics for one blob; never returns the binary payload."""
    row = get_image_blob(image_id)
    if not row:
        return {"exists": False, "image_id": (image_id or "").replace("pgimg://", "")}
    return {
        "exists": True,
        "image_id": str(row["id"]),
        "content_type": row.get("content_type"),
        "original_name": row.get("original_name"),
        "byte_size": int(row.get("byte_size") or 0),
        "sha256": row.get("sha256"),
        "created_at": row.get("created_at").isoformat() if row.get("created_at") else None,
    }


def image_blob_ready() -> tuple[bool, str | None]:
    """Prove that the fallback can write, re-read and delete a blob.

    Merely checking that the table exists produced a false green state in
    V0.15.13. This probe verifies the exact persistence path used by scans.
    """
    if not settings.supabase_database_url:
        return False, "SUPABASE_DATABASE_URL fehlt"
    probe_id = None
    payload = b"sportscard-vault-image-probe-v0.15.15"
    try:
        digest = hashlib.sha256(payload).hexdigest()
        with connect() as con, con.cursor() as cur:
            cur.execute(
                "insert into public.card_image_blobs (content_type, original_name, data, byte_size, sha256) "
                "values (%s,%s,%s,%s,%s) returning id",
                ("application/octet-stream", "_health_probe.bin", payload, len(payload), digest),
            )
            probe_id = str(cur.fetchone()["id"])
            con.commit()
        row = get_image_blob(probe_id)
        if not row or bytes(row["data"]) != payload:
            return False, "Postgres image blob re-read failed"
        return True, None
    except Exception as exc:
        return False, f"Postgres image blob probe failed: {type(exc).__name__}: {exc}"
    finally:
        if probe_id:
            try:
                with connect() as con, con.cursor() as cur:
                    cur.execute("delete from public.card_image_blobs where id::text=%s", (probe_id,))
                    con.commit()
            except Exception:
                pass
