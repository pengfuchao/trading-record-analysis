import csv
import io
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import pandas as pd

from src.main.python.models.account import Account
from src.main.python.models.enums import Platform
from src.main.python.models.trade import Trade
from src.main.python.services.derived_field_calculator import DerivedFieldCalculator
from src.main.python.services.field_mapper import FieldMapper
from src.main.python.services.validator import TradeValidator, ValidationError
from src.main.python.utils.config_loader import get_app_config, load_yaml
from src.main.python.utils.logging_utils import configure_logging, get_logger

logger = get_logger(__name__)

# Column name used to auto-detect platform from CSV headers
_MT5_SENTINEL = "Position"
_MT4_SENTINEL = "Ticket"

# Trade row type values (case-insensitive) — rows not matching these are filtered
_TRADE_TYPES = {"buy", "sell"}

# MT5 datetime formats to try in order
_DATETIME_FORMATS = [
    "%Y.%m.%d %H:%M:%S",
    "%Y-%m-%d %H:%M:%S",
    "%Y.%m.%d %H:%M",
    "%Y-%m-%d %H:%M",
    "%d.%m.%Y %H:%M:%S",
]

# ── Format registry ────────────────────────────────────────────────────────────
#
# Each entry describes a CSV format variant that doesn't match the standard
# MT4/MT5 column names directly.  The pipeline:
#   1. probe_format() scans the first few rows to identify the format
#   2. _normalize_for_format() renames columns so the existing FieldMapper
#      (loaded from mt_column_map.yaml) can handle the row unchanged
#
# To add a new format: add a _FMTKEY_SENTINELS set + rename dicts below,
# then wire them into _probe_format() and _normalize_for_format().

# ── Compact English (MyFXBook / broker compact export) ─────────────────────────
# Header:  Ticket,Open,Type,Volume,Symbol,Price,SL,TP,Close,Price,Swap,
#          Commissions,Profit,Pips,"Trade duration in seconds"
# Notable: duplicate "Price" columns (entry then exit); no metadata rows.
_COMPACT_EN_SENTINELS: frozenset = frozenset({"Ticket", "Open", "Close", "SL", "Commissions"})
_COMPACT_EN_SIMPLE_RENAMES: Dict[str, str] = {
    "Open":        "Open Time",
    "Close":       "Close Time",
    "SL":          "S/L",
    "TP":          "T/P",
    "Commissions": "Commission",
    "Volume":      "Lots",
}
# (original_col, name_for_1st_occurrence, name_for_2nd_occurrence)
_COMPACT_EN_DUP_RENAMES: List[Tuple[str, str, str]] = [
    ("Price", "Open Price", "Close Price"),
]

# ── Traditional Chinese MT5 report (FTMO and compatible brokers) ───────────────
# Header (row 6 after metadata):
#   時間,持倉,交易品種,類型,交易量,價位,止損,止盈,時間,價位,手續費,隔夜利息,盈利,,
# Notable: 6 metadata rows before the real header; duplicate 時間 and 價位
#          (same positional semantics as MT5 Time/Price).
_CHINESE_MT5_SENTINELS: frozenset = frozenset({"持倉", "交易品種"})
_CHINESE_MT5_SIMPLE_RENAMES: Dict[str, str] = {
    "持倉":   "Position",
    "交易品種": "Symbol",
    "類型":   "Type",
    "交易量":  "Volume",
    "止損":   "S / L",
    "止盈":   "T / P",
    "手續費":  "Commission",
    "隔夜利息": "Swap",
    "盈利":   "Profit",
}
# Both occurrences of 時間→Time and 價位→Price keep the same target name;
# the MT5 FieldMapper resolves them by positional index (first vs second).
_CHINESE_MT5_DUP_RENAMES: List[Tuple[str, str, str]] = [
    ("時間", "Time",  "Time"),
    ("價位", "Price", "Price"),
]


def _parse_datetime(raw: Optional[str]) -> Optional[datetime]:
    if not raw:
        return None
    for fmt in _DATETIME_FORMATS:
        try:
            return datetime.strptime(raw.strip(), fmt)
        except (ValueError, AttributeError):
            continue
    return None


