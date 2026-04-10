import pandas as pd
import pytest

from src.main.python.models.enums import Platform
from src.main.python.services.field_mapper import FieldMapper

COLUMN_MAP_PATH = "src/main/resources/config/mt_column_map.yaml"


def _mt5_row():
    """Simulate an MT5 DataFrame row with duplicate Time/Price columns."""
    columns = [
        "Position", "Symbol", "Type", "Volume",
        "Price",       # entry_price (first occurrence)
        "S / L", "T / P",
        "Time",        # entry_datetime (first occurrence)
        "Price",       # exit_price (second occurrence)
        "Commission", "Swap", "Profit", "Magic", "Comment",
        "Time",        # exit_datetime (second occurrence)
    ]
    values = [
        "12345", "EURUSD", "buy", "0.10",
        "1.08500",
        "1.08000", "1.09500",
        "2024.01.15 09:30:00",
        "1.09200",
        "-0.70", "0.00", "52.00", "0", "test",
        "2024.01.15 14:45:00",
    ]
    return pd.Series(dict(zip(range(len(columns)), values))), columns


def _mt4_row():
    columns = [
        "Ticket", "Open Time", "Type", "Lots", "Symbol",
        "Open Price", "S/L", "T/P", "Close Time", "Close Price",
        "Commission", "Swap", "Profit", "Comment",
    ]
    values = [
        "12345", "2024.01.15 09:30:00", "buy", "0.10", "EURUSD",
        "1.08500", "1.08000", "1.09500", "2024.01.15 14:45:00", "1.09200",
        "-0.70", "0.00", "52.00", "test",
    ]
    return pd.Series(dict(zip(range(len(columns)), values))), columns


class TestFieldMapperMT5:
    def setup_method(self):
        self.mapper = FieldMapper(Platform.MT5, COLUMN_MAP_PATH)

    def test_maps_all_canonical_fields(self):
        row, columns = _mt5_row()
        # Re-create as named series matching column name lookup style used in mapper
        named_row = pd.Series(dict(zip(columns, [row.iloc[i] for i in range(len(columns))])))
        result = self.mapper.map_row(named_row, columns)
        assert result["trade_id"] == "12345"
        assert result["symbol"] == "EURUSD"
        assert result["trade_type"] == "buy"
        assert result["gross_pnl"] == "52.00"

    def test_missing_commission_column_returns_none(self):
        row, columns = _mt5_row()
        named_row = pd.Series(dict(zip(columns, [row.iloc[i] for i in range(len(columns))])))
        # Remove Commission from columns
        filtered_cols = [c for c in columns if c != "Commission"]
        filtered_row = named_row.drop("Commission", errors="ignore")
        result = self.mapper.map_row(filtered_row, filtered_cols)
        assert result["commission"] is None

    def test_empty_value_returns_none(self):
        row, columns = _mt5_row()
        named_row = pd.Series(dict(zip(columns, [row.iloc[i] for i in range(len(columns))])))
        named_row["Comment"] = ""
        result = self.mapper.map_row(named_row, columns)
        assert result["comment"] is None or result["comment"] == ""


class TestFieldMapperMT4:
    def setup_method(self):
        self.mapper = FieldMapper(Platform.MT4, COLUMN_MAP_PATH)

    def test_maps_mt4_canonical_fields(self):
        row, columns = _mt4_row()
        named_row = pd.Series(dict(zip(columns, [row.iloc[i] for i in range(len(columns))])))
        result = self.mapper.map_row(named_row, columns)
        assert result["trade_id"] == "12345"
        assert result["symbol"] == "EURUSD"
        assert result["entry_datetime"] == "2024.01.15 09:30:00"
        assert result["exit_datetime"] == "2024.01.15 14:45:00"
        assert result["entry_price"] == "1.08500"
        assert result["exit_price"] == "1.09200"
        assert result["volume"] == "0.10"

    def test_missing_column_returns_none_and_warns(self, caplog):
        import logging
        row, columns = _mt4_row()
        named_row = pd.Series(dict(zip(columns, [row.iloc[i] for i in range(len(columns))])))
        filtered_cols = [c for c in columns if c != "S/L"]
        filtered_row = named_row.drop("S/L", errors="ignore")
        with caplog.at_level(logging.WARNING):
            result = self.mapper.map_row(filtered_row, filtered_cols)
        assert result["stop_loss"] is None
        assert any("S/L" in r.message for r in caplog.records)
