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


class ImportResponse(BaseModel):
    account_id: str
    import_run_id: str
    trades_imported: int
    trades_skipped: int
    validation_error_count: int
    skipped_rows: List[SkippedRowInfo]
    validation_errors: List[ValidationErrorInfo]
