"""
MT5Connector — thin context-manager wrapper around the MetaTrader5 Python package.

This module owns the terminal initialize/login/shutdown lifecycle and nothing else.
All normalization and business logic lives in MT5SyncService.

IMPORTANT: The MetaTrader5 package is Windows-only (requires a running MT5 terminal
on the same machine). On Linux/Mac the import will fail silently; _MT5_AVAILABLE is
set to False and any attempt to connect raises MT5ConnectionError immediately.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ── Windows-only guard ────────────────────────────────────────────────────────
try:
    import MetaTrader5 as mt5  # type: ignore[import]
    _MT5_AVAILABLE = True
except ImportError:
    mt5 = None  # type: ignore[assignment]
    _MT5_AVAILABLE = False
    logger.info("MetaTrader5 package not available — MT5 sync disabled on this platform")

# MT5 deal entry type constants (defined in the MT5 API)
_DEAL_ENTRY_IN = 0      # position opened
_DEAL_ENTRY_OUT = 1     # position closed
_DEAL_ENTRY_INOUT = 2   # partial close / hedge — deferred to Phase 2

# MT5 deal type constants
_DEAL_TYPE_BUY = 0
_DEAL_TYPE_SELL = 1


# ── Config dataclass ──────────────────────────────────────────────────────────

@dataclass
class MT5ConnectionConfig:
    """All parameters needed to connect to an MT5 terminal."""
    login: int
    password: str           # plaintext — loaded from .env at the call site; never stored in DB
    server: str
    terminal_path: Optional[str] = None   # path to terminal64.exe; None = let MT5 find it
    broker_utc_offset: int = 2            # broker server timezone offset from UTC


# ── Exception ─────────────────────────────────────────────────────────────────

class MT5ConnectionError(Exception):
    """Raised when MT5 initialize, login, or a data fetch fails."""


# ── Connector ─────────────────────────────────────────────────────────────────

class MT5Connector:
    """
    Context manager that opens an MT5 terminal session on __enter__ and
    closes it on __exit__.

    Usage::

        try:
            with MT5Connector(config) as conn:
                info = conn.fetch_account_info()
                deals = conn.fetch_deals(from_dt, to_dt)
                positions = conn.reconstruct_positions(deals)
        except MT5ConnectionError as e:
            # handle connection or fetch failure

    __enter__ raises MT5ConnectionError if:
    - MetaTrader5 package is not installed (non-Windows environment)
    - mt5.initialize() returns False
    - mt5.login() returns False
    """

    def __init__(self, config: MT5ConnectionConfig) -> None:
        self._config = config

    def __enter__(self) -> "MT5Connector":
        if not _MT5_AVAILABLE:
            raise MT5ConnectionError(
                "MetaTrader5 package not available on this platform. "
                "MT5 sync requires Windows with MetaTrader5 installed."
            )

        init_kwargs: Dict[str, Any] = {}
        if self._config.terminal_path:
            init_kwargs["path"] = self._config.terminal_path

        if not mt5.initialize(**init_kwargs):
            err = mt5.last_error()
            raise MT5ConnectionError(f"mt5.initialize() failed: {err}")

        # If the terminal is already logged in to the requested account,
        # skip mt5.login() — re-authenticating with a placeholder password
        # would fail even though the session is live.  This is the common
        # real-world case: MT5 is already running on the trader's machine.
        existing = mt5.account_info()
        already_logged_in = (
            existing is not None
            and existing.login == self._config.login
            and existing.server == self._config.server
        )

        if already_logged_in:
            logger.info(
                "MT5 already logged in: account=%d server=%s — skipping mt5.login()",
                self._config.login, self._config.server,
            )
        else:
            if not mt5.login(
                login=self._config.login,
                password=self._config.password,
                server=self._config.server,
            ):
                err = mt5.last_error()
                mt5.shutdown()
                raise MT5ConnectionError(
                    f"mt5.login() failed for account {self._config.login} "
                    f"on server {self._config.server}: {err}"
                )
            logger.info(
                "MT5 logged in: account=%d server=%s",
                self._config.login, self._config.server,
            )

        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        if _MT5_AVAILABLE and mt5 is not None:
            mt5.shutdown()
            logger.info("MT5 terminal disconnected")

    # ── Data fetch methods ─────────────────────────────────────────────────────

    def fetch_account_info(self) -> Dict[str, Any]:
        """
        Return basic account info from the connected terminal.

        Returns dict with keys: balance, equity, margin, free_margin, currency, login.
        Raises MT5ConnectionError if account_info() returns None.
        """
        info = mt5.account_info()
        if info is None:
            raise MT5ConnectionError(f"mt5.account_info() returned None: {mt5.last_error()}")
        return {
            "balance":      info.balance,
            "equity":       info.equity,
            "margin":       info.margin,
            "free_margin":  info.margin_free,
            "currency":     info.currency,
            "login":        info.login,
        }

    def fetch_open_positions(self) -> List[Dict[str, Any]]:
        """
        Return all currently open positions from the connected MT5 terminal.

        Uses mt5.positions_get() which returns live TradePosition objects.
        Each returned dict has keys:
            ticket        int
            symbol        str
            direction     str    — "long" (buy) or "short" (sell)
            lot_size      float
            entry_price   float
            current_price float
            stop_loss     float | None
            take_profit   float | None
            floating_pnl  float
            opened_at     datetime  (UTC)
            magic         int
            comment       str
        """
        raw = mt5.positions_get()
        if raw is None:
            raise MT5ConnectionError(
                f"mt5.positions_get() returned None: {mt5.last_error()}"
            )
        positions: List[Dict[str, Any]] = []
        for p in raw:
            # position type: 0 = buy, 1 = sell
            direction = "long" if getattr(p, "type", 0) == 0 else "short"
            sl = getattr(p, "sl", 0.0) or None
            tp = getattr(p, "tp", 0.0) or None
            opened_at = datetime.utcfromtimestamp(p.time) if p.time else None
            positions.append({
                "ticket":        p.ticket,
                "symbol":        p.symbol,
                "direction":     direction,
                "lot_size":      p.volume,
                "entry_price":   p.price_open,
                "current_price": p.price_current,
                "stop_loss":     sl,
                "take_profit":   tp,
                "floating_pnl":  p.profit,
                "opened_at":     opened_at,
                "magic":         getattr(p, "magic", 0),
                "comment":       getattr(p, "comment", "") or "",
            })
        logger.info("Fetched %d open positions from MT5", len(positions))
        return positions

    def fetch_deals(self, from_date: datetime, to_date: datetime) -> List[Any]:
        """
        Fetch all historical deals in the given date range.

        Returns the raw list of MT5 deal named tuples as returned by
        mt5.history_deals_get(). Raises MT5ConnectionError on failure.
        """
        deals = mt5.history_deals_get(from_date, to_date)
        if deals is None:
            raise MT5ConnectionError(
                f"mt5.history_deals_get() returned None: {mt5.last_error()}"
            )
        logger.info(
            "Fetched %d deals from %s to %s", len(deals), from_date, to_date
        )
        return list(deals)

    def reconstruct_positions(self, deals: List[Any]) -> List[Dict[str, Any]]:
        """
        Group deals by position_id and reconstruct closed positions.

        MT5 deal model:
        - Each trade = at least 2 deals: one DEAL_ENTRY_IN (open) + one or more exit deals
        - DEAL_ENTRY_OUT = full close; DEAL_ENTRY_INOUT = partial close (volume reduced)
        - A position with partial closes has: one IN + N INOUT (partials) + one OUT (final)
        - position_id links all deals belonging to the same position

        Returns a list of dicts for closed positions only (at least one OUT or INOUT deal).
        Positions with no exit deal (still open) are excluded.

        Partial-close handling (Phase B):
        - INOUT deals are included in out_deals alongside OUT deals
        - PnL is the sum across all exit deals (correct for partials)
        - Exit price is the volume-weighted average across all exit deals
        - Exit time is the last exit deal's timestamp
        - partial_close_count records how many INOUT deals were present

        Each returned dict has keys:
            position_id   int    — MT5 position ticket (used as trade_id)
            symbol        str
            raw_type      str    — "buy" or "sell" (from the IN deal type)
            volume        float  — lot size
            entry_time    datetime
            entry_price   float
            sl            float | None  — stop loss at entry (may be 0 → None)
            tp            float | None  — take profit at entry (may be 0 → None)
            exit_time     datetime      — last OUT deal time
            exit_price    float         — last OUT deal price (weighted avg for partials)
            gross_profit  float         — sum of profit across all OUT deals
            commission    float         — sum of commission across all deals
            swap          float         — sum of swap across all deals
            magic                int
            comment              str
            partial_close_count  int   — number of INOUT (partial-close) deals (0 for simple trades)
        """
        # Group deals by position_id
        by_position: Dict[int, Dict[str, Any]] = {}

        for deal in deals:
            entry_type = getattr(deal, "entry", None)

            if entry_type not in (_DEAL_ENTRY_IN, _DEAL_ENTRY_OUT, _DEAL_ENTRY_INOUT):
                continue  # balance operations, deposits, etc.

            pos_id = deal.position_id
            if pos_id not in by_position:
                by_position[pos_id] = {"in": None, "outs": []}

            if entry_type == _DEAL_ENTRY_IN:
                by_position[pos_id]["in"] = deal
            elif entry_type in (_DEAL_ENTRY_OUT, _DEAL_ENTRY_INOUT):
                # INOUT = partial close — treated identically to a full close
                # for aggregation purposes (PnL, commission, swap, exit price).
                by_position[pos_id]["outs"].append(deal)

        positions: List[Dict[str, Any]] = []

        for pos_id, group in by_position.items():
            in_deal = group["in"]
            out_deals = group["outs"]

            # Skip positions still open (no exit deal yet)
            if not out_deals:
                continue
            # Skip positions with no entry deal (edge case — shouldn't happen)
            if in_deal is None:
                logger.warning("Position %s has OUT deals but no IN deal — skipping", pos_id)
                continue

            # Determine direction from IN deal type
            raw_type = "buy" if in_deal.type == _DEAL_TYPE_BUY else "sell"

            # Aggregate all exit deals (OUT + INOUT partial closes)
            total_gross_profit = sum(d.profit for d in out_deals)
            total_commission = sum(getattr(d, "commission", 0.0) or 0.0 for d in out_deals)
            total_commission += getattr(in_deal, "commission", 0.0) or 0.0
            total_swap = sum(getattr(d, "swap", 0.0) or 0.0 for d in out_deals)
            total_swap += getattr(in_deal, "swap", 0.0) or 0.0

            # Exit time = last exit deal's timestamp
            # MT5 deal.time is a UTC epoch integer — use utcfromtimestamp so that
            # stored datetimes are timezone-naive UTC regardless of the machine's
            # local timezone. datetime.fromtimestamp() would apply the OS local
            # offset and produce wrong timestamps on non-UTC machines.
            last_out = max(out_deals, key=lambda d: d.time)
            exit_time = datetime.utcfromtimestamp(last_out.time)

            # Exit price = volume-weighted average across all partial and full closes.
            # Using last_out.price alone would be wrong for partial-close sequences
            # and produce an incorrect R-multiple.
            total_exit_volume = sum(getattr(d, "volume", 0.0) or 0.0 for d in out_deals)
            if total_exit_volume > 0:
                exit_price = (
                    sum((getattr(d, "volume", 0.0) or 0.0) * d.price for d in out_deals)
                    / total_exit_volume
                )
            else:
                exit_price = last_out.price  # fallback: no volume data

            # Entry from IN deal.
            # NOTE: sl/tp are NOT fields on TradeDeal (history_deals_get) — they live on
            # TradeOrder (history_orders_get). Fetching the matching order would require
            # a second API call keyed on in_deal.order; deferred to Phase 2. Until then,
            # sl/tp are None for all MT5-synced trades (same as CSV imports without those cols).
            entry_time = datetime.utcfromtimestamp(in_deal.time)
            entry_price = in_deal.price
            sl = getattr(in_deal, "sl", 0.0) or None   # 0.0 → None; missing attr → None
            tp = getattr(in_deal, "tp", 0.0) or None   # 0.0 → None; missing attr → None

            partial_close_count = sum(
                1 for d in out_deals
                if getattr(d, "entry", None) == _DEAL_ENTRY_INOUT
            )
            if partial_close_count:
                logger.debug(
                    "Position %s has %d partial close(s) — aggregating into single trade",
                    pos_id, partial_close_count,
                )

            positions.append({
                "position_id":         pos_id,
                "symbol":              in_deal.symbol,
                "raw_type":            raw_type,
                "volume":              in_deal.volume,
                "entry_time":          entry_time,
                "entry_price":         entry_price,
                "sl":                  sl,
                "tp":                  tp,
                "exit_time":           exit_time,
                "exit_price":          exit_price,
                "gross_profit":        total_gross_profit,
                "commission":          total_commission,
                "swap":                total_swap,
                "magic":               getattr(in_deal, "magic", 0),
                "comment":             getattr(in_deal, "comment", "") or "",
                "partial_close_count": partial_close_count,
            })

        logger.info(
            "Reconstructed %d closed positions from %d position groups",
            len(positions), len(by_position),
        )
        return positions
