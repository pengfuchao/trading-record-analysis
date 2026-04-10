from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel


class SkippedRowInfo(BaseModel):
    row_index: int
    trade_id: Optional[str] = None
    reason: str


class ValidationErrorInfo(BaseModel):
    trade_id: Optional[str] = None
    field: Optional[str] = None
    message: str


class ImportPreviewRow(BaseModel):
    trade_id: str
    symbol: Optional[str]
    direction: Optional[str]
    entry_datetime: Optional[str]
    exit_datetime: Optional[str]
    lot_size: Optional[float]
    gross_pnl: Optional[float]
    net_pnl: Optional[float]
    result: Optional[str]
    is_existing: bool   # True if trade_id already exists in DB for this account


class ImportPreviewResponse(BaseModel):
    account_id: str
    detected_platform: str          # "MT4" or "MT5"
    total_rows_in_file: int         # total rows in CSV (before type filtering)
    trade_rows_parsed: int          # rows successfully parsed as trades
    new_trade_count: int            # trades not yet in DB
    existing_trade_count: int       # trades already in DB
    validation_error_count: int
    preview_rows: List[ImportPreviewRow]    # first 20 successfully parsed trades
    skipped_rows: List[SkippedRowInfo]
    validation_errors: List[ValidationErrorInfo]


class ImportResponse(BaseModel):
    account_id: str
    import_run_id: str
    # Backward-compatible total count
    trades_imported: int            # = trades_new + trades_updated
    # Detailed deduplication counts
    trades_new: int
    trades_updated: int
    trades_skipped: int
    duplicate_strategy: str
    validation_error_count: int
    skipped_rows: List[SkippedRowInfo]
    validation_errors: List[ValidationErrorInfo]
