from __future__ import annotations

import os
import tempfile
import uuid

from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy.orm import Session

from src.main.python.api.dependencies import (
    get_account_repo, get_db, get_parser, get_trade_repo, require_account,
)
from src.main.python.api.schemas.imports import (
    EnrichSLTPResponse,
    ImportPreviewResponse, ImportPreviewRow,
    ImportResponse, RecomputeResponse, SkippedRowInfo, ValidationErrorInfo,
)
from src.main.python.services.csv_parser import MTCSVParser
from src.main.python.services.trade_repository import TradeRepository

router = APIRouter(prefix="/accounts", tags=["imports"])


def _write_temp(content: bytes) -> str:
    """Write bytes to a temp file and return the path. Caller must delete it."""
    tmp_fd, tmp_path = tempfile.mkstemp(suffix=".csv")
    os.write(tmp_fd, content)
    os.close(tmp_fd)
    return tmp_path


def _skipped_list(parser: MTCSVParser):
    return [
        SkippedRowInfo(
            row_index=r.get("row_index", 0),
            trade_id=r.get("trade_id"),
            reason=r.get("reason", "unknown"),
        )
        for r in parser.skipped_rows
    ]


def _error_list(parser: MTCSVParser):
    return [
        ValidationErrorInfo(
            trade_id=e.trade_id,
            field=e.field,
            message=e.message,
        )
        for e in parser.validation_errors
    ]


# ── Recompute derived fields ───────────────────────────────────────────────────

@router.post("/{account_id}/import/recompute-derived", response_model=RecomputeResponse)
def recompute_derived(
    account_id: str,
    recalculate_r: bool = True,
    recalculate_session: bool = False,
    overwrite_session: bool = False,
    broker_utc_offset: int = 2,
    db: Session = Depends(get_db),
):
    """
    Recompute broker-derived fields for existing trades — preserves all manual enrichment.

    Use this after the actual_r_multiple formula was corrected (Batch 2) to fix stale
    R values for previously imported trades without re-uploading CSV files.

    recalculate_r (default True):
      Recomputes actual_r_multiple using: signed_price_move / sl_distance.
      Trades missing exit_price, entry_price, stop_loss, or direction get None.
      Idempotent — safe to run repeatedly.

    recalculate_session (default False — safe):
      Re-derives session from entry_datetime using broker_utc_offset.
      WARNING: session is a manual enrichment field. By default only fills
      trades where session IS NULL. Set overwrite_session=True to replace all
      values, including those manually set by the user.

    broker_utc_offset (default 2):
      UTC offset for broker server time. Only used when recalculate_session=True.
    """
    account_repo = get_account_repo(db)
    trade_repo = get_trade_repo(db)
    require_account(account_id, account_repo)
    result = trade_repo.recompute_derived_fields(
        account_id,
        recalculate_r=recalculate_r,
        recalculate_session=recalculate_session,
        overwrite_session=overwrite_session,
        broker_utc_offset=broker_utc_offset,
    )
    return RecomputeResponse(**result)


# ── SL/TP enrichment from CSV ─────────────────────────────────────────────────

@router.post("/{account_id}/import/enrich-sl-tp", response_model=EnrichSLTPResponse)
async def enrich_sl_tp(
    account_id: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    parser: MTCSVParser = Depends(get_parser),
):
    """
    Use an FTMO / MT4 / MT5 exported CSV to fill missing stop_loss and
    take_profit for trades already in the DB, then recompute actual_r_multiple.

    Safe by design:
    - Never creates new trades (only enriches existing rows).
    - Never overwrites stop_loss or take_profit when already set.
    - Matching is exact: trade_id (MT5 Position number / MT4 Ticket).
    - actual_r_multiple is recomputed only for trades where stop_loss was just filled.

    The response counts explain exactly what happened:
    - matched        → trade_id found in DB
    - sl_filled      → stop_loss was NULL, CSV provided a value
    - tp_filled      → take_profit was NULL, CSV provided a value
    - r_computed     → R recomputed after SL was filled
    - already_had_sl → matched but SL was already present (no change)
    - not_in_db      → CSV row whose trade_id is not in this account's DB
    """
    account_repo = get_account_repo(db)
    trade_repo = get_trade_repo(db)
    account = require_account(account_id, account_repo)

    content = await file.read()
    tmp_path = _write_temp(content)
    try:
        trades = parser.parse(tmp_path, account)
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)

    counts = trade_repo.enrich_sl_tp(account_id, trades)

    return EnrichSLTPResponse(
        account_id=account_id,
        detected_platform=parser.detected_platform or "unknown",
        skipped_rows=_skipped_list(parser),
        **counts,
    )


