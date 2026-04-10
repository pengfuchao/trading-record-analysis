from collections import namedtuple
from typing import List

from src.main.python.models.trade import Trade

ValidationError = namedtuple("ValidationError", ["trade_id", "field", "message"])


class TradeValidator:
    """
    Validates a Trade dataclass and returns a list of ValidationError.
    Never raises — callers decide how to handle errors.
    """

    def validate(self, trade: Trade) -> List[ValidationError]:
        errors: List[ValidationError] = []
        tid = trade.trade_id or "<unknown>"

        if not trade.trade_id:
            errors.append(ValidationError(tid, "trade_id", "trade_id is required"))

        if not trade.symbol:
            errors.append(ValidationError(tid, "symbol", "symbol is required"))

        if trade.entry_datetime is None:
            errors.append(ValidationError(tid, "entry_datetime", "entry_datetime is required"))

        if trade.exit_datetime is None:
            errors.append(ValidationError(tid, "exit_datetime", "exit_datetime is required"))

        if trade.entry_datetime and trade.exit_datetime:
            if trade.exit_datetime < trade.entry_datetime:
                errors.append(
                    ValidationError(
                        tid,
                        "exit_datetime",
                        f"exit_datetime {trade.exit_datetime} is before entry_datetime {trade.entry_datetime}",
                    )
                )

        if trade.lot_size is not None and trade.lot_size <= 0:
            errors.append(
                ValidationError(tid, "lot_size", f"lot_size must be > 0, got {trade.lot_size}")
            )

        if trade.entry_price is not None and trade.entry_price <= 0:
            errors.append(
                ValidationError(
                    tid, "entry_price", f"entry_price must be > 0, got {trade.entry_price}"
                )
            )

        return errors
