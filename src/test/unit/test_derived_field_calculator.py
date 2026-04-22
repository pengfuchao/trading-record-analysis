from datetime import datetime, timedelta

import pytest

from src.main.python.models.enums import AssetClass, Direction, TradeResult
from src.main.python.services.derived_field_calculator import DerivedFieldCalculator
from src.main.python.utils.config_loader import load_yaml

COLUMN_MAP_PATH = "src/main/resources/config/mt_column_map.yaml"


@pytest.fixture
def asset_rules():
    return load_yaml(COLUMN_MAP_PATH)["asset_class_rules"]


@pytest.fixture
def calc():
    return DerivedFieldCalculator()


class TestCalcDirection:
    def test_buy_returns_long(self, calc):
        assert calc.calc_direction("buy") == Direction.LONG

    def test_sell_returns_short(self, calc):
        assert calc.calc_direction("sell") == Direction.SHORT

    def test_case_insensitive(self, calc):
        assert calc.calc_direction("BUY") == Direction.LONG
        assert calc.calc_direction("SELL") == Direction.SHORT

    def test_balance_returns_none(self, calc):
        assert calc.calc_direction("balance") is None

    def test_none_returns_none(self, calc):
        assert calc.calc_direction(None) is None


class TestCalcHoldingDuration:
    def test_calculates_duration(self, calc):
        entry = datetime(2024, 1, 15, 9, 30, 0)
        exit_ = datetime(2024, 1, 15, 11, 0, 0)
        assert calc.calc_holding_duration(entry, exit_) == timedelta(hours=1, minutes=30)

    def test_exit_before_entry_returns_none(self, calc):
        entry = datetime(2024, 1, 15, 11, 0, 0)
        exit_ = datetime(2024, 1, 15, 9, 0, 0)
        assert calc.calc_holding_duration(entry, exit_) is None

    def test_none_entry_returns_none(self, calc):
        assert calc.calc_holding_duration(None, datetime.now()) is None

    def test_none_exit_returns_none(self, calc):
        assert calc.calc_holding_duration(datetime.now(), None) is None


class TestCalcResult:
    def test_positive_pnl_is_win(self, calc):
        assert calc.calc_result(50.0) == TradeResult.WIN

    def test_negative_pnl_is_loss(self, calc):
        assert calc.calc_result(-20.0) == TradeResult.LOSS

    def test_zero_pnl_is_breakeven(self, calc):
        assert calc.calc_result(0.0) == TradeResult.BREAKEVEN

    def test_none_pnl_returns_none(self, calc):
        assert calc.calc_result(None) is None


class TestCalcNetPnl:
    def test_sums_correctly(self, calc):
        assert calc.calc_net_pnl(52.0, -0.70, 0.0) == pytest.approx(51.30)

    def test_none_commission_treated_as_zero(self, calc):
        assert calc.calc_net_pnl(52.0, None, None) == 52.0

    def test_none_gross_pnl_returns_none(self, calc):
        assert calc.calc_net_pnl(None, -1.0, 0.0) is None


class TestCalcActualR:
    def test_returns_float_for_valid_long(self, calc):
        # LONG: entry=1.0850, exit=1.0900, SL=1.0800 → R = 0.005/0.005 = 1.0
        result = calc.calc_actual_r(1.09000, 1.08500, 1.08000, Direction.LONG)
        assert result == pytest.approx(1.0)

    def test_returns_float_for_valid_short(self, calc):
        # SHORT: entry=2000, exit=1950, SL=2025 → R = 50/25 = 2.0
        result = calc.calc_actual_r(1950.0, 2000.0, 2025.0, Direction.SHORT)
        assert result == pytest.approx(2.0)

    def test_no_stop_loss_returns_none(self, calc):
        assert calc.calc_actual_r(1.09000, 1.08500, None, Direction.LONG) is None

    def test_zero_stop_loss_returns_none(self, calc):
        assert calc.calc_actual_r(1.09000, 1.08500, 0.0, Direction.LONG) is None

    def test_sl_equals_entry_returns_none(self, calc):
        # SL distance = 0 → undefined R
        assert calc.calc_actual_r(1.09000, 1.08500, 1.08500, Direction.LONG) is None

    def test_none_exit_price_returns_none(self, calc):
        assert calc.calc_actual_r(None, 1.08500, 1.08000, Direction.LONG) is None

    def test_none_direction_returns_none(self, calc):
        assert calc.calc_actual_r(1.09000, 1.08500, 1.08000, None) is None


class TestCalcAssetClass:
    def test_eurusd_is_forex(self, calc, asset_rules):
        assert calc.calc_asset_class("EURUSD", asset_rules) == AssetClass.FOREX

    def test_xauusd_is_gold(self, calc, asset_rules):
        assert calc.calc_asset_class("XAUUSD", asset_rules) == AssetClass.GOLD

    def test_us30_is_indices(self, calc, asset_rules):
        assert calc.calc_asset_class("US30", asset_rules) == AssetClass.INDICES

    def test_nas100_is_indices(self, calc, asset_rules):
        assert calc.calc_asset_class("NAS100", asset_rules) == AssetClass.INDICES

    def test_usoil_is_oil(self, calc, asset_rules):
        assert calc.calc_asset_class("USOIL", asset_rules) == AssetClass.OIL

    def test_broker_suffix_stripped(self, calc, asset_rules):
        assert calc.calc_asset_class("EURUSD.pro", asset_rules) == AssetClass.FOREX

    def test_unknown_symbol_returns_unknown(self, calc, asset_rules):
        assert calc.calc_asset_class("UNKNOWNSYM", asset_rules) == AssetClass.UNKNOWN

    def test_none_symbol_returns_unknown(self, calc, asset_rules):
        assert calc.calc_asset_class(None, asset_rules) == AssetClass.UNKNOWN
