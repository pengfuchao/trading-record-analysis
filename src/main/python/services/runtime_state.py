"""
Thin helpers for reading and writing persistent runtime state.

Used by mt5_scheduler (error cooldown) and telegram_notifier (FTMO dedup status).
All functions are stateless — the caller owns the session lifecycle.

Typical usage:
    from src.main.python.services.database import get_session
    import src.main.python.services.runtime_state as rs

    with get_session() as session:
        rs.set_state(session, account_id, "ftmo_last_status", "SAFE")
    # session auto-commits on exit
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy.orm import Session

from src.main.python.models.db_models import RuntimeStateModel

logger = logging.getLogger(__name__)


def get_state(session: Session, scope: str, kind: str) -> Optional[Any]:
    """Return the parsed JSON value for (scope, kind), or None if not found."""
    row = session.get(RuntimeStateModel, (scope, kind))
    if row is None:
        return None
    try:
        return json.loads(row.value_json)
    except Exception as exc:
        logger.warning("runtime_state: could not parse value for (%s, %s): %s", scope, kind, exc)
        return None


def set_state(session: Session, scope: str, kind: str, value: Any) -> None:
    """Upsert the JSON-serialised value for (scope, kind)."""
    row = session.get(RuntimeStateModel, (scope, kind))
    now = datetime.now(timezone.utc)
    if row is None:
        session.add(
            RuntimeStateModel(
                scope=scope,
                kind=kind,
                value_json=json.dumps(value),
                updated_at=now,
            )
        )
    else:
        row.value_json = json.dumps(value)
        row.updated_at = now


def delete_state(session: Session, scope: str, kind: str) -> None:
    """Remove the row for (scope, kind) if it exists; no-op otherwise."""
    row = session.get(RuntimeStateModel, (scope, kind))
    if row is not None:
        session.delete(row)
