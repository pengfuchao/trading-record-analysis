import dataclasses
import json
import os
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, List

import pandas as pd

from src.main.python.models.trade import Trade
from src.main.python.utils.logging_utils import get_logger

logger = get_logger(__name__)


class _TradeEncoder(json.JSONEncoder):
    def default(self, obj: Any) -> Any:
        if isinstance(obj, datetime):
            return obj.isoformat()
        if isinstance(obj, timedelta):
            return obj.total_seconds()
        if isinstance(obj, Enum):
            return obj.value
        return super().default(obj)


class OutputWriter:
    def __init__(self, config: dict) -> None:
        self._output_dir: str = config["paths"]["output_dir"]
        self._json_indent: int = config["output"].get("json_indent", 2)
        self._ts_format: str = config["output"].get("timestamp_format", "%Y%m%d_%H%M%S")
        os.makedirs(self._output_dir, exist_ok=True)

    def _ts(self) -> str:
        return datetime.utcnow().strftime(self._ts_format)

    def write_json(self, trades: List[Trade], run_label: str) -> str:
        path = os.path.join(self._output_dir, f"trades_{run_label}.json")
        data = [dataclasses.asdict(t) for t in trades]
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, cls=_TradeEncoder, indent=self._json_indent, ensure_ascii=False)
        logger.info("Wrote %d trades to %s", len(trades), path)
        return path

    def write_csv(self, trades: List[Trade], run_label: str) -> str:
        path = os.path.join(self._output_dir, f"trades_{run_label}.csv")
        rows = []
        for t in trades:
            row = dataclasses.asdict(t)
            # Flatten enums and timedelta for CSV
            for k, v in row.items():
                if isinstance(v, Enum):
                    row[k] = v.value
                elif isinstance(v, timedelta):
                    row[k] = v.total_seconds()
                elif isinstance(v, datetime):
                    row[k] = v.isoformat()
                elif isinstance(v, list):
                    row[k] = "|".join(str(x) for x in v)
            rows.append(row)
        df = pd.DataFrame(rows)
        df.to_csv(path, index=False, encoding="utf-8")
        logger.info("Wrote %d trades to %s", len(trades), path)
        return path

    def write_summary(
        self,
        trades: List[Trade],
        skipped_rows: list,
        validation_errors: list,
        run_label: str,
    ) -> str:
        path = os.path.join(self._output_dir, f"import_summary_{run_label}.json")
        summary = {
            "run_label": run_label,
            "trades_written": len(trades),
            "rows_skipped": len(skipped_rows),
            "validation_error_count": len(validation_errors),
            "validation_errors": [
                {"trade_id": e.trade_id, "field": e.field, "message": e.message}
                for e in validation_errors
            ],
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=self._json_indent, ensure_ascii=False)
        logger.info("Import summary written to %s", path)
        return path
