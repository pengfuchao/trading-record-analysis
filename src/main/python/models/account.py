from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from src.main.python.models.enums import ChallengePhase, Platform


@dataclass
class Account:
    account_id: str
    broker: str
    platform: Platform
    prop_firm: Optional[str] = None
    challenge_phase: Optional[ChallengePhase] = None
    starting_balance: Optional[float] = None
    account_currency: str = "USD"
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
