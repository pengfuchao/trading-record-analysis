from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class MT5ConfigCreate(BaseModel):
    """Body for POST /accounts/{id}/mt5-config. Password is set in .env, not here."""
    mt5_login: int = Field(..., description="MT5 account number (numeric login)")
    mt5_server: str = Field(..., description="Broker server string, e.g. 'ICMarkets-Live'")
    terminal_path: Optional[str] = Field(
        None,
        description="Full path to terminal64.exe. Leave null to use MT5 default location.",
    )
    broker_utc_offset: int = Field(2, description="Broker server UTC offset (default 2 = EET)")
    polling_interval_minutes: int = Field(
        60, description="Placeholder for Phase 2 auto-polling. Not used in Phase 1."
    )
    enabled: bool = Field(True, description="Whether auto-sync is enabled (Phase 2)")


class MT5ConfigResponse(MT5ConfigCreate):
    """Response for GET /accounts/{id}/mt5-config. Password is never returned."""
    account_id: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class MT5SyncRequest(BaseModel):
    """Optional body for POST /accounts/{id}/mt5-sync."""
    from_date: Optional[datetime] = Field(
        None,
        description="Start of deal history window. Defaults to 30 days ago.",
    )
    to_date: Optional[datetime] = Field(
        None,
        description="End of deal history window. Defaults to now.",
    )


class MT5SyncResponse(BaseModel):
    """Response for POST /accounts/{id}/mt5-sync."""
    run_id: str
    account_id: str
    status: str                     # "success" | "error"
    deals_fetched: int
    positions_built: int
    trades_new: int
    trades_updated: int
    trades_skipped: int
    error_message: Optional[str]
    started_at: datetime
    completed_at: Optional[datetime]


class MT5SyncRunSummary(BaseModel):
    """One entry in the sync history list."""
    run_id: str
    triggered_by: str
    started_at: datetime
    completed_at: Optional[datetime]
    status: str
    deals_fetched: Optional[int]
    positions_built: Optional[int]
    trades_new: Optional[int]
    trades_updated: Optional[int]
    trades_skipped: Optional[int]
    error_message: Optional[str]

    class Config:
        from_attributes = True


class MT5SyncStatusResponse(BaseModel):
    """Response for GET /accounts/{id}/mt5-sync/status."""
    account_id: str
    sync_configured: bool
    enabled: bool
    last_runs: List[MT5SyncRunSummary]