# ── Preview (parse without saving) ────────────────────────────────────────────

@router.post("/{account_id}/import/preview", response_model=ImportPreviewResponse)
async def preview_import(
    account_id: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    parser: MTCSVParser = Depends(get_parser),
):
    """Parse a CSV and return a preview of what would be imported — no DB writes."""
    account_repo = get_account_repo(db)
    trade_repo = get_trade_repo(db)
    account = require_account(account_id, account_repo)

    content = await file.read()
    tmp_path = _write_temp(content)
    try:
        trades = parser.parse(tmp_path, account)
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)

    # Deduplication check against existing DB trades
    incoming_ids = [t.trade_id for t in trades]
    existing_ids = trade_repo.get_existing_trade_ids(account_id, incoming_ids)

    preview_rows = [
        ImportPreviewRow(
            trade_id=t.trade_id,
            symbol=t.symbol,
            direction=t.direction.value if t.direction else None,
            entry_datetime=t.entry_datetime.isoformat() if t.entry_datetime else None,
            exit_datetime=t.exit_datetime.isoformat() if t.exit_datetime else None,
            lot_size=t.lot_size,
            gross_pnl=t.gross_pnl,
            net_pnl=t.net_pnl,
            result=t.result.value if t.result else None,
            is_existing=(t.trade_id in existing_ids),
        )
        for t in trades[:20]
    ]

    new_count = sum(1 for tid in incoming_ids if tid not in existing_ids)
    existing_count = len(existing_ids & set(incoming_ids))

    return ImportPreviewResponse(
        account_id=account_id,
        detected_platform=parser.detected_platform or "unknown",
        total_rows_in_file=parser.total_rows_in_file,
        trade_rows_parsed=len(trades),
        new_trade_count=new_count,
        existing_trade_count=existing_count,
        validation_error_count=len(parser.validation_errors),
        preview_rows=preview_rows,
        skipped_rows=_skipped_list(parser),
        validation_errors=_error_list(parser),
    )


# ── Import (parse + save) ──────────────────────────────────────────────────────

@router.post("/{account_id}/import", response_model=ImportResponse)
async def import_csv(
    account_id: str,
    file: UploadFile = File(...),
    duplicate_strategy: str = "skip",
    db: Session = Depends(get_db),
    parser: MTCSVParser = Depends(get_parser),
):
    """
    Import a MT4/MT5 CSV into the trade log.

    duplicate_strategy:
      skip          — skip trades whose trade_id already exists in DB (default, safest)
      update_broker — update broker-sourced fields for existing trades;
                      manual enrichment (setup tags, lessons, etc.) is preserved
    """
    account_repo = get_account_repo(db)
    trade_repo = get_trade_repo(db)
    account = require_account(account_id, account_repo)

    import_run_id = str(uuid.uuid4())

    content = await file.read()
    tmp_path = _write_temp(content)
    try:
        trades = parser.parse(tmp_path, account)
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)

    counts = trade_repo.save_batch_import(
        trades,
        import_run_id=import_run_id,
        duplicate_strategy=duplicate_strategy,
    )

    return ImportResponse(
        account_id=account_id,
        import_run_id=import_run_id,
        trades_imported=counts.new + counts.updated,
        trades_new=counts.new,
        trades_updated=counts.updated,
        trades_skipped=counts.skipped,
        duplicate_strategy=duplicate_strategy,
        validation_error_count=len(parser.validation_errors),
        skipped_rows=_skipped_list(parser),
        validation_errors=_error_list(parser),
    )
