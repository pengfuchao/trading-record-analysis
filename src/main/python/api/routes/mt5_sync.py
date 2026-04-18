"""
MT5 sync routes — Phase 1 (manual trigger, config CRUD, status).

Endpoints:
  POST /accounts/{account_id}/mt5-config        — create or update MT5 config
  GET  /accounts/{account_id}/mt5-config        — read config (no password)
  POST /accounts/{account_id}/mt5-sync          — trigger a manual sync
  GET  /accounts/{account_id}/mt5-sync/status   — last N sync runs

Password convention:
  MT5 passwords are read from environment variables, never from the request body.
  Key format: MT5_<ACCOUNT_ID_UPPER_UNDERSCORED>_PASSWORD
  Example:    account "ftmo-p1" → env var MT5_FTMO_P1_PASSWORD
"""
from __future__ import annotations

from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from src.main.python.api.dependencies import get_db, require_account
from src.main.python.services.telegram_notifier import get_notifier
from src.main.python.api.schemas.mt5_sync import (
    MT5ConfigCreate,
    MT5ConfigResponse,
    MT5SyncRequest,
    MT5SyncResponse,
    MT5SyncRunSummary,
    MT5SyncStatusResponse,
    OpenPositionResponse,
    OpenPositionsResponse,
)
from src.main.python.services.account_repository import AccountRepository
from src.main.python.services.mt5_connector import MT5ConnectionConfig
from src.main.python.services.mt5_sync_service import MT5SyncService, load_mt5_password

router = APIRouter(tags=["MT5 Sync"])


def _get_sync_service(db: Session = Depends(get_db)) -> MT5SyncService:
    return MT5SyncService(db)


def _get_account_repo(db: Session = Depends(get_db)) -> AccountRepository:
    return AccountRepository(db)


# ── Config endpoints ───────────────────────────────────────────────────────────

@router.post(
    "/accounts/{account_id}/mt5-config",
    response_model=MT5ConfigResponse,
    summary="Create or update MT5 connection config for an account",
)
def upsert_mt5_config(
    account_id: str,
    body: MT5ConfigCreate,
    db: Session = Depends(get_db),
    account_repo: AccountRepository = Depends(_get_account_repo),
) -> MT5ConfigResponse:
    require_account(account_id, account_repo)
    svc = MT5SyncService(db)
    obj = svc.save_config(account_id, body.model_dump())
    return MT5ConfigResponse.model_validate(obj)


@router.get(
    "/accounts/{account_id}/mt5-config",
    response_model=MT5ConfigResponse,
    summary="Get MT5 connection config for an account",
)
def get_mt5_config(
    account_id: str,
    account_repo: AccountRepository = Depends(_get_account_repo),
    svc: MT5SyncService = Depends(_get_sync_service),
) -> MT5ConfigResponse:
    require_account(account_id, account_repo)
    cfg = svc.get_config(account_id)
    if cfg is None:
        raise HTTPException(
            status_code=404,
            detail=f"No MT5 config found for account '{account_id}'. "
                   "Use POST /mt5-config to set one up.",
        )
    return MT5ConfigResponse.model_validate(cfg)


# ── Sync trigger ───────────────────────────────────────────────────────────────

