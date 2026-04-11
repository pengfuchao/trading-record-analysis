from datetime import datetime, timedelta
from typing import Optional

from src.main.python.models.enums import AssetClass, Direction, TradeResult
from src.main.python.utils.logging_utils import get_logger
from src.main.python.utils.symbol_utils import classify_symbol

logger = get_logger(__name__)

# Trades with |net_pnl| below this threshold are classified as Breakeven.
# Avoids floating-point noise producing WIN/LOSS on micro-PnL trades.
_BREAKEVEN_EPSILON = 0.01


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
    def calc_result(
        net_pnl: Optional[float],
        gross_pnl: Optional[float] = None,
    ) -> Optional[TradeResult]:
        """
        Classify trade outcome using net_pnl (gross + commission + swap).

        Falls back to gross_pnl only when net_pnl is unavailable.
        Trades with |pnl| < _BREAKEVEN_EPSILON are classified as Breakeven
        to absorb floating-point noise.

        Definition:
          WIN       — net_pnl > +epsilon
          LOSS      — net_pnl < -epsilon
          BREAKEVEN — |net_pnl| <= epsilon, or both net_pnl and gross_pnl are None
        """
        pnl = net_pnl if net_pnl is not None else gross_pnl
        if pnl is None:
            return None
        if pnl > _BREAKEVEN_EPSILON:
            return TradeResult.WIN
        if pnl < -_BREAKEVEN_EPSILON:
            return TradeResult.LOSS
        return TradeResult.BREAKEVEN

    @staticmethod
    def calc_net_pnl(
        gross_pnl: Optional[float],
        commission: Optional[float],
        swap: Optional[float],
    ) -> Optional[float]:
        """
        Net PnL = gross_pnl + commission + swap.

        In MT4/MT5 exports, commission and swap are already signed:
        commission is typically negative (cost), swap may be positive (credit) or
        negative (debit). gross_pnl is the raw trade profit before costs.
        """
        if gross_pnl is None:
            return None
        return gross_pnl + (commission or 0.0) + (swap or 0.0)

    @staticmethod
    def calc_actual_r(
        exit_price: Optional[float],
        entry_price: Optional[float],
        stop_loss: Optional[float],
        direction: Optional[Direction],
    ) -> Optional[float]:
        """
        Price-based R multiple: signed_price_move / sl_distance.

        Formula:
          LONG:  R = (exit_price - entry_price) / abs(entry_price - stop_loss)
          SHORT: R = (entry_price - exit_price) / abs(stop_loss - entry_price)

        This is instrument-independent and does NOT require pip value, contract size,
        or lot size. It measures how many times the risk distance the trade moved in
        the trader's favour (or against). Works correctly for forex, gold, indices,
        and any instrument with a numeric price.

        Examples:
          LONG EURUSD: entry=1.1000, exit=1.1100, SL=1.0950 → R = 0.01/0.005 = 2.0
          SHORT XAUUSD: entry=2000, exit=1950, SL=2025 → R = 50/25 = 2.0
          LONG US30: entry=38000, exit=37800, SL=37900 → R = -200/100 = -2.0 (loss)

        Returns None if entry_price, exit_price, stop_loss, or direction are missing,
        or if sl_distance is zero (no stop loss set or SL equals entry).

        NOTE: Does not account for SL moves after entry (cannot be detected from data).
        """
        if exit_price is None or entry_price is None or not stop_loss or direction is None:
            return None
        sl_distance = abs(entry_price - stop_loss)
        if sl_distance == 0:
            return None
        if direction == Direction.LONG:
            return round((exit_price - entry_price) / sl_distance, 2)
        else:  # SHORT
            return round((entry_price - exit_price) / sl_distance, 2)

    @staticmethod
    def calc_asset_class(symbol: Optional[str], rules: dict) -> AssetClass:
        if not symbol:
            return AssetClass.UNKNOWN
        return classify_symbol(symbol, rules)

    @staticmethod
    def calc_session(
        entry_datetime: Optional[datetime], utc_offset: int = 2
    ) -> Optional[str]:
        """
        Auto-derive trading session from entry datetime hour.

        MT4/MT5 timestamps are in broker server local time. The session
        boundaries are calibrated against UTC+2 (EET winter, used by most
        MT4/MT5 brokers including FTMO). Pass utc_offset to adjust for brokers
        that use a different server timezone.

        The hour is normalised to a UTC+2 reference before comparison:
          normalized_hour = (broker_local_hour - (utc_offset - 2)) % 24

        Session classification (UTC+2 reference hours):
          Asia            00:00 – 08:59
          London          09:00 – 12:59  (London open, pre-NY overlap)
          London/NY       13:00 – 16:59  (London/New York overlap — highest liquidity)
          New York        17:00 – 20:59  (NY session, post-London)
          After Hours     21:00 – 23:59  (low liquidity)

        Returns None if entry_datetime is None.
        """
        if entry_datetime is None:
            return None
        # Normalise to UTC+2 reference (the frame the boundaries were calibrated in).
        # utc_offset=2 → no change; utc_offset=3 → shift left 1hr; utc_offset=0 → shift right 2hrs
        hour = (entry_datetime.hour - (utc_offset - 2)) % 24
        if hour < 9:
            return "Asia"
        if hour < 13:
            return "London"
        if hour < 17:
            return "London/NY"
        if hour < 21:
            return "New York"
        return "After Hours"
