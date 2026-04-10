from datetime import datetime

import pytest

from src.main.python.models.enums import Direction, Platform, TradeResult
from src.main.python.models.trade import Trade
from src.main.python.services.validator import TradeValidator


def _valid_trade(**overrides) -> Trade:
    defaults = dict(
        trade_id="T001",
        account_id="ACC001",
        symbol="EURUSD",
        entry_datetime=datetime(2024, 1, 15, 9, 30),
        exit_datetime=datetime(2024, 1, 15, 14, 45),
        lot_size=0.10,
        entry_price=1.08500,
    )
    defaults.update(overrides)
    return Trade(**defaults)


@pytest.fixture
def validator():
    return TradeValidator()


class TestTradeValidator:
    def test_valid_trade_has_no_errors(self, validator):
        assert validator.validate(_valid_trade()) == []

    def test_missing_trade_id_fails(self, validator):
        errors = validator.validate(_valid_trade(trade_id=None))
        assert any(e.field == "trade_id" for e in errors)

    def test_empty_trade_id_fails(self, validator):
        errors = validator.validate(_valid_trade(trade_id=""))
        assert any(e.field == "trade_id" for e in errors)

    def test_missing_symbol_fails(self, validator):
        errors = validator.validate(_valid_trade(symbol=None))
        assert any(e.field == "symbol" for e in errors)

    def test_missing_entry_datetime_fails(self, validator):
        errors = validator.validate(_valid_trade(entry_datetime=None))
        assert any(e.field == "entry_datetime" for e in errors)

    def test_missing_exit_datetime_fails(self, validator):
        errors = validator.validate(_valid_trade(exit_datetime=None))
        assert any(e.field == "exit_datetime" for e in errors)

    def test_exit_before_entry_fails(self, validator):
        errors = validator.validate(
            _valid_trade(
                entry_datetime=datetime(2024, 1, 15, 14, 0),
                exit_datetime=datetime(2024, 1, 15, 9, 0),
            )
        )
        assert any(e.field == "exit_datetime" for e in errors)

    def test_zero_lot_size_fails(self, validator):
        errors = validator.validate(_valid_trade(lot_size=0.0))
        assert any(e.field == "lot_size" for e in errors)

    def test_negative_lot_size_fails(self, validator):
        errors = validator.validate(_valid_trade(lot_size=-0.1))
        assert any(e.field == "lot_size" for e in errors)

    def test_negative_entry_price_fails(self, validator):
        errors = validator.validate(_valid_trade(entry_price=-1.0))
        assert any(e.field == "entry_price" for e in errors)

    def test_multiple_errors_all_returned(self, validator):
        trade = _valid_trade(trade_id=None, symbol=None, entry_datetime=None)
        errors = validator.validate(trade)
        assert len(errors) >= 3

    def test_none_lot_size_passes(self, validator):
        errors = validator.validate(_valid_trade(lot_size=None))
        assert not any(e.field == "lot_size" for e in errors)