@router.post(
    "/accounts/{account_id}/mt5-sync",
    response_model=MT5SyncResponse,
    summary="Trigger a manual MT5 sync for an account",
)
def trigger_mt5_sync(
    account_id: str,
    body: MT5SyncRequest = MT5SyncRequest(),  # noqa: B008
    db: Session = Depends(get_db),
    account_repo: AccountRepository = Depends(_get_account_repo),
) -> MT5SyncResponse:
    """
    Synchronously fetches closed trade history from MT5 and upserts into the trade log.

    Requires:
    - An MT5 config row (POST /mt5-config first)
    - The environment variable MT5_<ACCOUNT_ID_UPPER>_PASSWORD to be set

    The request blocks until the sync completes (typically a few seconds).
    Manual enrichment (setup_type, notes, flags, etc.) is always preserved.
    """
    account = require_account(account_id, account_repo)
    svc = MT5SyncService(db)

    # Config must exist
    cfg = svc.get_config(account_id)
    if cfg is None:
        raise HTTPException(
            status_code=409,
            detail=f"No MT5 config for account '{account_id}'. "
                   "Set up config first with POST /accounts/{account_id}/mt5-config.",
        )

    # Load password from environment — never from the request
    password = load_mt5_password(account_id)
    if not password:
        env_key = f"MT5_{account_id.upper().replace('-', '_').replace(' ', '_')}_PASSWORD"
        raise HTTPException(
            status_code=422,
            detail=f"MT5 password not found. Set environment variable '{env_key}' and restart the server.",
        )

    conn_config = MT5ConnectionConfig(
        login=cfg.mt5_login,
        password=password,
        server=cfg.mt5_server,
        terminal_path=cfg.terminal_path,
        broker_utc_offset=cfg.broker_utc_offset,
    )

    from_date = body.from_date or (datetime.utcnow() - timedelta(days=30))
    to_date = body.to_date or datetime.utcnow()

    result = svc.sync_account(
        account_id=account_id,
        config=conn_config,
        from_date=from_date,
        to_date=to_date,
        triggered_by="manual",
    )

    try:
        get_notifier().notify_mt5_sync_result(account_id, result)
    except Exception:
        pass  # notification failure must never affect sync response

    return MT5SyncResponse(
        run_id=result.run_id,
        account_id=result.account_id,
        status=result.status,
        deals_fetched=result.deals_fetched,
        positions_built=result.positions_built,
        trades_new=result.trades_new,
        trades_updated=result.trades_updated,
        trades_skipped=result.trades_skipped,
        open_positions_count=result.open_positions_count,
        error_message=result.error_message,
        started_at=result.started_at,
        completed_at=result.completed_at,
    )


# ── Status endpoint ────────────────────────────────────────────────────────────

@router.get(
    "/accounts/{account_id}/mt5-sync/status",
    response_model=MT5SyncStatusResponse,
    summary="Get MT5 sync status and recent run history for an account",
)
def get_sync_status(
    account_id: str,
    limit: int = 5,
    account_repo: AccountRepository = Depends(_get_account_repo),
    svc: MT5SyncService = Depends(_get_sync_service),
) -> MT5SyncStatusResponse:
    require_account(account_id, account_repo)

    cfg = svc.get_config(account_id)
    runs = svc.get_recent_runs(account_id, limit=limit)

    # Surface the most-recent successful run's completion time prominently
    last_sync_at = next(
        (r.completed_at for r in runs if r.status == "success" and r.completed_at),
        None,
    )

    return MT5SyncStatusResponse(
        account_id=account_id,
        sync_configured=cfg is not None,
        enabled=cfg.enabled if cfg else False,
        last_sync_at=last_sync_at,
        last_runs=[MT5SyncRunSummary.model_validate(r) for r in runs],
    )


# ── Open positions endpoint ────────────────────────────────────────────────────

@router.get(
    "/accounts/{account_id}/open-positions",
    response_model=OpenPositionsResponse,
    summary="Get currently open MT5 positions for an account",
)
def get_open_positions(
    account_id: str,
    account_repo: AccountRepository = Depends(_get_account_repo),
    svc: MT5SyncService = Depends(_get_sync_service),
) -> OpenPositionsResponse:
    """
    Returns the open-positions snapshot captured during the last successful MT5 sync.
    This list is replaced wholesale on every sync run — positions that have closed
    since the last sync will no longer appear here.

    Returns an empty list if no sync has been run yet or no positions were open.
    """
    require_account(account_id, account_repo)
    rows = svc.get_open_positions(account_id)
    return OpenPositionsResponse(
        account_id=account_id,
        count=len(rows),
        positions=[OpenPositionResponse.model_validate(r) for r in rows],
    )
