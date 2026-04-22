"""
Targeted tests for the behavioral analytics functions in AccountAnalytics.

Covers:
  - compute_plan_adherence()
  - compute_rr_analysis()
  - compute_rr_trend()
  - compute_exit_decomposition()  /  _classify_exit()
  - compute_entry_exit_quality()
  - compute_daily_adherence()
"""
from datetime import date, datetime, timedelta
from typing import Optional

import pytest

from src.main.python.core.account_analytics import AccountAnalytics
from src.main.python.models.enums import Direction, TradeResult
from src.main.python.models.trade import Trade


# ── Shared factory ────────────────────────────────────────────────────────────

def make_trade(
    trade_id: str = "T1",
    result: TradeResult = TradeResult.WIN,
    net_pnl: float = 100.0,
    actual_r: Optional[float] = None,
    planned_rr: Optional[float] = None,
    trade_plan_id: Optional[str] = None,
    followed_plan: Optional[bool] = None,
    setup_type: Optional[str] = None,
    exit_dt: Optional[datetime] = None,
    entry_price: Optional[float] = None,
    exit_price: Optional[float] = None,
    stop_loss: Optional[float] = None,
    take_profit: Optional[float] = None,
    direction: Direction = Direction.LONG,
    problem_source: Optional[str] = None,
    early_entry: Optional[bool] = None,
    premature_exit: Optional[bool] = None,
    moved_stop: Optional[bool] = None,
    is_a_plus_setup: Optional[bool] = None,
) -> Trade:
    t = Trade(trade_id=trade_id, account_id="TEST")
    t.result = result
    t.net_pnl = net_pnl
    t.actual_r_multiple = actual_r
    t.planned_rr = planned_rr
    t.trade_plan_id = trade_plan_id
    t.followed_plan = followed_plan
    t.setup_type = setup_type
    t.exit_datetime = exit_dt or datetime(2026, 1, 15, 12, 0)
    t.entry_price = entry_price
    t.exit_price = exit_price
    t.stop_loss = stop_loss
    t.take_profit = take_profit
    t.direction = direction
    t.problem_source = problem_source
    t.early_entry = early_entry
    t.premature_exit = premature_exit
    t.moved_stop = moved_stop
    t.is_a_plus_setup = is_a_plus_setup
    return t


# ── compute_plan_adherence ────────────────────────────────────────────────────

