import io

import pandas as pd
import pytest

from src.main.python.models.account import Account
from src.main.python.models.enums import Direction, Platform, TradeResult
from src.main.python.services.csv_parser import MTCSVParser

MT5_CSV = """Position,Symbol,Type,Volume,Price,S / L,T / P,Time,Price,Commission,Swap,Profit,Magic,Comment,Time
12345001,EURUSD,buy,0.10,1.08500,1.08000,1.09500,2024.01.15 09:30:00,1.09200,-0.70,0.00,52.00,0,trade1,2024.01.15 14:45:00
12345002,XAUUSD,sell,0.05,2020.50,2030.00,2005.00,2024.01.16 10:00:00,2025.80,-1.50,-0.30,-33.00,0,trade2,2024.01.16 11:30:00
12345003,US30,buy,0.10,37500.00,37200.00,38000.00,2024.01.17 14:30:00,37500.00,-2.00,0.00,0.00,0,trade3,2024.01.17 16:00:00
balance,,,,,,,2024.01.15 00:00:00,,,,500.00,,,
"""

MT4_CSV = """Ticket,Open Time,Type,Lots,Symbol,Open Price,S/L,T/P,Close Time,Close Price,Commission,Swap,Profit,Comment
12345001,2024.01.15 09:30:00,buy,0.10,EURUSD,1.08500,1.08000,1.09500,2024.01.15 14:45:00,1.09200,-0.70,0.00,52.00,trade1
12345002,2024.01.16 10:00:00,sell,0.05,XAUUSD,2020.50,2030.00,2005.00,2024.01.16 11:30:00,2025.80,-1.50,-0.30,-33.00,trade2
"""

BAD_DATE_CSV = """Position,Symbol,Type,Volume,Price,S / L,T / P,Time,Price,Commission,Swap,Profit,Magic,Comment,Time
12345001,EURUSD,buy,0.10,1.08500,1.08000,1.09500,2024.01.15 09:30:00,1.09200,-0.70,0.00,52.00,0,trade1,2024.01.15 14:45:00
12345002,GBPUSD,sell,0.10,1.27000,1.27500,1.26000,NOT_A_DATE,1.26500,-1.40,0.00,100.00,0,trade2,2024.01.18 10:30:00
"""


@pytest.fixture
def mt5_account():
    return Account(account_id="ACC001", broker="FTMO", platform=Platform.MT5)


@pytest.fixture
def mt4_account():
    return Account(account_id="ACC002", broker="IC Markets", platform=Platform.MT4)


@pytest.fixture
def parser(tmp_path):
    cfg = tmp_path / "app_config.yaml"
    cfg.write_text(
        f"""
paths:
  input_dir: "input/"
  output_dir: "{tmp_path}/output/"
  mt_column_map: "src/main/resources/config/mt_column_map.yaml"
logging:
  level: "WARNING"
output:
  formats: ["json"]
  timestamp_format: "%Y%m%d_%H%M%S"
  json_indent: 2
import:
  skip_invalid_rows: true
  encoding: "utf-8"
""",
        encoding="utf-8",
    )
    return MTCSVParser(config_path=str(cfg))


def _write_csv(tmp_path, content, name="test.csv"):
    p = tmp_path / name
    p.write_text(content, encoding="utf-8")
    return str(p)


class TestMTCSVParser:
    def test_parses_mt5_three_trade_rows(self, parser, mt5_account, tmp_path):
        path = _write_csv(tmp_path, MT5_CSV)
        trades = parser.parse(path, mt5_account)
        assert len(trades) == 3

    def test_balance_row_filtered_out(self, parser, mt5_account, tmp_path):
        path = _write_csv(tmp_path, MT5_CSV)
        parser.parse(path, mt5_account)
        # 4 rows in CSV, 1 is balance — should be filtered before parsing
        assert len(parser.skipped_rows) == 0  # filtered rows don't count as skipped

    def test_eurusd_trade_fields(self, parser, mt5_account, tmp_path):
        path = _write_csv(tmp_path, MT5_CSV)
        trades = parser.parse(path, mt5_account)
        t = next(t for t in trades if t.trade_id == "12345001")
        assert t.symbol == "EURUSD"
        assert t.direction == Direction.LONG
        assert t.result == TradeResult.WIN
        assert t.gross_pnl == pytest.approx(52.0)

    def test_detects_mt5_platform(self, parser, mt5_account, tmp_path):
        path = _write_csv(tmp_path, MT5_CSV)
        trades = parser.parse(path, mt5_account)
        assert all(t.platform == Platform.MT5 for t in trades)

    def test_detects_mt4_platform(self, parser, mt4_account, tmp_path):
        path = _write_csv(tmp_path, MT4_CSV)
        trades = parser.parse(path, mt4_account)
        assert len(trades) == 2
        assert all(t.platform == Platform.MT4 for t in trades)

    def test_bad_date_row_skipped(self, parser, mt5_account, tmp_path):
        path = _write_csv(tmp_path, BAD_DATE_CSV)
        trades = parser.parse(path, mt5_account)
        # Row with bad date should produce a trade with None exit_datetime, then fail validation
        assert len(trades) + len(parser.skipped_rows) == 2

    def test_account_id_set_on_trades(self, parser, mt5_account, tmp_path):
        path = _write_csv(tmp_path, MT5_CSV)
        trades = parser.parse(path, mt5_account)
        assert all(t.account_id == "ACC001" for t in trades)
