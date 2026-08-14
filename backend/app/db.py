"""Persistence facade.

DATABASE_PROVIDER=sqlite keeps the local/test backend.
DATABASE_PROVIDER=supabase activates persistent Postgres through Supabase.
"""
from .config import settings

if (settings.database_provider or "sqlite").lower() == "supabase":
    from .supabase_db import *  # noqa: F401,F403
else:
    from .sqlite_db import *  # noqa: F401,F403