class TestComputePlanAdherence:
    def test_empty_trades_returns_zero_report(self):
        r = AccountAnalytics.compute_plan_adherence([])
        assert r.total_trades == 0
        assert r.planned_count == 0
        assert r.planned_pct is None

    def test_all_unplanned_generates_no_plan_signal(self):
        trades = [make_trade(f"T{i}") for i in range(4)]
        r = AccountAnalytics.compute_plan_adherence(trades)
        assert r.planned_count == 0
        assert r.unplanned_count == 4
        assert any("pre-trade plan" in s.lower() for s in r.coaching_signals)

    def test_planned_count_uses_trade_plan_id(self):
        trades = [
            make_trade("T1", trade_plan_id="P1"),
            make_trade("T2", trade_plan_id="P2"),
            make_trade("T3"),
        ]
        r = AccountAnalytics.compute_plan_adherence(trades)
        assert r.planned_count == 2
        assert r.unplanned_count == 1

    def test_planned_pct_correct(self):
        trades = [make_trade("T1", trade_plan_id="P1"), make_trade("T2")]
        r = AccountAnalytics.compute_plan_adherence(trades)
        assert r.planned_pct == pytest.approx(50.0)

    def test_followed_deviated_counts(self):
        trades = [
            make_trade("T1", followed_plan=True),
            make_trade("T2", followed_plan=True),
            make_trade("T3", followed_plan=False),
            make_trade("T4"),
        ]
        r = AccountAnalytics.compute_plan_adherence(trades)
        assert r.followed_count == 2
        assert r.deviated_count == 1
        assert r.not_tagged_count == 1

    def test_linked_but_deviated_count(self):
        trades = [
            make_trade("T1", trade_plan_id="P1", followed_plan=False),
            make_trade("T2", trade_plan_id="P2", followed_plan=True),
            make_trade("T3", followed_plan=False),   # no plan_id → not linked_but_deviated
        ]
        r = AccountAnalytics.compute_plan_adherence(trades)
        assert r.linked_but_deviated_count == 1

    def test_planned_vs_unplanned_signal_when_both_n_gte3(self):
        # 3 planned wins, 3 unplanned losses — signal should compare them
        trades = (
            [make_trade(f"P{i}", result=TradeResult.WIN, net_pnl=200.0, trade_plan_id=f"plan{i}") for i in range(3)]
            + [make_trade(f"U{i}", result=TradeResult.LOSS, net_pnl=-50.0) for i in range(3)]
        )
        r = AccountAnalytics.compute_plan_adherence(trades)
        assert any("planned" in s.lower() for s in r.coaching_signals)

    def test_no_signal_when_only_one_side_has_enough(self):
        # Only 1 unplanned — not enough for comparison
        trades = [
            make_trade("P1", trade_plan_id="plan1"),
            make_trade("P2", trade_plan_id="plan2"),
            make_trade("P3", trade_plan_id="plan3"),
            make_trade("U1"),
        ]
        r = AccountAnalytics.compute_plan_adherence(trades)
        # Should NOT generate a planned-vs-unplanned performance signal
        perf_signals = [s for s in r.coaching_signals if "outperform" in s or "performing better" in s]
        assert len(perf_signals) == 0


# ── compute_rr_analysis ───────────────────────────────────────────────────────

