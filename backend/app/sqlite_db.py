import json
import sqlite3
import hashlib
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4
from .config import settings

SCHEMA = """
PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS card_identities (
  id TEXT PRIMARY KEY,
  data_json TEXT NOT NULL,
  sport TEXT NOT NULL,
  season TEXT,
  primary_subject_name TEXT NOT NULL,
  card_number_normalized TEXT,
  product_line TEXT,
  set_name TEXT,
  parallel_name TEXT,
  identity_fingerprint TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS card_instances (
  id TEXT PRIMARY KEY,
  card_identity_id TEXT NOT NULL REFERENCES card_identities(id) ON DELETE CASCADE,
  data_json TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS market_comps (
  id TEXT PRIMARY KEY,
  card_identity_id TEXT NOT NULL REFERENCES card_identities(id) ON DELETE CASCADE,
  data_json TEXT NOT NULL,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS market_price_snapshots (
  id TEXT PRIMARY KEY,
  card_identity_id TEXT NOT NULL REFERENCES card_identities(id) ON DELETE CASCADE,
  data_json TEXT NOT NULL,
  recorded_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS scan_events (
  id TEXT PRIMARY KEY,
  front_image_path TEXT,
  back_image_path TEXT,
  locked_context_json TEXT,
  raw_structured_output_json TEXT,
  final_card_identity_id TEXT,
  status TEXT NOT NULL DEFAULT 'analyzed',
  created_at TEXT NOT NULL,
  finalized_at TEXT
);
CREATE TABLE IF NOT EXISTS scan_corrections (
  id TEXT PRIMARY KEY,
  scan_id TEXT NOT NULL REFERENCES scan_events(id) ON DELETE CASCADE,
  field_name TEXT NOT NULL,
  suggested_json TEXT,
  final_json TEXT,
  correction_type TEXT NOT NULL,
  created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_identity_search ON card_identities(sport, season, primary_subject_name, card_number_normalized);
CREATE INDEX IF NOT EXISTS idx_instances_identity ON card_instances(card_identity_id);
CREATE INDEX IF NOT EXISTS idx_comps_identity ON market_comps(card_identity_id);
CREATE INDEX IF NOT EXISTS idx_market_snapshots_card_time ON market_price_snapshots(card_identity_id, recorded_at);
CREATE INDEX IF NOT EXISTS idx_scan_created ON scan_events(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_scan_corrections_scan ON scan_corrections(scan_id);
"""

@contextmanager
def connect():
    con = sqlite3.connect(settings.database_path)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    try:
        yield con
        con.commit()
    finally:
        con.close()

def _ensure_column(con: sqlite3.Connection, table: str, column: str, ddl: str) -> None:
    columns = {r[1] for r in con.execute(f"PRAGMA table_info({table})").fetchall()}
    if column not in columns:
        con.execute(f"ALTER TABLE {table} ADD COLUMN {ddl}")

def init_db() -> None:
    Path(settings.database_path).parent.mkdir(parents=True, exist_ok=True)
    with connect() as con:
        con.executescript(SCHEMA)
        # Lightweight migration path from V0.2 SQLite databases.
        _ensure_column(con, "scan_events", "status", "status TEXT NOT NULL DEFAULT 'analyzed'")
        _ensure_column(con, "scan_events", "finalized_at", "finalized_at TEXT")
        _ensure_column(con, "card_identities", "identity_fingerprint", "identity_fingerprint TEXT")
        con.execute("CREATE INDEX IF NOT EXISTS idx_identity_fingerprint ON card_identities(identity_fingerprint)")

def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

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
    """Stable fingerprint for one exact card identity; ownership-specific fields are excluded."""
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


