from datetime import datetime
from typing import List, Optional, Tuple

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
        return float(str(raw).replace(",", ".").strip())
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

        self.skipped_rows: list = []
        self.validation_errors: List[ValidationError] = []

    def parse(self, file_path: str, account: Account) -> List[Trade]:
        self.skipped_rows = []
        self.validation_errors = []

        logger.info("Parsing file: %s", file_path)

        try:
            df = pd.read_csv(
                file_path,
                encoding=self._encoding,
                dtype=str,           # read everything as string; we coerce later
                keep_default_na=False,
            )
        except Exception as exc:
            logger.error("Failed to read CSV '%s': %s", file_path, exc)
            raise

        logger.info("Loaded %d rows from CSV", len(df))

        platform = self._detect_platform(df, account)
        logger.info("Detected platform: %s", platform.value)

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

    def _detect_platform(self, df: pd.DataFrame, account: Account) -> Platform:
        cols = df.columns.tolist()
        if _MT5_SENTINEL in cols:
            return Platform.MT5
        if _MT4_SENTINEL in cols:
            return Platform.MT4
        # Fall back to account's platform if ambiguous
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
            result = calc.calc_result(gross_pnl)
            net_pnl = calc.calc_net_pnl(gross_pnl, commission, swap)
            actual_r = calc.calc_actual_r(gross_pnl, entry_price, stop_loss, lot_size, direction)
            symbol = raw.get("symbol")
            asset_class = calc.calc_asset_class(symbol, self._asset_class_rules)

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
            )

            errors = validator.validate(trade)
            return trade, errors

        except Exception as exc:
            logger.warning("Failed to parse row %d: %s", row_index, exc, exc_info=True)
            return None, []