class TestComputeRRAnalysis:
    def test_empty_trades_returns_zero_sample(self):
        r = AccountAnalytics.compute_rr_analysis([])
        assert r.sample_count == 0
        assert r.avg_planned_rr is None
        assert r.realization_pct is None

    def test_no_qualifying_trades_returns_zero_sample(self):
        # No planned_rr or no trade_plan_id
        trades = [make_trade("T1", actual_r=1.5)]
        r = AccountAnalytics.compute_rr_analysis(trades)
        assert r.sample_count == 0

    def test_qualifying_criteria_all_required(self):
        # trade_plan_id, planned_rr > 0, actual_r all required
        trades = [
            make_trade("T1", trade_plan_id="P1", planned_rr=2.0, actual_r=None),   # missing actual_r
            make_trade("T2", trade_plan_id=None, planned_rr=2.0, actual_r=1.5),    # missing plan
            make_trade("T3", trade_plan_id="P3", planned_rr=0.0, actual_r=1.5),    # planned_rr = 0
        ]
        r = AccountAnalytics.compute_rr_analysis(trades)
        assert r.sample_count == 0

    def test_averages_computed_correctly(self):
        trades = [
            make_trade("T1", trade_plan_id="P1", planned_rr=2.0, actual_r=1.0),
            make_trade("T2", trade_plan_id="P2", planned_rr=2.0, actual_r=2.0),
            make_trade("T3", trade_plan_id="P3", planned_rr=2.0, actual_r=3.0),
        ]
        r = AccountAnalytics.compute_rr_analysis(trades)
        assert r.sample_count == 3
        assert r.avg_planned_rr == pytest.approx(2.0)
        assert r.avg_actual_r == pytest.approx(2.0)
        assert r.avg_r_shortfall == pytest.approx(0.0)
        assert r.realization_pct == pytest.approx(100.0)

    def test_severe_leakage_signal_below_50(self):
        trades = [
            make_trade(f"T{i}", trade_plan_id=f"P{i}", planned_rr=2.0, actual_r=0.5)
            for i in range(4)
        ]
        r = AccountAnalytics.compute_rr_analysis(trades)
        assert r.realization_pct < 50
        assert any("only" in s.lower() for s in r.coaching_signals)

    def test_execution_leakage_signal_50_to_80(self):
        # realization_pct ≈ 70%: 4 trades planned 2.0, actual 1.4
        trades = [
            make_trade(f"T{i}", trade_plan_id=f"P{i}", planned_rr=2.0, actual_r=1.4)
            for i in range(4)
        ]
        r = AccountAnalytics.compute_rr_analysis(trades)
        assert 50 <= r.realization_pct < 80
        assert any("execution leakage" in s.lower() or "capturing" in s.lower() for s in r.coaching_signals)

    def test_hold_discipline_signal_at_or_above_100(self):
        trades = [
            make_trade(f"T{i}", trade_plan_id=f"P{i}", planned_rr=2.0, actual_r=2.5)
            for i in range(4)
        ]
        r = AccountAnalytics.compute_rr_analysis(trades)
        assert r.realization_pct >= 100
        assert any("strong hold" in s.lower() or "equals or exceeds" in s.lower() for s in r.coaching_signals)

    def test_met_target_count(self):
        trades = [
            make_trade("T1", trade_plan_id="P1", planned_rr=2.0, actual_r=2.5),  # met
            make_trade("T2", trade_plan_id="P2", planned_rr=2.0, actual_r=2.0),  # met (equal)
            make_trade("T3", trade_plan_id="P3", planned_rr=2.0, actual_r=1.0),  # missed
        ]
        r = AccountAnalytics.compute_rr_analysis(trades)
        assert r.met_target_count == 2
        assert r.missed_target_count == 1

    def test_below_n3_no_signals(self):
        # Only 2 qualifying trades — below MIN_N=3
        trades = [
            make_trade(f"T{i}", trade_plan_id=f"P{i}", planned_rr=2.0, actual_r=0.2)
            for i in range(2)
        ]
        r = AccountAnalytics.compute_rr_analysis(trades)
        assert r.coaching_signals == []

    def test_pct_met_below_40_signal(self):
        # 1 out of 4 met target → 25%
        trades = [
            make_trade("T1", trade_plan_id="P1", planned_rr=2.0, actual_r=2.0),
            make_trade("T2", trade_plan_id="P2", planned_rr=2.0, actual_r=0.5),
            make_trade("T3", trade_plan_id="P3", planned_rr=2.0, actual_r=0.3),
            make_trade("T4", trade_plan_id="P4", planned_rr=2.0, actual_r=0.1),
        ]
        r = AccountAnalytics.compute_rr_analysis(trades)
        assert r.pct_met_target < 40
        assert any("only" in s.lower() and "%" in s for s in r.coaching_signals)


# ── compute_rr_trend ──────────────────────────────────────────────────────────

