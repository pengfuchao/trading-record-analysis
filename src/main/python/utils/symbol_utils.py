import re
from typing import Optional

from src.main.python.models.enums import AssetClass


# Common broker suffixes appended to symbol names (e.g. EURUSD.pro, XAUUSD_SB)
_BROKER_SUFFIX_PATTERN = re.compile(r"[._\-](pro|ecn|raw|std|sb|micro|mini|classic|plus|prime|fix)$", re.IGNORECASE)


def normalize_symbol(symbol: str) -> str:
    """Strip broker-added suffixes so classification patterns match cleanly."""
    return _BROKER_SUFFIX_PATTERN.sub("", symbol.strip()).upper()


def classify_symbol(symbol: str, rules: dict) -> AssetClass:
    """
    Match a symbol against ordered regex rules from mt_column_map.yaml.
    Returns AssetClass.UNKNOWN if no rule matches.
    """
    clean = normalize_symbol(symbol)
    for asset_class_name, patterns in rules.items():
        for pattern in patterns:
            if re.match(pattern, clean, re.IGNORECASE):
                try:
                    return AssetClass(asset_class_name.capitalize())
                except ValueError:
                    # asset_class_name in config doesn't match enum — fall through
                    pass
    return AssetClass.UNKNOWN
