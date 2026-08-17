"""Native Postgres connectivity/schema diagnostics for V0.15.3."""
from __future__ import annotations
import socket
from urllib.parse import urlparse
from .config import settings


def _parsed():
    if not settings.supabase_database_url:
        return None
    try:
        return urlparse(settings.supabase_database_url)
    except Exception:
        return None


def host() -> str | None:
    p = _parsed()
    return p.hostname if p else None


def port() -> int:
    p = _parsed()
    return int(p.port or 5432) if p else 5432


def dns_check() -> tuple[bool | None, str | None]:
    if not settings.supabase_database_url:
        return None, None
    h = host()
    if not h:
        return False, "SUPABASE_DATABASE_URL enthält keinen gültigen Hostnamen."
    try:
        socket.getaddrinfo(h, port(), type=socket.SOCK_STREAM)
        return True, None
    except Exception as exc:
        return False, f"DNS-Auflösung für Postgres-Host {h} fehlgeschlagen: {type(exc).__name__}: {exc}"


def connection_check() -> tuple[bool | None, str | None, dict]:
    if not settings.supabase_database_url:
        return None, None, {}
    try:
        import psycopg
        with psycopg.connect(settings.supabase_database_url, connect_timeout=8) as con:
            with con.cursor() as cur:
                cur.execute("select current_database(), current_user, version()")
                db, user, version = cur.fetchone()
                cur.execute("""
                    select table_name from information_schema.tables
                    where table_schema='public' and table_name in
                    ('card_identities','card_instances','market_comps','scan_events','scan_corrections')
                    order by table_name
                """)
                tables = [r[0] for r in cur.fetchall()]
                cur.execute("""
                    select column_name from information_schema.columns
                    where table_schema='public' and table_name='card_identities'
                """)
                cols = {r[0] for r in cur.fetchall()}
                schema_family = (
                    "json-provider-v0.14+" if "data_json" in cols and "identity_fingerprint" in cols
                    else "legacy-detailed-v0.1" if "owner_user_id" in cols
                    else "unknown"
                )
        return True, None, {
            "database": db,
            "user": user,
            "server_version": version.split(',')[0] if version else None,
            "sportscard_tables": tables,
            "schema_family": schema_family,
        }
    except Exception as exc:
        return False, f"Postgres-Verbindung fehlgeschlagen: {type(exc).__name__}: {exc}", {}