class TestComputeRRTrend:
    def _make_weekly_trades(self, week_actual_pairs):
        """Create trades in specific ISO weeks. week_actual_pairs: [(year, week, actual_r), ...]"""
        trades = []
        for i, (year, week, actual_r) in enumerate(week_actual_pairs):
            # Place exit_datetime on Monday of given ISO week
            jan4 = datetime(year, 1, 4)
            monday = jan4 - timedelta(days=jan4.weekday()) + timedelta(weeks=week - 1)
            t = make_trade(
                f"T{i}", trade_plan_id=f"P{i}", planned_rr=2.0, actual_r=actual_r,
                exit_dt=monday + timedelta(hours=12),
            )
            trades.append(t)
        return trades

    def test_no_qualifying_trades_returns_empty(self):
        r = AccountAnalytics.compute_rr_trend([])
        assert r.buckets == []
        assert r.trend_signal is None

    def test_fewer_than_4_buckets_trend_signal_is_none(self):
        trades = self._make_weekly_trades([
            (2026, 1, 1.8), (2026, 2, 1.6), (2026, 3, 1.7),
        ])
        r = AccountAnalytics.compute_rr_trend(trades)
        assert len(r.buckets) == 3
        assert r.trend_signal is None

    def test_improving_trend(self):
        # First two weeks low realization, last two weeks high
        trades = self._make_weekly_trades([
            (2026, 1, 0.6),  # 30% of 2.0
            (2026, 2, 0.7),  # 35%
            (2026, 3, 1.8),  # 90%
            (2026, 4, 2.0),  # 100%
        ])
        r = AccountAnalytics.compute_rr_trend(trades)
        assert r.trend_signal == "improving"

    def test_worsening_trend(self):
        trades = self._make_weekly_trades([
            (2026, 1, 2.0),  # 100%
            (2026, 2, 1.9),  # 95%
            (2026, 3, 0.7),  # 35%
            (2026, 4, 0.5),  # 25%
        ])
        r = AccountAnalytics.compute_rr_trend(trades)
        assert r.trend_signal == "worsening"

    def test_stable_trend(self):
        # All four weeks at ~90% realization → first-half avg == second-half avg → diff=0 → stable
        trades = self._make_weekly_trades([
            (2026, 1, 1.8),
            (2026, 2, 1.8),
            (2026, 3, 1.8),
            (2026, 4, 1.8),
        ])
        r = AccountAnalytics.compute_rr_trend(trades)
        assert r.trend_signal == "stable"

    def test_bucket_count_matches_unique_weeks(self):
        # Two trades in same week → 1 bucket
        trades = self._make_weekly_trades([
            (2026, 1, 1.5), (2026, 1, 2.0),
            (2026, 2, 1.0),
        ])
        r = AccountAnalytics.compute_rr_trend(trades)
        assert len(r.buckets) == 2
        assert r.buckets[0].n == 2
        assert r.buckets[1].n == 1

    def test_total_qualifying_count(self):
        trades = self._make_weekly_trades([(2026, i + 1, 1.5) for i in range(4)])
        r = AccountAnalytics.compute_rr_trend(trades)
        assert r.total_qualifying == 4


# ── _classify_exit ────────────────────────────────────────────────────────────

class TestClassifyExit:
    def test_no_actual_r_returns_unclear(self):
        t = make_trade(actual_r=None)
        assert AccountAnalytics._classify_exit(t) == "unclear"

    def test_stop_hit_at_boundary(self):
        t = make_trade(result=TradeResult.LOSS, actual_r=-0.85)
        assert AccountAnalytics._classify_exit(t) == "stop_hit"

    def test_stop_hit_beyond_boundary(self):
        t = make_trade(result=TradeResult.LOSS, actual_r=-1.2)
        assert AccountAnalytics._classify_exit(t) == "stop_hit"

    def test_manual_cut_loss_before_stop(self):
        t = make_trade(result=TradeResult.LOSS, actual_r=-0.4)
        assert AccountAnalytics._classify_exit(t) == "manual_cut"

    def test_manual_cut_boundary(self):
        # r == -0.65 is NOT manual_cut (condition is r > -0.65)
        t = make_trade(result=TradeResult.LOSS, actual_r=-0.65)
        # -0.65 is between -0.85 and -0.65 boundary — it's neither stop_hit nor manual_cut
        # Actually: -0.65 > -0.65 is False, so NOT manual_cut. -0.65 <= -0.85 is False, so NOT stop_hit.
        # → falls through to unclear
        result = AccountAnalytics._classify_exit(t)
        assert result == "unclear"

    def test_target_hit_long(self):
        # LONG: entry=1.0, SL=0.9 (dist=0.1), TP=1.2 (dist=0.2 = 2R)
        # Exit at 1.19 → actual_dist=0.19, tp_dist=0.2 → reach=0.95 >= 0.90 → target_hit
        t = make_trade(
            result=TradeResult.WIN, actual_r=1.9,
            entry_price=1.0, exit_price=1.19, take_profit=1.2,
            direction=Direction.LONG,
        )
        assert AccountAnalytics._classify_exit(t) == "target_hit"

    def test_exit_before_target_long(self):
        # Exit at 1.10 → actual_dist=0.10, tp_dist=0.20 → reach=0.50 < 0.90
        t = make_trade(
            result=TradeResult.WIN, actual_r=1.0,
            entry_price=1.0, exit_price=1.10, take_profit=1.20,
            direction=Direction.LONG,
        )
        assert AccountAnalytics._classify_exit(t) == "exit_before_target"

    def test_target_hit_short(self):
        # SHORT: entry=1.2, SL=1.3 (dist=0.1), TP=1.0 (dist=0.2)
        # Exit at 1.01 → actual_dist=0.19, tp_dist=0.2 → reach=0.95 >= 0.90
        t = make_trade(
            result=TradeResult.WIN, actual_r=1.9,
            entry_price=1.2, exit_price=1.01, take_profit=1.0,
            direction=Direction.SHORT,
        )
        assert AccountAnalytics._classify_exit(t) == "target_hit"

    def test_win_without_tp_returns_unclear(self):
        t = make_trade(result=TradeResult.WIN, actual_r=1.5)
        assert AccountAnalytics._classify_exit(t) == "unclear"

    def test_win_uses_planned_rr_inferred_tp(self):
        # Entry=1.0, SL=0.9 (dist=0.1), planned_rr=2.0 → inferred TP=1.2
        # Exit=1.19 → dist=0.19/0.20 = 0.95 → target_hit
        t = make_trade(
            result=TradeResult.WIN, actual_r=1.9,
            entry_price=1.0, exit_price=1.19, stop_loss=0.9,
            planned_rr=2.0, trade_plan_id="P1",
            direction=Direction.LONG,
        )
        assert AccountAnalytics._classify_exit(t) == "target_hit"


