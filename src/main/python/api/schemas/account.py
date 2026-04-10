from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel

from src.main.python.models.enums import ChallengePhase, Platform


class AccountCreate(BaseModel):
    account_id: str
    broker: str
    platform: Platform
    prop_firm: Optional[str] = None
    challenge_phase: Optional[ChallengePhase] = None
    starting_balance: Optional[float] = None
    account_currency: str = "USD"


class AccountUpdate(BaseModel):
    broker: Optional[str] = None
    platform: Optional[Platform] = None
    prop_firm: Optional[str] = None
    challenge_phase: Optional[ChallengePhase] = None
    starting_balance: Optional[float] = None
    account_currency: Optional[str] = None


class AccountResponse(BaseModel):
    account_id: str
    broker: str
    platform: Platform
    prop_firm: Optional[str]
    challenge_phase: Optional[ChallengePhase]
    starting_balance: Optional[float]
    account_currency: str
    created_at: datetime
    trade_count: Optional[int] = None
