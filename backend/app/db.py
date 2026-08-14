"""Resilient persistence facade for SportsCard Vault.

V0.15.2 deliberately keeps the API alive when Supabase is misconfigured or
temporarily unreachable. DATABASE_PROVIDER=Supabase is still treated as the
requested production provider, but a local SQLite fallback is activated for
non-destructive diagnostics and scanner continuity until persistence is green.
"""
from __future__ import annotations

import socket
from types import ModuleType
from .config import settings
from . import sqlite_db

def _load_supabase_module():
    from . import supabase_db
    return supabase_db

REQUESTED_PROVIDER = (settings.database_provider or "sqlite").lower()
ACTIVE_PROVIDER = "sqlite"
PROVIDER_ERROR: str | None = None
_provider: ModuleType = sqlite_db


def _supabase_dns_check() -> tuple[bool, str | None]:
    host = settings.supabase_host
    if not host:
        return False, "SUPABASE_URL enthält keinen gültigen Hostnamen."
    try:
        socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
        return True, None
    except Exception as exc:
        return False, f"DNS-Auflösung für {host} fehlgeschlagen: {type(exc).__name__}: {exc}"


def activate_sqlite_fallback(reason: str) -> None:
    global ACTIVE_PROVIDER, PROVIDER_ERROR, _provider
    ACTIVE_PROVIDER = "sqlite-fallback" if REQUESTED_PROVIDER == "supabase" else "sqlite"
    PROVIDER_ERROR = reason
    _provider = sqlite_db
    # Ensure the fallback DB exists so scanner/history endpoints stay usable.
    try:
        sqlite_db.init_db()
    except Exception:
        pass


def init_db() -> None:
    global ACTIVE_PROVIDER, PROVIDER_ERROR, _provider
    if REQUESTED_PROVIDER != "supabase":
        _provider = sqlite_db
        ACTIVE_PROVIDER = "sqlite"
        PROVIDER_ERROR = None
        return sqlite_db.init_db()

    if not settings.supabase_ready:
        return activate_sqlite_fallback("Supabase gewählt, aber URL oder Secret Key fehlt.")

    dns_ok, dns_error = _supabase_dns_check()
    if not dns_ok:
        return activate_sqlite_fallback(dns_error or "Supabase DNS nicht verfügbar.")

    try:
        supabase_db = _load_supabase_module()
        supabase_db.init_db()
        _provider = supabase_db
        ACTIVE_PROVIDER = "supabase"
        PROVIDER_ERROR = None
    except Exception as exc:
        activate_sqlite_fallback(f"Supabase-Verbindung fehlgeschlagen: {type(exc).__name__}: {exc}")


def provider_status() -> dict:
    dns_ok, dns_error = _supabase_dns_check() if REQUESTED_PROVIDER == "supabase" else (None, None)
    return {
        "requested_provider": REQUESTED_PROVIDER,
        "active_provider": ACTIVE_PROVIDER,
        "fallback_active": ACTIVE_PROVIDER == "sqlite-fallback",
        "provider_error": PROVIDER_ERROR,
        "supabase_host": settings.supabase_host,
        "supabase_dns_ok": dns_ok,
        "supabase_dns_error": dns_error,
    }


def _call(name, *args, **kwargs):
    return getattr(_provider, name)(*args, **kwargs)


def create_card(*a, **k): return _call("create_card", *a, **k)
def duplicate_count(*a, **k): return _call("duplicate_count", *a, **k)
def list_collection(*a, **k): return _call("list_collection", *a, **k)
def get_card(*a, **k): return _call("get_card", *a, **k)
def add_comp(*a, **k): return _call("add_comp", *a, **k)
def save_scan(*a, **k): return _call("save_scan", *a, **k)
def record_corrections(*a, **k): return _call("record_corrections", *a, **k)
def finalize_scan(*a, **k): return _call("finalize_scan", *a, **k)
def list_scans(*a, **k): return _call("list_scans", *a, **k)
def get_scan(*a, **k): return _call("get_scan", *a, **k)
def correction_stats(*a, **k): return _call("correction_stats", *a, **k)
def export_rows(*a, **k): return _call("export_rows", *a, **k)
def identity_fingerprint(*a, **k): return _call("identity_fingerprint", *a, **k)