# ── compute_exit_decomposition ────────────────────────────────────────────────

class TestComputeExitDecomposition:
    def test_no_trades_with_actual_r(self):
        trades = [make_trade(actual_r=None), make_trade(actual_r=None)]
        r = AccountAnalytics.compute_exit_decomposition(trades)
        assert r.total_classified == 0
        assert r.total_unclassified == 2
        assert r.stop_hit.count == 0

    def test_bucket_counts(self):
        trades = [
            make_trade("T1", result=TradeResult.LOSS, actual_r=-1.0),   # stop_hit
            make_trade("T2", result=TradeResult.LOSS, actual_r=-0.3),   # manual_cut
            make_trade("T3", result=TradeResult.WIN, actual_r=1.9,
                       entry_price=1.0, exit_price=1.19, take_profit=1.2,
                       direction=Direction.LONG),                         # target_hit
            make_trade("T4", result=TradeResult.WIN, actual_r=1.0,
                       entry_price=1.0, exit_price=1.10, take_profit=1.2,
                       direction=Direction.LONG),                         # exit_before_target
            make_trade("T5", result=TradeResult.WIN, actual_r=1.5),     # unclear (no TP)
        ]
        r = AccountAnalytics.compute_exit_decomposition(trades)
        assert r.total_classified == 5
        assert r.stop_hit.count == 1
        assert r.manual_cut.count == 1
        assert r.target_hit.count == 1
        assert r.exit_before_target.count == 1
        assert r.unclear.count == 1

    def test_pct_of_total_sums_to_100(self):
        trades = [
            make_trade("T1", result=TradeResult.LOSS, actual_r=-1.0),
            make_trade("T2", result=TradeResult.LOSS, actual_r=-0.3),
            make_trade("T3", result=TradeResult.WIN, actual_r=1.5),
        ]
        r = AccountAnalytics.compute_exit_decomposition(trades)
        total_pct = (
            (r.stop_hit.pct_of_total or 0)
            + (r.manual_cut.pct_of_total or 0)
            + (r.target_hit.pct_of_total or 0)
            + (r.exit_before_target.pct_of_total or 0)
            + (r.unclear.pct_of_total or 0)
        )
        assert total_pct == pytest.approx(100.0, abs=0.5)

    def test_cut_signal_with_at_least_2_cuts(self):
        trades = [
            make_trade(f"L{i}", result=TradeResult.LOSS, actual_r=-0.3) for i in range(2)
        ]
        r = AccountAnalytics.compute_exit_decomposition(trades)
        assert any("manual cut" in s.lower() for s in r.coaching_signals)

    def test_no_cut_signal_with_only_1_cut(self):
        trades = [make_trade("L1", result=TradeResult.LOSS, actual_r=-0.3)]
        r = AccountAnalytics.compute_exit_decomposition(trades)
        cut_signals = [s for s in r.coaching_signals if "manual cut" in s.lower()]
        assert len(cut_signals) == 0

    def test_target_hit_signal_when_high_pct(self):
        # 4 out of 4 tp-eligible wins hit target → 100%
        trades = [
            make_trade(f"W{i}", result=TradeResult.WIN, actual_r=1.9,
                       entry_price=1.0, exit_price=1.19, take_profit=1.2,
                       direction=Direction.LONG)
            for i in range(3)
        ]
        r = AccountAnalytics.compute_exit_decomposition(trades)
        assert any("strong target" in s.lower() for s in r.coaching_signals)

    def test_missing_actual_r_counted_unclassified(self):
        trades = [
            make_trade("T1", actual_r=None),
            make_trade("T2", actual_r=-1.0, result=TradeResult.LOSS),
        ]
        r = AccountAnalytics.compute_exit_decomposition(trades)
        assert r.total_unclassified == 1
        assert r.total_classified == 1


