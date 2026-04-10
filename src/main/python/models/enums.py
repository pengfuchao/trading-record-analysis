from enum import Enum


class Direction(str, Enum):
    LONG = "Long"
    SHORT = "Short"


class AssetClass(str, Enum):
    FOREX = "Forex"
    GOLD = "Gold"
    SILVER = "Silver"
    OIL = "Oil"
    INDICES = "Indices"
    CRYPTO = "Crypto"
    UNKNOWN = "Unknown"


class TradeResult(str, Enum):
    WIN = "Win"
    LOSS = "Loss"
    BREAKEVEN = "Breakeven"


class Platform(str, Enum):
    MT4 = "MT4"
    MT5 = "MT5"


class ChallengePhase(str, Enum):
    PHASE_1 = "Phase1"
    PHASE_2 = "Phase2"
    FUNDED = "Funded"
    LIVE = "Live"