def create_card(identity: dict, instance: dict) -> dict:
    """Create an owned instance and reuse an existing exact card identity when possible."""
    instance_id = str(uuid4())
    now = now_iso()
    normalized = identity.get("card_number_normalized") or (identity.get("card_number_printed") or "").strip().upper() or None
    identity["card_number_normalized"] = normalized
    fingerprint = identity_fingerprint(identity)
    reused = False
    with connect() as con:
        row = con.execute("SELECT id FROM card_identities WHERE identity_fingerprint=? ORDER BY created_at LIMIT 1", (fingerprint,)).fetchone()
        if row:
            identity_id = row["id"]
            reused = True
        else:
            identity_id = str(uuid4())
            con.execute("""INSERT INTO card_identities
                (id,data_json,sport,season,primary_subject_name,card_number_normalized,product_line,set_name,parallel_name,identity_fingerprint,created_at,updated_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""", (
                identity_id, json.dumps(identity, ensure_ascii=False), identity["sport"], identity.get("season"), identity["primary_subject_name"], normalized,
                identity.get("product_line"), identity.get("set_name"), identity.get("parallel_name"), fingerprint, now, now
            ))
        con.execute("INSERT INTO card_instances VALUES (?,?,?,?,?)", (instance_id, identity_id, json.dumps(instance, ensure_ascii=False, default=str), now, now))
    return {"card_identity_id": identity_id, "instance_id": instance_id, "reused_identity": reused, "duplicate_count": duplicate_count(identity_id)}

def duplicate_count(card_identity_id: str) -> int:
    with connect() as con:
        rows = con.execute("SELECT data_json FROM card_instances WHERE card_identity_id=?", (card_identity_id,)).fetchall()
    total = 0
    for row in rows:
        try:
            total += max(1, int(json.loads(row[0]).get("quantity") or 1))
        except Exception:
            total += 1
    return total

def list_collection(q: str | None = None, sport: str | None = None, page: int = 1, page_size: int = 50) -> dict:
    page = max(page, 1); page_size = min(max(page_size, 1), 200)
    where, params = [], []
    if sport:
        where.append("lower(i.sport)=lower(?)"); params.append(sport)
    if q:
        where.append("(lower(i.primary_subject_name) LIKE lower(?) OR lower(COALESCE(i.card_number_normalized,'')) LIKE lower(?) OR lower(COALESCE(i.product_line,'')) LIKE lower(?) OR lower(COALESCE(i.set_name,'')) LIKE lower(?) OR lower(COALESCE(i.parallel_name,'')) LIKE lower(?))")
        s=f"%{q}%"; params += [s,s,s,s,s]
    where_sql = (" WHERE " + " AND ".join(where)) if where else ""
    with connect() as con:
        total = con.execute("SELECT count(*) FROM card_identities i"+where_sql, params).fetchone()[0]
        rows = con.execute("SELECT i.*, (SELECT count(*) FROM card_instances ci WHERE ci.card_identity_id=i.id) as instance_rows FROM card_identities i"+where_sql+" ORDER BY i.created_at DESC LIMIT ? OFFSET ?", params+[page_size,(page-1)*page_size]).fetchall()
    items=[]
    for r in rows:
        d=json.loads(r["data_json"]); d["id"]=r["id"]; d["instance_rows"]=r["instance_rows"]; items.append(d)
    return {"items":items,"page":page,"page_size":page_size,"total":total}

def get_card(card_id: str) -> dict | None:
    with connect() as con:
        ident=con.execute("SELECT * FROM card_identities WHERE id=?",(card_id,)).fetchone()
        if not ident: return None
        instances=con.execute("SELECT * FROM card_instances WHERE card_identity_id=? ORDER BY created_at",(card_id,)).fetchall()
        comps=con.execute("SELECT * FROM market_comps WHERE card_identity_id=? ORDER BY created_at DESC",(card_id,)).fetchall()
    identity=json.loads(ident["data_json"]); identity["id"]=card_id
    return {"identity":identity,"instances":[dict(id=r["id"],**json.loads(r["data_json"])) for r in instances],"comps":[dict(id=r["id"],**json.loads(r["data_json"])) for r in comps]}

def add_comp(card_id: str, comp: dict) -> str:
    cid=str(uuid4())
    with connect() as con:
        if not con.execute("SELECT 1 FROM card_identities WHERE id=?",(card_id,)).fetchone(): raise KeyError(card_id)
        con.execute("INSERT INTO market_comps VALUES (?,?,?,?)",(cid,card_id,json.dumps(comp,ensure_ascii=False,default=str),now_iso()))
    return cid


