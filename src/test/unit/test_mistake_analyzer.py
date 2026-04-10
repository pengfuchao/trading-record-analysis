"""
Unit tests for MistakeAnalyzer — no database required.
All tests use plain Trade dataclasses.
"""
from datetime import datetime, timedelta

import pytest

from src.main.python.core.mistake_analyzer import MistakeAnalyzer, _BOOLEAN_FLAG_MAP
from src.main.python.models.enums import TradeResult
from src.main.python.models.trade import Trade

analyzer = MistakeAnalyzer()


# ── Helpers ───────────────────────────────────────────────────────────────────

def make_trade(
    trade_id: str = "T001",
    account_id: str = "ACC001",
    result: TradeResult = TradeResult.WIN,
    net_pnl: float = 100.0,
    exit_datetime: datetime = None,
    session: str = "London",
    symbol: str = "EURUSD",
    mistake_tags=None,
    **flags,
) -> Trade:
    return Trade(
        trade_id=trade_id,
        account_id=account_id,
        result=result,
        net_pnl=net_pnl,
        exit_datetime=exit_datetime or datetime(2024, 1, 15, 10, 0),
        session=session,
        symbol=symbol,
        mistake_tags=mistake_tags or [],
        **flags,
    )


# ── _extract_tags ─────────────────────────────────────────────────────────────

class TestExtractTags:
    def test_no_flags_no_tags(self):
        trade = make_trade()
        assert MistakeAnalyzer._extract_tags(trade) == []

    def test_single_boolean_flag_true(self):
        trade = make_trade(fomo=True)
        assert "fomo" in MistakeAnalyzer._extract_tags(trade)

    def test_false_boolean_flag_excluded(self):
        trade = make_trade(fomo=False, chasing=False)
        assert MistakeAnalyzer._extract_tags(trade) == []

    def test_none_boolean_flag_excluded(self):
        trade = make_trade(fomo=None)
        assert MistakeAnalyzer._extract_tags(trade) == []

    def test_all_boolean_flags_true(self):
        flags = {attr: True for attr in _BOOLEAN_FLAG_MAP}
        trade = make_trade(**flags)
        tags = MistakeAnalyzer._extract_tags(trade)
        for canonical in _BOOLEAN_FLAG_MAP.values():
            assert canonical in tags

    def test_followed_plan_false_adds_plan_violation(self):
        trade = make_trade(followed_plan=False)
        assert "plan_violation" in MistakeAnalyzer._extract_tags(trade)

    def test_followed_plan_true_no_plan_violation(self):
        trade = make_trade(followed_plan=True)
        assert "plan_violation" not in MistakeAnalyzer._extract_tags(trade)

    def test_followed_plan_none_no_plan_violation(self):
        trade = make_trade(followed_plan=None)
        assert "plan_violation" not in MistakeAnalyzer._extract_tags(trade)

    def test_is_a_plus_setup_false_not_a_mistake(self):
        trade = make_trade(is_a_plus_setup=False)
        assert MistakeAnalyzer._extract_tags(trade) == []

    def test_explicit_tags_merged(self):
        trade = make_trade(mistake_tags=["poor_location", "incorrect_sizing"])
        tags = MistakeAnalyzer._extract_tags(trade)
        assert "poor_location" in tags
        assert "incorrect_sizing" in tags

    def test_deduplication_flag_and_explicit_same_tag(self):
        trade = make_trade(fomo=True, mistake_tags=["fomo"])
        tags = MistakeAnalyzer._extract_tags(trade)
        assert tags.count("fomo") == 1

    def test_empty_string_in_mistake_tags_ignored(self):
        trade = make_trade(mistake_tags=["", "  "])
        # Empty/whitespace-only strings should not create tags
        assert MistakeAnalyzer._extract_tags(trade) == []

    def test_whitespace_stripped_from_explicit_tags(self):
        trade = make_trade(mistake_tags=["  fomo  "])
        tags = MistakeAnalyzer._extract_tags(trade)
        assert "fomo" in tags


# ── generate_report ───────────────────────────────────────────────────────────

