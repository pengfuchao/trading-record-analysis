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
    ImportResponse, SkippedRowInfo, ValidationErrorInfo,
)
from src.main.python.services.csv_parser import MTCSVParser
from src.main.python.services.trade_repository import TradeRepository

router = APIRouter(prefix="/accounts", tags=["imports"])


@router.post("/{account_id}/import", response_model=ImportResponse)
async def import_csv(
    account_id: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    parser: MTCSVParser = Depends(get_parser),
):
    account_repo = get_account_repo(db)
    trade_repo = get_trade_repo(db)
    account = require_account(account_id, account_repo)

    import_run_id = str(uuid.uuid4())

    # MTCSVParser requires a file path — write upload bytes to a temp file
    content = await file.read()
    tmp_fd, tmp_path = tempfile.mkstemp(suffix=".csv")
    try:
        os.write(tmp_fd, content)
        os.close(tmp_fd)
        trades = parser.parse(tmp_path, account)
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)

    count = trade_repo.save_batch(trades, import_run_id=import_run_id)

    skipped = [
        SkippedRowInfo(
            row_index=r.get("row_index", 0),
            trade_id=r.get("trade_id"),
            reason=r.get("reason", "unknown"),
        )
        for r in parser.skipped_rows
    ]
    errors = [
        ValidationErrorInfo(
            trade_id=e.trade_id,
            field=e.field,
            message=e.message,
        )
        for e in parser.validation_errors
    ]

    return ImportResponse(
        account_id=account_id,
        import_run_id=import_run_id,
        trades_imported=count,
        trades_skipped=len(parser.skipped_rows),
        validation_error_count=len(errors),
        skipped_rows=skipped,
        validation_errors=errors,
    )