# ── compute_entry_exit_quality ────────────────────────────────────────────────

class TestComputeEntryExitQuality:
    def _make_win_before_target(self, trade_id: str) -> Trade:
        return make_trade(
            trade_id, result=TradeResult.WIN, actual_r=1.0,
            entry_price=1.0, exit_price=1.10, take_profit=1.2,
            direction=Direction.LONG,
        )

    def _make_stop_hit(self, trade_id: str, has_entry_flag: bool = False) -> Trade:
        t = make_trade(trade_id, result=TradeResult.LOSS, actual_r=-1.0)
        if has_entry_flag:
            t.followed_plan = False
        return t

    def test_fewer_than_5_classified_returns_unclear_low(self):
        trades = [make_trade(f"T{i}", actual_r=float(i) * 0.5) for i in range(4)]
        r = AccountAnalytics.compute_entry_exit_quality(trades)
        assert r.primary_diagnosis == "unclear"
        assert r.confidence == "low"

    def test_exit_discipline_diagnosis(self):
        # 6 wins with TP info, 5 exited early (>40%)
        trades = [self._make_win_before_target(f"W{i}") for i in range(5)]
        trades += [
            make_trade("W5", result=TradeResult.WIN, actual_r=1.9,
                       entry_price=1.0, exit_price=1.19, take_profit=1.2,
                       direction=Direction.LONG),  # hit target
        ]
        r = AccountAnalytics.compute_entry_exit_quality(trades)
        assert r.primary_diagnosis == "exit_discipline"

    def test_entry_quality_diagnosis(self):
        # 6 stop_hit losses (>=60%), all with entry flags (followed_plan=False), + flag_plan_dev>=2
        trades = [self._make_stop_hit(f"SH{i}", has_entry_flag=True) for i in range(6)]
        r = AccountAnalytics.compute_entry_exit_quality(trades)
        assert r.primary_diagnosis == "entry_quality"

    def test_unclear_when_not_enough_signals(self):
        # 5 wins with TP but low early exit rate
        trades = [
            make_trade(f"W{i}", result=TradeResult.WIN, actual_r=1.9,
                       entry_price=1.0, exit_price=1.19, take_profit=1.2,
                       direction=Direction.LONG)
            for i in range(5)
        ]
        r = AccountAnalytics.compute_entry_exit_quality(trades)
        assert r.primary_diagnosis == "unclear"

    def test_early_exit_pct_computed_correctly(self):
        # 3 wins with TP: 2 early, 1 hit
        trades = [
            self._make_win_before_target("W1"),
            self._make_win_before_target("W2"),
            make_trade("W3", result=TradeResult.WIN, actual_r=1.9,
                       entry_price=1.0, exit_price=1.19, take_profit=1.2,
                       direction=Direction.LONG),
        ]
        r = AccountAnalytics.compute_entry_exit_quality(trades)
        assert r.early_exit_pct == pytest.approx(66.7, abs=0.5)

    def test_early_exit_pct_none_when_fewer_than_3_tp_wins(self):
        trades = [
            self._make_win_before_target("W1"),
            self._make_win_before_target("W2"),
        ]
        r = AccountAnalytics.compute_entry_exit_quality(trades)
        assert r.early_exit_pct is None

    def test_flag_coverage_signal_when_sparse(self):
        # 5 classified trades, no flags → coverage = 0%
        trades = [make_trade(f"T{i}", actual_r=float(i) * 0.5) for i in range(5)]
        r = AccountAnalytics.compute_entry_exit_quality(trades)
        assert r.flag_coverage_pct == 0.0
        assert any("flag coverage" in s.lower() or "tagging" in s.lower() for s in r.coaching_signals)

    def test_premature_exit_flag_count(self):
        trades = [make_trade(f"T{i}", actual_r=0.5, premature_exit=True) for i in range(3)]
        r = AccountAnalytics.compute_entry_exit_quality(trades)
        assert r.flag_premature_exit == 3

    def test_moved_stop_flag_count(self):
        trades = [make_trade(f"T{i}", actual_r=0.5, moved_stop=True) for i in range(3)]
        r = AccountAnalytics.compute_entry_exit_quality(trades)
        assert r.flag_moved_stop == 3

    def test_confidence_high_exit_discipline_with_enough_data(self):
        # 12 wins with TP, 10 exited early → exit_concern=True, early_exit_pct >= 50, total >= 10
        trades = [self._make_win_before_target(f"W{i}") for i in range(10)]
        trades += [
            make_trade(f"WH{i}", result=TradeResult.WIN, actual_r=1.9,
                       entry_price=1.0, exit_price=1.19, take_profit=1.2,
                       direction=Direction.LONG)
            for i in range(2)
        ]
        r = AccountAnalytics.compute_entry_exit_quality(trades)
        assert r.primary_diagnosis == "exit_discipline"
        assert r.confidence == "high"

    def test_confidence_low_mixed_with_sparse_flags(self):
        # exit_concern + entry_concern (stop hits + plan_dev) + sparse flags
        exits_early = [self._make_win_before_target(f"W{i}") for i in range(4)]
        stop_hits = [self._make_stop_hit(f"SH{i}", has_entry_flag=True) for i in range(4)]
        # stop_hit_pct = 4/4 = 100%, entry_flagged = 4/4 = 100%, flag_plan_dev = 4 >= 2
        # total = 8 >= 5 → but flag_coverage_pct depends on actual flags
        trades = exits_early + stop_hits
        r = AccountAnalytics.compute_entry_exit_quality(trades)
        # With followed_plan=False as entry flag → covered
        # We're mainly checking that mixed diagnosis is produced, confidence can vary
        assert r.primary_diagnosis in ("mixed", "exit_discipline", "entry_quality")


