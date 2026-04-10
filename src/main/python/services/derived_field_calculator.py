from datetime import datetime, timedelta
from typing import Optional

from src.main.python.models.enums import AssetClass, Direction, TradeResult
from src.main.python.utils.logging_utils import get_logger
from src.main.python.utils.symbol_utils import classify_symbol

logger = get_logger(__name__)


class DerivedFieldCalculator:
    """
    Computes fields that cannot be read directly from a CSV row but can be
    derived from other imported values.
    """

    @staticmethod
    def calc_direction(raw_type: Optional[str]) -> Optional[Direction]:
        if not raw_type:
            return None
        normalized = raw_type.strip().lower()
        if normalized == "buy":
            return Direction.LONG
        if normalized == "sell":
            return Direction.SHORT
        return None

    @staticmethod
    def calc_holding_duration(
        entry: Optional[datetime], exit_: Optional[datetime]
    ) -> Optional[timedelta]:
        if entry is None or exit_ is None:
            return None
        if exit_ < entry:
            return None
        return exit_ - entry

    @staticmethod
    def calc_result(gross_pnl: Optional[float]) -> Optional[TradeResult]:
        if gross_pnl is None:
            return None
        if gross_pnl > 0:
            return TradeResult.WIN
        if gross_pnl < 0:
            return TradeResult.LOSS
        return TradeResult.BREAKEVEN

    @staticmethod
    def calc_net_pnl(
        gross_pnl: Optional[float],
        commission: Optional[float],
        swap: Optional[float],
    ) -> Optional[float]:
        if gross_pnl is None:
            return None
        return gross_pnl + (commission or 0.0) + (swap or 0.0)

    @staticmethod
    def calc_actual_r(
        gross_pnl: Optional[float],
        entry_price: Optional[float],
        stop_loss: Optional[float],
        lot_size: Optional[float],
        direction: Optional[Direction],
    ) -> Optional[float]:
        """
        Simplified R multiple: gross_pnl / (SL distance in price * lot_size).

        NOTE: This is an approximation. Accurate R calculation requires pip value
        and contract size, which are broker- and instrument-specific and are not
        available in MT4/MT5 CSV exports. This value should be treated as indicative.
        """
        if gross_pnl is None or entry_price is None or not stop_loss or not lot_size:
            return None
        sl_distance = abs(entry_price - stop_loss)
        if sl_distance == 0 or lot_size == 0:
            return None
        denominator = sl_distance * lot_size
        try:
            return round(gross_pnl / denominator, 2)
        except ZeroDivisionError:
            return None

    @staticmethod
    def calc_asset_class(symbol: Optional[str], rules: dict) -> AssetClass:
        if not symbol:
            return AssetClass.UNKNOWN
        return classify_symbol(symbol, rules)
