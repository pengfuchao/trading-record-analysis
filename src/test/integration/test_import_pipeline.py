import json
import os

import pandas as pd
import pytest

from src.main.python.models.account import Account
from src.main.python.models.enums import Platform
from src.main.python.services.csv_parser import MTCSVParser
from src.main.python.services.output_writer import OutputWriter

FIXTURE_DIR = "src/test/integration/fixtures"
MT5_FIXTURE = os.path.join(FIXTURE_DIR, "sample_mt5.csv")
MT4_FIXTURE = os.path.join(FIXTURE_DIR, "sample_mt4.csv")


@pytest.fixture
def mt5_account():
    return Account(account_id="ACC001", broker="FTMO", platform=Platform.MT5)


@pytest.fixture
def mt4_account():
    return Account(account_id="ACC002", broker="IC Markets", platform=Platform.MT4)


@pytest.fixture
def parser_and_writer(tmp_path):
    cfg_path = tmp_path / "app_config.yaml"
    output_dir = str(tmp_path / "output")
    cfg_path.write_text(
        f"""
paths:
  input_dir: "input/"
  output_dir: "{output_dir}/"
  mt_column_map: "src/main/resources/config/mt_column_map.yaml"
logging:
  level: "WARNING"
output:
  formats: ["json", "csv"]
  timestamp_format: "%Y%m%d_%H%M%S"
  json_indent: 2
import:
  skip_invalid_rows: true
  encoding: "utf-8"
""",
        encoding="utf-8",
    )
    cfg = {
        "paths": {"output_dir": output_dir + "/", "mt_column_map": "src/main/resources/config/mt_column_map.yaml"},
        "output": {"formats": ["json", "csv"], "timestamp_format": "%Y%m%d_%H%M%S", "json_indent": 2},
    }
    return MTCSVParser(config_path=str(cfg_path)), OutputWriter(cfg)


class TestMT5ImportPipeline:
    def test_full_pipeline_produces_trades(self, parser_and_writer, mt5_account):
        parser, writer = parser_and_writer
        trades = parser.parse(MT5_FIXTURE, mt5_account)
        assert len(trades) == 9  # 10 rows minus 1 balance deposit

    def test_all_trades_have_result(self, parser_and_writer, mt5_account):
        parser, writer = parser_and_writer
        trades = parser.parse(MT5_FIXTURE, mt5_account)
        assert all(t.result is not None for t in trades)

    def test_all_trades_have_asset_class(self, parser_and_writer, mt5_account):
        parser, writer = parser_and_writer
        trades = parser.parse(MT5_FIXTURE, mt5_account)
        assert all(t.asset_class is not None for t in trades)

    def test_json_output_written(self, parser_and_writer, mt5_account):
        parser, writer = parser_and_writer
        trades = parser.parse(MT5_FIXTURE, mt5_account)
        path = writer.write_json(trades, "test_run")
        assert os.path.exists(path)
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        assert len(data) == 9
        assert "symbol" in data[0]
        assert "result" in data[0]

    def test_csv_output_written(self, parser_and_writer, mt5_account):
        parser, writer = parser_and_writer
        trades = parser.parse(MT5_FIXTURE, mt5_account)
        path = writer.write_csv(trades, "test_run")
        assert os.path.exists(path)
        df = pd.read_csv(path)
        assert len(df) == 9
        assert "symbol" in df.columns

    def test_summary_output_written(self, parser_and_writer, mt5_account):
        parser, writer = parser_and_writer
        trades = parser.parse(MT5_FIXTURE, mt5_account)
        path = writer.write_summary(trades, parser.skipped_rows, parser.validation_errors, "test_run")
        assert os.path.exists(path)
        with open(path, encoding="utf-8") as f:
            summary = json.load(f)
        assert summary["trades_written"] == 9
        assert summary["rows_skipped"] == 0

    def test_no_sl_trade_has_none_r_multiple(self, parser_and_writer, mt5_account):
        parser, writer = parser_and_writer
        trades = parser.parse(MT5_FIXTURE, mt5_account)
        no_sl_trade = next(t for t in trades if t.trade_id == "12345005")
        assert no_sl_trade.actual_r_multiple is None


class TestMT4ImportPipeline:
    def test_mt4_full_pipeline(self, parser_and_writer, mt4_account):
        parser, writer = parser_and_writer
        trades = parser.parse(MT4_FIXTURE, mt4_account)
        assert len(trades) == 9

    def test_mt4_csv_output_readable(self, parser_and_writer, mt4_account):
        parser, writer = parser_and_writer
        trades = parser.parse(MT4_FIXTURE, mt4_account)
        path = writer.write_csv(trades, "mt4_test_run")
        df = pd.read_csv(path)
        assert len(df) == 9
        assert "direction" in df.columns
