from typing import Any, Dict, List, Optional

import pandas as pd

from src.main.python.models.enums import Platform
from src.main.python.utils.config_loader import load_yaml
from src.main.python.utils.logging_utils import get_logger

logger = get_logger(__name__)

# Canonical fields that may appear more than once under the same column name in MT5.
# The tuple value is (first_occurrence_field, second_occurrence_field).
_MT5_DUPLICATE_COLS = {
    "Time": ("entry_datetime", "exit_datetime"),
    "Price": ("entry_price", "exit_price"),
}


class FieldMapper:
    """
    Translates a raw pandas DataFrame row (with platform-specific column names)
    into a dict keyed by canonical field names.

    All values are returned as raw strings. Type coercion is the parser's job.
    """

    def __init__(self, platform: Platform, column_map_path: str) -> None:
        config = load_yaml(column_map_path)
        platform_key = "mt5" if platform == Platform.MT5 else "mt4"
        self._mapping: Dict[str, str] = config["platforms"][platform_key]
        self._platform = platform

    def map_row(self, row: pd.Series, df_columns: List[str]) -> Dict[str, Optional[str]]:
        """
        Map one DataFrame row to a canonical field dict.

        For MT5 duplicate columns (Time, Price), the first and second occurrences
        in df_columns are resolved by index position.
        """
        result: Dict[str, Optional[Any]] = {}

        # Pre-compute positional indices for duplicate column names (MT5 only)
        duplicate_indices: Dict[str, List[int]] = {}
        if self._platform == Platform.MT5:
            for col_name in _MT5_DUPLICATE_COLS:
                indices = [i for i, c in enumerate(df_columns) if c == col_name]
                if indices:
                    duplicate_indices[col_name] = indices

        for canonical_field, source_col in self._mapping.items():
            value = self._resolve_field(
                canonical_field, source_col, row, df_columns, duplicate_indices
            )
            result[canonical_field] = value

        return result

    def _resolve_field(
        self,
        canonical_field: str,
        source_col: str,
        row: pd.Series,
        df_columns: List[str],
        duplicate_indices: Dict[str, List[int]],
    ) -> Optional[str]:
        # Handle MT5 duplicate columns by positional index
        if self._platform == Platform.MT5 and source_col in _MT5_DUPLICATE_COLS:
            first_field, second_field = _MT5_DUPLICATE_COLS[source_col]
            indices = duplicate_indices.get(source_col, [])
            if canonical_field == first_field and len(indices) >= 1:
                return self._get_by_index(row, indices[0])
            elif canonical_field == second_field and len(indices) >= 2:
                return self._get_by_index(row, indices[1])
            else:
                logger.warning(
                    "Duplicate column '%s' not found at expected index for field '%s' — setting to None",
                    source_col,
                    canonical_field,
                )
                return None

        # Standard lookup by column name
        if source_col not in df_columns:
            logger.warning(
                "Column '%s' not found in CSV for field '%s' — setting to None",
                source_col,
                canonical_field,
            )
            return None

        raw = row.get(source_col)
        if pd.isna(raw):
            return None
        return str(raw).strip()

    @staticmethod
    def _get_by_index(row: pd.Series, index: int) -> Optional[str]:
        try:
            raw = row.iloc[index]
            if pd.isna(raw):
                return None
            return str(raw).strip()
        except IndexError:
            return None
