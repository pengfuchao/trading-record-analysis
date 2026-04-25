from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator


class MT5ConfigCreate(BaseModel):
    """Body for POST /accounts/{id}/mt5-config. Password is set in .env, not here."""
    mt5_login: int = Field(..., gt=0, description="MT5 account number (numeric login, must be > 0)")
    mt5_server: str = Field(..., min_length=1, description="Broker server string, e.g. 'ICMarkets-Live'")
    terminal_path: Optional[str] = Field(
        None,
        description="Full path to terminal64.exe. Leave null to use MT5 default location.",
    )
    broker_utc_offset: int = Field(2, ge=-12, le=14, description="Broker server UTC offset (default 2 = EET)")
    polling_interval_minutes: int = Field(
        60, gt=0, description="How often the background scheduler polls MT5 (minutes)."
    )
    lookback_days: int = Field(
        7, gt=0, le=365,
        description="Days of trade history to fetch on each scheduled poll (default 7).",
    )
    enabled: bool = Field(True, description="Whether auto-sync polling is enabled")

    @field_validator("mt5_server")
    @classmethod
    def server_not_whitespace(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("mt5_server must not be blank")
        return v.strip()


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
    open_positions_count: int = 0
    error_message: Optional[str]
    started_at: datetime
    completed_at: Optional[datetime]


class OpenPositionResponse(BaseModel):
    """One open MT5 position as of the last sync."""
    account_id: str
    ticket: int
    symbol: str
    direction: str                  # "long" | "short"
    lot_size: float
    entry_price: float
    current_price: Optional[float]
    stop_loss: Optional[float]
    take_profit: Optional[float]
    floating_pnl: Optional[float]
    opened_at: Optional[datetime]
    magic: Optional[int]
    comment: Optional[str]
    source: str
    synced_at: datetime

    class Config:
        from_attributes = True


class OpenPositionsResponse(BaseModel):
    """Response for GET /accounts/{id}/open-positions."""
    account_id: str
    count: int
    positions: List[OpenPositionResponse]


class MT5SyncRunSummary(BaseModel):
    """One entry in the sync history list."""
    run_id: str
    triggered_by: str
    started_at: datetime
    completed_at: Optional[datetime]
    status: str
    from_date: Optional[datetime]
    to_date: Optional[datetime]
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
    polling_interval_minutes: Optional[int]
    next_poll_at: Optional[datetime]    # next scheduled fire time (None if not scheduled)
    last_sync_at: Optional[datetime]    # completed_at of the most recent successful run
    last_runs: List[MT5SyncRunSummary]