def _parse_float(raw: Optional[str]) -> Optional[float]:
    if raw is None:
        return None
    try:
        # Normalise before parsing:
        #   "- 5.00"  → "-5.00"   (space between sign and digits)
        #   "4 326.95"→ "4326.95" (space as thousands separator)
        #   ","-style decimal separators → "."
        cleaned = str(raw).strip().replace(",", ".").replace(" ", "")
        return float(cleaned)
    except (ValueError, TypeError):
        return None


def _parse_int(raw: Optional[str]) -> Optional[int]:
    if raw is None:
        return None
    try:
        return int(float(str(raw).strip()))
    except (ValueError, TypeError):
        return None


class MTCSVParser:
    """
    Parses MT4/MT5 exported CSV files into a list of Trade objects.

    Usage:
        parser = MTCSVParser()
        trades = parser.parse("path/to/history.csv", account)
        print(f"Parsed {len(trades)} trades, skipped {len(parser.skipped_rows)}")
    """

    def __init__(self, config_path: str = "src/main/resources/config/app_config.yaml") -> None:
        self._config = get_app_config(config_path)
        configure_logging(
            level=self._config["logging"]["level"],
            log_file=self._config["paths"].get("log_file"),
        )
        self._column_map_path: str = self._config["paths"]["mt_column_map"]
        self._skip_invalid: bool = self._config["import"].get("skip_invalid_rows", True)
        self._encoding: str = self._config["import"].get("encoding", "utf-8")

        self._asset_class_rules: dict = load_yaml(self._column_map_path).get(
            "asset_class_rules", {}
        )
        session_cfg = self._config.get("session_classification", {})
        self._session_utc_offset: int = int(session_cfg.get("broker_utc_offset", 2))

        self.skipped_rows: list = []
        self.validation_errors: List[ValidationError] = []
        self.detected_platform: str = ""    # set during parse(); "MT4" or "MT5"
        self.total_rows_in_file: int = 0    # row count before type filtering

    # ── Format detection & normalisation ──────────────────────────────────────

    def _probe_format(self, file_path: str) -> Tuple[str, int]:
        """
        Peek at the first 12 rows of the file to determine the CSV format.

        Returns:
            format_key  — one of "mt5" | "mt4" | "compact_en" | "chinese_mt5"
            header_row  — 0-based index of the row that contains column headers
                          (>0 for formats with metadata rows before the header)
        """
        # Try configured encoding, then safe fallbacks
        encodings = [self._encoding, "utf-8-sig", "utf-8", "latin-1"]
        raw_lines: List[str] = []
        for enc in encodings:
            try:
                with open(file_path, encoding=enc, errors="replace") as fh:
                    raw_lines = [fh.readline().rstrip("\n\r") for _ in range(12)]
                break
            except Exception:
                continue

        if not raw_lines:
            logger.warning("Could not probe file encoding — defaulting to MT4")
            return "mt4", 0

        def _split(line: str) -> List[str]:
            try:
                return [c.strip().strip('"') for c in next(csv.reader(io.StringIO(line)))]
            except Exception:
                return [c.strip().strip('"') for c in line.split(",")]

        for row_idx, line in enumerate(raw_lines):
            cells = _split(line)
            cell_set = set(cells) - {""}

            # Compact English (must check before MT4 because both have "Ticket")
            if _COMPACT_EN_SENTINELS <= cell_set:
                logger.info("Detected format: compact_en (header at row %d)", row_idx)
                return "compact_en", row_idx

            # Chinese MT5 report (header appears after metadata rows)
            if _CHINESE_MT5_SENTINELS <= cell_set:
                logger.info("Detected format: chinese_mt5 (header at row %d)", row_idx)
                return "chinese_mt5", row_idx

            # Standard MT5: sentinel column "Position"
            if _MT5_SENTINEL in cell_set:
                logger.info("Detected format: mt5 (header at row %d)", row_idx)
                return "mt5", row_idx

            # Standard MT4: "Ticket" + "Open Time" to distinguish from compact_en
            if _MT4_SENTINEL in cell_set and "Open Time" in cell_set:
                logger.info("Detected format: mt4 (header at row %d)", row_idx)
                return "mt4", row_idx

        logger.warning("Format unrecognised — defaulting to MT4 at row 0")
        return "mt4", 0

    @staticmethod
    def _apply_column_renames(
        df: pd.DataFrame,
        simple_renames: Dict[str, str],
        dup_renames: List[Tuple[str, str, str]],
    ) -> pd.DataFrame:
        """
        Rename DataFrame columns in-place and return the DataFrame.

        dup_renames: list of (original, first_occurrence_new, second_occurrence_new)
                     applied by positional index before simple_renames.
        simple_renames: {old: new} applied to all remaining columns by name.
        """
        cols = list(df.columns)

        # Positional renames for duplicate column names
        for orig, first_new, second_new in dup_renames:
            indices = [i for i, c in enumerate(cols) if c == orig]
            if len(indices) >= 1:
                cols[indices[0]] = first_new
            if len(indices) >= 2:
                cols[indices[1]] = second_new

        # Name-based renames for unique columns
        cols = [simple_renames.get(c, c) for c in cols]
        df.columns = cols
        return df

    def _normalize_for_format(self, df: pd.DataFrame, format_key: str) -> pd.DataFrame:
        """
        Rename columns of a non-standard format so the existing FieldMapper
        (keyed off standard MT4/MT5 column names) can process rows unchanged.

        Standard formats ("mt4", "mt5") are returned as-is.
        """
        if format_key == "compact_en":
            return self._apply_column_renames(
                df, _COMPACT_EN_SIMPLE_RENAMES, _COMPACT_EN_DUP_RENAMES
            )
        if format_key == "chinese_mt5":
            return self._apply_column_renames(
                df, _CHINESE_MT5_SIMPLE_RENAMES, _CHINESE_MT5_DUP_RENAMES
            )
        return df

    # ── Public parse entry-point ───────────────────────────────────────────────

    def parse(self, file_path: str, account: Account) -> List[Trade]:
        self.skipped_rows = []
        self.validation_errors = []
        self.detected_platform = ""
        self.total_rows_in_file = 0

        logger.info("Parsing file: %s", file_path)

        # Step 1: identify format and locate the real header row
        format_key, header_row = self._probe_format(file_path)

        # Step 2: read CSV, skipping any metadata rows that precede the header
        skip = list(range(header_row)) if header_row > 0 else None
        try:
            df = pd.read_csv(
                file_path,
                encoding=self._encoding,
                dtype=str,           # read everything as string; we coerce later
                keep_default_na=False,
                skiprows=skip,
            )
        except Exception as exc:
            logger.error("Failed to read CSV '%s': %s", file_path, exc)
            raise

        logger.info("Loaded %d rows from CSV (format=%s)", len(df), format_key)
        self.total_rows_in_file = len(df)

        # Step 3: normalise non-standard column names to the MT4/MT5 schema
        df = self._normalize_for_format(df, format_key)

        platform = self._detect_platform(df, account, format_key)
        self.detected_platform = platform.value
        logger.info("Detected platform: %s (format=%s)", platform.value, format_key)

        df = self._filter_trade_rows(df)
        logger.info("%d trade rows after filtering", len(df))

        mapper = FieldMapper(platform, self._column_map_path)
        validator = TradeValidator()
        calc = DerivedFieldCalculator()
        df_columns = df.columns.tolist()

        trades: List[Trade] = []
        for idx, row in df.iterrows():
            trade, errors = self._parse_row(
                row, idx, df_columns, platform, account, mapper, calc, validator
            )
            if trade is None:
                self.skipped_rows.append({"row_index": idx, "reason": "parse_error"})
                continue

            if errors:
                self.validation_errors.extend(errors)
                if self._skip_invalid:
                    logger.warning(
                        "Skipping row %d (trade_id=%s): %d validation error(s)",
                        idx,
                        trade.trade_id,
                        len(errors),
                    )
                    self.skipped_rows.append(
                        {"row_index": idx, "trade_id": trade.trade_id, "reason": "validation"}
                    )
                    continue

            trades.append(trade)

        logger.info(
            "Parse complete: %d trades, %d skipped, %d validation errors",
            len(trades),
            len(self.skipped_rows),
            len(self.validation_errors),
        )
        return trades

    def _detect_platform(
        self, df: pd.DataFrame, account: Account, format_key: str = ""
    ) -> Platform:
        # Format key takes precedence when supplied by _probe_format
        if format_key in ("mt5", "chinese_mt5"):
            return Platform.MT5
        if format_key in ("mt4", "compact_en"):
            return Platform.MT4

        # Legacy sentinel-based detection for unknown/unlabelled formats
        cols = df.columns.tolist()
        if _MT5_SENTINEL in cols:
            return Platform.MT5
        if _MT4_SENTINEL in cols:
            return Platform.MT4

        logger.warning(
            "Could not detect platform from columns %s — using account platform %s",
            cols,
            account.platform,
        )
        return account.platform

    def _filter_trade_rows(self, df: pd.DataFrame) -> pd.DataFrame:
        """Remove balance/deposit/summary rows that are not actual trades."""
        # Identify the trade type column (MT5: "Type", MT4: "Type")
        if "Type" not in df.columns:
            return df
        mask = df["Type"].str.strip().str.lower().isin(_TRADE_TYPES)
        removed = (~mask).sum()
        if removed:
            logger.info("Filtered %d non-trade rows (balance/summary)", removed)
        return df[mask].reset_index(drop=True)

    def _parse_row(
        self,
        row: pd.Series,
        row_index: int,
        df_columns: List[str],
        platform: Platform,
        account: Account,
        mapper: FieldMapper,
        calc: DerivedFieldCalculator,
        validator: TradeValidator,
    ) -> Tuple[Optional[Trade], List[ValidationError]]:
        try:
            raw = mapper.map_row(row, df_columns)

            entry_dt = _parse_datetime(raw.get("entry_datetime"))
            exit_dt = _parse_datetime(raw.get("exit_datetime"))
            entry_price = _parse_float(raw.get("entry_price"))
            exit_price = _parse_float(raw.get("exit_price"))
            stop_loss = _parse_float(raw.get("stop_loss"))
            take_profit = _parse_float(raw.get("take_profit"))
            lot_size = _parse_float(raw.get("volume"))
            commission = _parse_float(raw.get("commission"))
            swap = _parse_float(raw.get("swap"))
            gross_pnl = _parse_float(raw.get("gross_pnl"))
            magic = _parse_int(raw.get("magic"))

            raw_type = raw.get("trade_type")
            direction = calc.calc_direction(raw_type)
            holding_duration = calc.calc_holding_duration(entry_dt, exit_dt)
            net_pnl = calc.calc_net_pnl(gross_pnl, commission, swap)
            # Use net_pnl for result classification (gross fallback when net unavailable)
            result = calc.calc_result(net_pnl, gross_pnl)
            actual_r = calc.calc_actual_r(exit_price, entry_price, stop_loss, direction)
            symbol = raw.get("symbol")
            asset_class = calc.calc_asset_class(symbol, self._asset_class_rules)
            # Auto-derive session from entry_datetime when not manually set
            session = calc.calc_session(entry_dt, utc_offset=self._session_utc_offset)

            trade = Trade(
                trade_id=raw.get("trade_id") or f"row_{row_index}",
                account_id=account.account_id,
                symbol=symbol,
                asset_class=asset_class,
                direction=direction,
                platform=platform,
                raw_trade_type=raw_type,
                entry_datetime=entry_dt,
                exit_datetime=exit_dt,
                holding_duration=holding_duration,
                entry_price=entry_price,
                exit_price=exit_price,
                stop_loss=stop_loss if stop_loss and stop_loss != 0.0 else None,
                take_profit=take_profit if take_profit and take_profit != 0.0 else None,
                lot_size=lot_size,
                gross_pnl=gross_pnl,
                commission=commission,
                swap=swap,
                net_pnl=net_pnl,
                actual_r_multiple=actual_r,
                result=result,
                magic=magic,
                comment=raw.get("comment"),
                session=session,
            )

            errors = validator.validate(trade)
            return trade, errors

        except Exception as exc:
            logger.warning("Failed to parse row %d: %s", row_index, exc, exc_info=True)
            return None, []