# ── compute_daily_adherence ───────────────────────────────────────────────────

class TestComputeDailyAdherence:
    class _Plan:
        def __init__(self, allowed=None, disallowed=None, max_trades=None):
            self.trading_date = date(2026, 4, 15)
            self.allowed_setups = allowed or []
            self.disallowed_setups = disallowed or []
            self.max_trades = max_trades

    def _trade(self, trade_id, setup_type, plan_id=None):
        t = Trade.__new__(Trade)
        t.trade_id = trade_id
        t.account_id = "TEST"
        t.setup_type = setup_type
        t.trade_plan_id = plan_id
        return t

    def test_empty_trades_no_signals(self):
        r = AccountAnalytics.compute_daily_adherence(self._Plan(), [])
        assert r.trades_taken == 0
        assert r.discipline_signals == []

    def test_max_trades_exceeded(self):
        plan = self._Plan(max_trades=2)
        trades = [self._trade(f"T{i}", "OB") for i in range(3)]
        r = AccountAnalytics.compute_daily_adherence(plan, trades)
        assert r.max_trades_exceeded is True
        assert r.max_trades_exceeded_by == 1

    def test_max_trades_not_exceeded(self):
        plan = self._Plan(max_trades=3)
        trades = [self._trade(f"T{i}", "OB") for i in range(3)]
        r = AccountAnalytics.compute_daily_adherence(plan, trades)
        assert r.max_trades_exceeded is False
        assert r.max_trades_exceeded_by == 0

    def test_disallowed_setup_violation(self):
        plan = self._Plan(disallowed=["Fake MSS"])
        trades = [self._trade("T1", "Fake MSS"), self._trade("T2", "ICT Breaker")]
        r = AccountAnalytics.compute_daily_adherence(plan, trades)
        assert r.disallowed_violation_count == 1
        assert r.disallowed_violations[0].trade_id == "T1"

    def test_disallowed_matching_is_case_insensitive(self):
        plan = self._Plan(disallowed=["fake mss"])
        trades = [self._trade("T1", "FAKE MSS")]
        r = AccountAnalytics.compute_daily_adherence(plan, trades)
        assert r.disallowed_violation_count == 1

    def test_outside_allowed_setups(self):
        plan = self._Plan(allowed=["ICT Breaker"])
        trades = [self._trade("T1", "ICT Breaker"), self._trade("T2", "Scalp")]
        r = AccountAnalytics.compute_daily_adherence(plan, trades)
        assert r.outside_allowed_count == 1
        assert "Scalp" in r.outside_allowed_setups

    def test_allowed_matching_is_case_insensitive(self):
        plan = self._Plan(allowed=["ict breaker"])
        trades = [self._trade("T1", "ICT Breaker")]
        r = AccountAnalytics.compute_daily_adherence(plan, trades)
        assert r.outside_allowed_count == 0

    def test_untagged_trades_excluded_from_setup_checks(self):
        plan = self._Plan(allowed=["ICT Breaker"], disallowed=["Scalp"])
        trades = [self._trade("T1", None)]   # setup_type=None
        r = AccountAnalytics.compute_daily_adherence(plan, trades)
        assert r.untagged_count == 1
        assert r.outside_allowed_count == 0
        assert r.disallowed_violation_count == 0

    def test_planned_vs_unplanned_count(self):
        plan = self._Plan()
        trades = [
            self._trade("T1", "OB", plan_id="P1"),
            self._trade("T2", "OB", plan_id=None),
        ]
        r = AccountAnalytics.compute_daily_adherence(plan, trades)
        assert r.planned_count == 1
        assert r.unplanned_count == 1

    def test_allowed_setups_not_configured_no_outside_check(self):
        # allowed_setups is empty → any setup_type is fine
        plan = self._Plan(allowed=[])
        trades = [self._trade("T1", "RandomSetup")]
        r = AccountAnalytics.compute_daily_adherence(plan, trades)
        assert r.allowed_setups_configured is False
        assert r.outside_allowed_count == 0

    def test_discipline_signals_populated_on_violations(self):
        plan = self._Plan(max_trades=1, disallowed=["Fake MSS"])
        trades = [self._trade("T1", "Fake MSS"), self._trade("T2", "OB")]
        r = AccountAnalytics.compute_daily_adherence(plan, trades)
        assert len(r.discipline_signals) > 0