class TestGenerateReport:
    def test_empty_trades_returns_empty_report(self):
        report = analyzer.generate_report([], "ACC001")
        assert report.account_id == "ACC001"
        assert report.total_trades_analyzed == 0
        assert report.by_mistake == {}
        assert report.ranked_by_frequency == []
        assert report.ranked_by_cost == []

    def test_no_mistakes_all_clean(self):
        trades = [make_trade(f"T{i}") for i in range(3)]
        report = analyzer.generate_report(trades, "ACC001")
        assert report.total_trades_analyzed == 3
        assert report.trades_with_any_mistake == 0
        assert report.mistake_rate == 0.0
        assert report.by_mistake == {}

    def test_occurrence_count(self):
        trades = [
            make_trade("T1", fomo=True),
            make_trade("T2", fomo=True),
            make_trade("T3", fomo=False),
        ]
        report = analyzer.generate_report(trades, "ACC001")
        assert report.by_mistake["fomo"].occurrence_count == 2

    def test_occurrence_pct(self):
        trades = [
            make_trade("T1", fomo=True),
            make_trade("T2"),
            make_trade("T3"),
            make_trade("T4"),
        ]
        report = analyzer.generate_report(trades, "ACC001")
        assert report.by_mistake["fomo"].occurrence_pct == pytest.approx(0.25)

    def test_total_cost(self):
        trades = [
            make_trade("T1", fomo=True, net_pnl=-50.0, result=TradeResult.LOSS),
            make_trade("T2", fomo=True, net_pnl=-30.0, result=TradeResult.LOSS),
            make_trade("T3"),
        ]
        report = analyzer.generate_report(trades, "ACC001")
        assert report.by_mistake["fomo"].total_cost == pytest.approx(-80.0)
        assert report.by_mistake["fomo"].avg_cost_per_trade == pytest.approx(-40.0)

    def test_total_cost_with_none_pnl_treated_as_zero(self):
        trade = make_trade("T1", fomo=True, net_pnl=None)
        trade.net_pnl = None
        report = analyzer.generate_report([trade], "ACC001")
        assert report.by_mistake["fomo"].total_cost == pytest.approx(0.0)

    def test_win_rate_per_mistake(self):
        trades = [
            make_trade("T1", fomo=True, result=TradeResult.WIN),
            make_trade("T2", fomo=True, result=TradeResult.LOSS),
            make_trade("T3", fomo=True, result=TradeResult.LOSS),
        ]
        report = analyzer.generate_report(trades, "ACC001")
        stats = report.by_mistake["fomo"]
        assert stats.win_rate == pytest.approx(1 / 3)
        assert stats.loss_rate == pytest.approx(2 / 3)

    def test_frequency_ranking_order(self):
        trades = [
            make_trade("T1", fomo=True),
            make_trade("T2", fomo=True),
            make_trade("T3", fomo=True),
            make_trade("T4", chasing=True),
            make_trade("T5", chasing=True),
            make_trade("T6", revenge_trade=True),
        ]
        report = analyzer.generate_report(trades, "ACC001")
        assert report.ranked_by_frequency[0] == "fomo"
        assert report.ranked_by_frequency[1] == "chasing"
        assert report.ranked_by_frequency[2] == "revenge_trade"

    def test_cost_ranking_order(self):
        trades = [
            make_trade("T1", fomo=True, net_pnl=-200.0, result=TradeResult.LOSS),
            make_trade("T2", chasing=True, net_pnl=-50.0, result=TradeResult.LOSS),
        ]
        report = analyzer.generate_report(trades, "ACC001")
        # fomo costs more (−200) → should be ranked first (worst)
        assert report.ranked_by_cost[0] == "fomo"
        assert report.ranked_by_cost[1] == "chasing"

    def test_trades_with_any_mistake_count(self):
        trades = [
            make_trade("T1", fomo=True),
            make_trade("T2", chasing=True, fomo=True),  # multiple flags, counts once
            make_trade("T3"),                             # clean
        ]
        report = analyzer.generate_report(trades, "ACC001")
        assert report.trades_with_any_mistake == 2
        assert report.mistake_rate == pytest.approx(2 / 3)

    def test_by_session_breakdown(self):
        trades = [
            make_trade("T1", fomo=True, session="London"),
            make_trade("T2", fomo=True, session="London"),
            make_trade("T3", fomo=True, session="New York"),
        ]
        report = analyzer.generate_report(trades, "ACC001")
        by_session = report.by_mistake["fomo"].by_session
        assert by_session["London"] == 2
        assert by_session["New York"] == 1

    def test_by_symbol_breakdown(self):
        trades = [
            make_trade("T1", chasing=True, symbol="EURUSD"),
            make_trade("T2", chasing=True, symbol="GBPUSD"),
            make_trade("T3", chasing=True, symbol="EURUSD"),
        ]
        report = analyzer.generate_report(trades, "ACC001")
        by_symbol = report.by_mistake["chasing"].by_symbol
        assert by_symbol["EURUSD"] == 2
        assert by_symbol["GBPUSD"] == 1

    def test_by_session_excludes_none_session(self):
        trades = [
            make_trade("T1", fomo=True, session=None),
            make_trade("T2", fomo=True, session="London"),
        ]
        trades[0].session = None
        report = analyzer.generate_report(trades, "ACC001")
        by_session = report.by_mistake["fomo"].by_session
        assert None not in by_session
        assert "London" in by_session

    def test_after_loss_rate_revenge_trade(self):
        """Revenge trades that follow losses should have high after_loss_rate."""
        trades = [
            make_trade("T1", result=TradeResult.LOSS, net_pnl=-100.0,
                       exit_datetime=datetime(2024, 1, 1, 10, 0)),
            make_trade("T2", revenge_trade=True, result=TradeResult.LOSS, net_pnl=-50.0,
                       exit_datetime=datetime(2024, 1, 1, 11, 0)),
            make_trade("T3", revenge_trade=True, result=TradeResult.WIN, net_pnl=80.0,
                       exit_datetime=datetime(2024, 1, 1, 12, 0)),
        ]
        report = analyzer.generate_report(trades, "ACC001")
        # T2 follows a LOSS (T1), T3 follows a LOSS (T2) → 2/2 = 1.0
        assert report.by_mistake["revenge_trade"].after_loss_rate == pytest.approx(1.0)

    def test_after_loss_rate_first_trade_excluded(self):
        """The very first trade has no preceding trade — never counted as 'after loss'."""
        trades = [
            make_trade("T1", fomo=True, exit_datetime=datetime(2024, 1, 1, 10, 0)),
        ]
        report = analyzer.generate_report(trades, "ACC001")
        assert report.by_mistake["fomo"].after_loss_rate == pytest.approx(0.0)

    def test_after_loss_rate_mixed(self):
        trades = [
            make_trade("T1", result=TradeResult.WIN, net_pnl=100.0,
                       exit_datetime=datetime(2024, 1, 1, 9, 0)),
            make_trade("T2", fomo=True, result=TradeResult.LOSS, net_pnl=-50.0,
                       exit_datetime=datetime(2024, 1, 1, 10, 0)),   # follows WIN → not counted
            make_trade("T3", result=TradeResult.LOSS, net_pnl=-80.0,
                       exit_datetime=datetime(2024, 1, 1, 11, 0)),
            make_trade("T4", fomo=True, result=TradeResult.WIN, net_pnl=60.0,
                       exit_datetime=datetime(2024, 1, 1, 12, 0)),   # follows LOSS → counted
        ]
        report = analyzer.generate_report(trades, "ACC001")
        # T2 follows WIN, T4 follows LOSS → after_loss_rate = 1/2 = 0.5
        assert report.by_mistake["fomo"].after_loss_rate == pytest.approx(0.5)

    def test_plan_violation_tag_from_followed_plan_false(self):
        trades = [make_trade("T1", followed_plan=False)]
        report = analyzer.generate_report(trades, "ACC001")
        assert "plan_violation" in report.by_mistake

    def test_explicit_mistake_tags_counted(self):
        trades = [
            make_trade("T1", mistake_tags=["poor_location"]),
            make_trade("T2", mistake_tags=["poor_location", "incorrect_sizing"]),
        ]
        report = analyzer.generate_report(trades, "ACC001")
        assert report.by_mistake["poor_location"].occurrence_count == 2
        assert report.by_mistake["incorrect_sizing"].occurrence_count == 1

    def test_multiple_tags_on_one_trade_counted_separately(self):
        trades = [make_trade("T1", fomo=True, chasing=True, overtrading=True)]
        report = analyzer.generate_report(trades, "ACC001")
        assert report.by_mistake["fomo"].occurrence_count == 1
        assert report.by_mistake["chasing"].occurrence_count == 1
        assert report.by_mistake["overtrading"].occurrence_count == 1
        # Trade still only counted once as "has any mistake"
        assert report.trades_with_any_mistake == 1

    def test_account_id_in_report(self):
        report = analyzer.generate_report([], "MY_ACCOUNT")
        assert report.account_id == "MY_ACCOUNT"

    def test_generated_at_is_set(self):
        report = analyzer.generate_report([], "ACC001")
        assert isinstance(report.generated_at, datetime)