def add_market_snapshot(card_id: str, snapshot: dict) -> str:
    sid=str(uuid4()); row=dict(snapshot); recorded=row.pop('recorded_at',None) or now_iso()
    with connect() as con:
        if not con.execute("SELECT 1 FROM card_identities WHERE id=?",(card_id,)).fetchone(): raise KeyError(card_id)
        con.execute("INSERT INTO market_price_snapshots VALUES (?,?,?,?)",(sid,card_id,json.dumps(row,ensure_ascii=False,default=str),recorded))
    return sid

def list_market_snapshots(card_id: str, limit: int = 365) -> list[dict]:
    limit=min(max(int(limit or 365),1),10000)
    with connect() as con:
        rows=con.execute("SELECT * FROM market_price_snapshots WHERE card_identity_id=? ORDER BY recorded_at ASC LIMIT ?",(card_id,limit)).fetchall()
    out=[]
    for r in rows:
        d=json.loads(r['data_json']); d['id']=r['id']; d['recorded_at']=r['recorded_at']; out.append(d)
    return out

def save_scan(front: str, back: str | None, locked_context: dict, output: dict, scan_id: str | None = None) -> str:
    sid=scan_id or str(uuid4())
    with connect() as con:
        con.execute("INSERT INTO scan_events (id,front_image_path,back_image_path,locked_context_json,raw_structured_output_json,final_card_identity_id,status,created_at,finalized_at) VALUES (?,?,?,?,?,?,?,?,?)",
                    (sid,front,back,json.dumps(locked_context),json.dumps(output,ensure_ascii=False),None,"analyzed",now_iso(),None))
    return sid

def _value_of_guess(guess):
    if isinstance(guess, dict) and "value" in guess:
        return guess.get("value")
    return guess

def record_corrections(scan_id: str, identity: dict, instance: dict) -> int:
    with connect() as con:
        row=con.execute("SELECT raw_structured_output_json FROM scan_events WHERE id=?",(scan_id,)).fetchone()
        if not row:
            raise KeyError(scan_id)
        original=json.loads(row[0]) if row[0] else {}
        extracted=original.get("extracted",{})
        inst_extracted=original.get("instance_extracted",{})
        count=0
        for field, final_value in identity.items():
            suggested=_value_of_guess(extracted.get(field))
            if suggested != final_value:
                correction_type = "filled" if suggested in (None, "", []) and final_value not in (None, "", []) else "changed"
                con.execute("INSERT INTO scan_corrections VALUES (?,?,?,?,?,?,?)",(
                    str(uuid4()),scan_id,field,json.dumps(suggested,ensure_ascii=False),json.dumps(final_value,ensure_ascii=False,default=str),correction_type,now_iso()))
                count += 1
        for field, final_value in instance.items():
            suggested=_value_of_guess(inst_extracted.get(field))
            if suggested != final_value:
                correction_type = "filled" if suggested in (None, "", []) and final_value not in (None, "", []) else "changed"
                con.execute("INSERT INTO scan_corrections VALUES (?,?,?,?,?,?,?)",(
                    str(uuid4()),scan_id,f"instance.{field}",json.dumps(suggested,ensure_ascii=False),json.dumps(final_value,ensure_ascii=False,default=str),correction_type,now_iso()))
                count += 1
    return count

def finalize_scan(scan_id: str, card_identity_id: str, identity: dict | None = None, instance: dict | None = None) -> int:
    corrections = record_corrections(scan_id, identity or {}, instance or {}) if identity is not None else 0
    with connect() as con:
        updated=con.execute("UPDATE scan_events SET final_card_identity_id=?, status='confirmed', finalized_at=? WHERE id=?",(card_identity_id,now_iso(),scan_id)).rowcount
        if not updated:
            raise KeyError(scan_id)
    return corrections

def list_scans(page: int = 1, page_size: int = 50, status: str | None = None) -> dict:
    page=max(1,page); page_size=min(max(1,page_size),200)
    where=""; params=[]
    if status:
        where=" WHERE status=?"; params.append(status)
    with connect() as con:
        total=con.execute("SELECT count(*) FROM scan_events"+where,params).fetchone()[0]
        rows=con.execute("SELECT * FROM scan_events"+where+" ORDER BY created_at DESC LIMIT ? OFFSET ?",params+[page_size,(page-1)*page_size]).fetchall()
    items=[]
    for r in rows:
        raw=json.loads(r["raw_structured_output_json"] or "{}")
        extracted=raw.get("extracted",{})
        items.append({
            "scan_id":r["id"],"status":r["status"],"created_at":r["created_at"],"finalized_at":r["finalized_at"],
            "final_card_identity_id":r["final_card_identity_id"],"overall_confidence":raw.get("overall_confidence",0),
            "primary_subject_name":_value_of_guess(extracted.get("primary_subject_name")),
            "product_line":_value_of_guess(extracted.get("product_line")),
            "card_number_printed":_value_of_guess(extracted.get("card_number_printed")),
            "parallel_name":_value_of_guess(extracted.get("parallel_name")),
        })
    return {"items":items,"page":page,"page_size":page_size,"total":total}

def get_scan(scan_id: str) -> dict | None:
    with connect() as con:
        row=con.execute("SELECT * FROM scan_events WHERE id=?",(scan_id,)).fetchone()
        if not row:return None
        corr=con.execute("SELECT * FROM scan_corrections WHERE scan_id=? ORDER BY created_at",(scan_id,)).fetchall()
    return {
        "scan_id":row["id"],"front_image_path":row["front_image_path"],"back_image_path":row["back_image_path"],
        "locked_context":json.loads(row["locked_context_json"] or "{}"),"analysis":json.loads(row["raw_structured_output_json"] or "{}"),
        "final_card_identity_id":row["final_card_identity_id"],"status":row["status"],"created_at":row["created_at"],"finalized_at":row["finalized_at"],
        "corrections":[{"id":c["id"],"field_name":c["field_name"],"suggested":json.loads(c["suggested_json"]),"final":json.loads(c["final_json"]),"correction_type":c["correction_type"],"created_at":c["created_at"]} for c in corr]
    }

def correction_stats() -> dict:
    with connect() as con:
        total_scans=con.execute("SELECT count(*) FROM scan_events").fetchone()[0]
        confirmed=con.execute("SELECT count(*) FROM scan_events WHERE status='confirmed'").fetchone()[0]
        total_corr=con.execute("SELECT count(*) FROM scan_corrections").fetchone()[0]
        rows=con.execute("SELECT field_name,count(*) n FROM scan_corrections GROUP BY field_name ORDER BY n DESC, field_name LIMIT 20").fetchall()
    return {"total_scans":total_scans,"confirmed_scans":confirmed,"total_corrections":total_corr,"top_corrected_fields":[{"field_name":r["field_name"],"count":r["n"]} for r in rows]}

def export_rows() -> list[dict]:
    with connect() as con:
        rows=con.execute("SELECT i.id identity_id, i.data_json identity_json, ci.id instance_id, ci.data_json instance_json FROM card_identities i JOIN card_instances ci ON ci.card_identity_id=i.id ORDER BY i.created_at").fetchall()
    out=[]
    for r in rows:
        d=json.loads(r["identity_json"]); d.update({f"owned_{k}":v for k,v in json.loads(r["instance_json"]).items()}); d["card_identity_id"]=r["identity_id"]; d["instance_id"]=r["instance_id"]; out.append(d)
    return out

def delete_card_instance(instance_id: str) -> dict:
    with connect() as con:
        row=con.execute("SELECT card_identity_id FROM card_instances WHERE id=?",(instance_id,)).fetchone()
        if not row: raise KeyError(instance_id)
        card_id=row[0]
        con.execute("DELETE FROM card_instances WHERE id=?",(instance_id,))
        remaining=con.execute("SELECT count(*) FROM card_instances WHERE card_identity_id=?",(card_id,)).fetchone()[0]
        identity_deleted=False
        if remaining == 0:
            con.execute("DELETE FROM card_identities WHERE id=?",(card_id,))
            identity_deleted=True
    return {"instance_id":instance_id,"card_id":card_id,"remaining_instances":remaining,"identity_deleted":identity_deleted}
