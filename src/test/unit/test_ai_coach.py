"""
Targeted tests for services/ai_coach.py — deterministic logic only.

Covers:
  - _build_context(): field population from trade data
  - _generate_fallback_sections(): all 4 sections, key diagnosis branches
  - daily discipline signals (Phase 1 integration)
  - low-data / no-data graceful degradation
  - no external API calls — ANTHROPIC_API_KEY is unset in these tests
"""
from datetime import date, datetime, timedelta
from typing import Optional

import pytest

from src.main.python.models.account import Account
from src.main.python.models.enums import AssetClass, Direction, Platform, TradeResult
from src.main.python.models.trade import Trade
from src.main.python.services.ai_coach import AICoachService, CoachingContext


# ── Helpers ───────────────────────────────────────────────────────────────────

def make_account(account_id="TEST", starting_balance=10000.0) -> Account:
    return Account(
        account_id=account_id,
        broker="FTMO",
        platform=Platform.MT5,
        starting_balance=starting_balance,
    )


def make_trade(
    trade_id: str = "T1",
    result: TradeResult = TradeResult.WIN,
    net_pnl: float = 100.0,
    exit_dt: Optional[datetime] = None,
    trade_plan_id: Optional[str] = None,
    followed_plan: Optional[bool] = None,
    actual_r: Optional[float] = None,
    planned_rr: Optional[float] = None,
    is_a_plus_setup: Optional[bool] = None,
    problem_source: Optional[str] = None,
    entry_price: Optional[float] = None,
    exit_price: Optional[float] = None,
    stop_loss: Optional[float] = None,
    take_profit: Optional[float] = None,
    direction: Direction = Direction.LONG,
    setup_type: Optional[str] = None,
) -> Trade:
    t = Trade(
        trade_id=trade_id,
        account_id="TEST",
        symbol="EURUSD",
        asset_class=AssetClass.FOREX,
        direction=direction,
        result=result,
        net_pnl=net_pnl,
        gross_pnl=net_pnl,
        exit_datetime=exit_dt or datetime(2026, 1, 15, 12, 0),
        entry_datetime=(exit_dt or datetime(2026, 1, 15, 12, 0)) - timedelta(hours=2),
    )
    t.trade_plan_id = trade_plan_id
    t.followed_plan = followed_plan
    t.actual_r_multiple = actual_r
    t.planned_rr = planned_rr
    t.is_a_plus_setup = is_a_plus_setup
    t.problem_source = problem_source
    t.entry_price = entry_price
    t.exit_price = exit_price
    t.stop_loss = stop_loss
    t.take_profit = take_profit
    t.setup_type = setup_type
    return t


class MockDailyPlan:
    def __init__(self, trading_date, max_trades=None, allowed=None, disallowed=None):
        self.trading_date = trading_date
        self.max_trades = max_trades
        self.allowed_setups = allowed or []
        self.disallowed_setups = disallowed or []


# ── _build_context — base fields ──────────────────────────────────────────────

class TestBuildContextBaseFields:
    def test_zero_trades_safe_defaults(self):
        ctx = AICoachService._build_context([], make_account(), None, None)
        assert ctx.total_trades == 0
        assert ctx.win_rate_pct == 0.0
        assert ctx.total_net_pnl == 0.0
        assert ctx.followed_plan_rate is None
        assert ctx.a_plus_rate is None

    def test_win_rate_pct_computed(self):
        trades = [
            make_trade("T1", result=TradeResult.WIN, net_pnl=100.0),
            make_trade("T2", result=TradeResult.WIN, net_pnl=100.0),
            make_trade("T3", result=TradeResult.LOSS, net_pnl=-50.0),
        ]
        ctx = AICoachService._build_context(trades, make_account(), None, None)
        assert ctx.win_rate_pct == pytest.approx(66.7, abs=0.5)

    def test_total_net_pnl_computed(self):
        trades = [
            make_trade("T1", net_pnl=200.0),
            make_trade("T2", net_pnl=-80.0),
        ]
        ctx = AICoachService._build_context(trades, make_account(), None, None)
        assert ctx.total_net_pnl == pytest.approx(120.0)

    def test_planned_unplanned_counts(self):
        trades = [
            make_trade("T1", trade_plan_id="P1"),
            make_trade("T2", trade_plan_id="P2"),
            make_trade("T3"),
        ]
        ctx = AICoachService._build_context(trades, make_account(), None, None)
        assert ctx.planned_trade_count == 2
        assert ctx.unplanned_trade_count == 1

    def test_followed_plan_rate_computed(self):
        trades = [
            make_trade("T1", followed_plan=True),
            make_trade("T2", followed_plan=True),
            make_trade("T3", followed_plan=False),
            make_trade("T4"),
        ]
        ctx = AICoachService._build_context(trades, make_account(), None, None)
        # 2 followed out of 4 total → 50%
        assert ctx.followed_plan_rate == pytest.approx(50.0)

    def test_a_plus_rate_computed(self):
        trades = [
            make_trade("T1", is_a_plus_setup=True),
            make_trade("T2", is_a_plus_setup=True),
            make_trade("T3", is_a_plus_setup=False),
        ]
        ctx = AICoachService._build_context(trades, make_account(), None, None)
        assert ctx.a_plus_rate == pytest.approx(66.7, abs=0.5)

    def test_source_counts_populated(self):
        trades = [
            make_trade("T1", problem_source="execution"),
            make_trade("T2", problem_source="execution"),
            make_trade("T3", problem_source="psychology"),
        ]
        ctx = AICoachService._build_context(trades, make_account(), None, None)
        assert ctx.source_counts.get("execution") == 2
        assert ctx.source_counts.get("psychology") == 1


# ── _build_context — plan adherence fields ────────────────────────────────────

class TestBuildContextPlanFields:
    def test_planned_win_rate_none_when_n_below_3(self):
        # Only 2 planned trades → below MIN_N=3
        trades = [
            make_trade("P1", trade_plan_id="plan1"),
            make_trade("P2", trade_plan_id="plan2"),
        ]
        ctx = AICoachService._build_context(trades, make_account(), None, None)
        assert ctx.planned_win_rate is None

    def test_planned_win_rate_populated_when_n_gte3(self):
        trades = [
            make_trade(f"P{i}", result=TradeResult.WIN, trade_plan_id=f"plan{i}") for i in range(3)
        ]
        ctx = AICoachService._build_context(trades, make_account(), None, None)
        assert ctx.planned_win_rate == pytest.approx(100.0)

    def test_rr_fields_none_when_no_qualifying_trades(self):
        trades = [make_trade("T1", net_pnl=100.0)]
        ctx = AICoachService._build_context(trades, make_account(), None, None)
        assert ctx.rr_sample_count == 0
        assert ctx.avg_planned_rr is None
        assert ctx.realization_pct is None

    def test_rr_fields_populated_with_qualifying_trades(self):
        trades = [
            make_trade(f"T{i}", trade_plan_id=f"P{i}", planned_rr=2.0, actual_r=1.0)
            for i in range(3)
        ]
        ctx = AICoachService._build_context(trades, make_account(), None, None)
        assert ctx.rr_sample_count == 3
        assert ctx.avg_planned_rr == pytest.approx(2.0)
        assert ctx.avg_actual_r == pytest.approx(1.0)
        assert ctx.realization_pct == pytest.approx(50.0)


# ── _build_context — exit decomposition / entry-exit quality fields ───────────

class TestBuildContextExitFields:
    def test_exit_fields_none_when_fewer_than_3_classified(self):
        trades = [make_trade("T1", actual_r=-1.0, result=TradeResult.LOSS)]
        ctx = AICoachService._build_context(trades, make_account(), None, None)
        assert ctx.exit_stop_hit_pct is None

    def test_exit_stop_hit_pct_populated(self):
        trades = [
            make_trade(f"T{i}", result=TradeResult.LOSS, actual_r=-1.0, net_pnl=-50.0)
            for i in range(3)
        ]
        ctx = AICoachService._build_context(trades, make_account(), None, None)
        assert ctx.exit_stop_hit_pct == pytest.approx(100.0)

    def test_entry_exit_fields_none_when_fewer_than_5_classified(self):
        trades = [make_trade(f"T{i}", actual_r=float(i)) for i in range(4)]
        ctx = AICoachService._build_context(trades, make_account(), None, None)
        assert ctx.entry_exit_diagnosis is None
        assert ctx.entry_exit_confidence is None


# ── _build_context — daily discipline fields ──────────────────────────────────

class TestBuildContextDailyDiscipline:
    def test_no_daily_plans_no_signals(self):
        trades = [make_trade("T1")]
        ctx = AICoachService._build_context(trades, make_account(), None, None, daily_plans=None)
        assert ctx.daily_days_with_violations == 0
        assert ctx.daily_discipline_signals == []

    def test_disallowed_violation_populates_signal(self):
        trade_date = date(2026, 4, 15)
        t = make_trade("T1", exit_dt=datetime(2026, 4, 15, 12, 0), setup_type="Fake MSS")
        plan = MockDailyPlan(trade_date, disallowed=["Fake MSS"])
        ctx = AICoachService._build_context([t], make_account(), None, None, daily_plans=[plan])
        assert ctx.daily_disallowed_violations == 1
        assert ctx.daily_days_with_violations == 1
        assert any("disallowed" in s.lower() for s in ctx.daily_discipline_signals)

    def test_max_trades_exceeded_populates_signal(self):
        trade_date = date(2026, 4, 15)
        trades = [make_trade(f"T{i}", exit_dt=datetime(2026, 4, 15, 12, 0)) for i in range(3)]
        plan = MockDailyPlan(trade_date, max_trades=2)
        ctx = AICoachService._build_context(trades, make_account(), None, None, daily_plans=[plan])
        assert ctx.daily_max_exceeded_days == 1
        assert any("exceeded" in s.lower() or "max trades" in s.lower() for s in ctx.daily_discipline_signals)

    def test_trade_on_different_day_not_counted(self):
        plan = MockDailyPlan(date(2026, 4, 15), disallowed=["Fake MSS"])
        t = make_trade("T1", exit_dt=datetime(2026, 4, 16, 12, 0), setup_type="Fake MSS")
        ctx = AICoachService._build_context([t], make_account(), None, None, daily_plans=[plan])
        # Trade is on 4/16, plan is for 4/15 → no match
        assert ctx.daily_disallowed_violations == 0

    def test_outside_allowed_populates_signal(self):
        trade_date = date(2026, 4, 15)
        t = make_trade("T1", exit_dt=datetime(2026, 4, 15, 12, 0), setup_type="Scalp")
        plan = MockDailyPlan(trade_date, allowed=["ICT Breaker"])
        ctx = AICoachService._build_context([t], make_account(), None, None, daily_plans=[plan])
        assert ctx.daily_outside_allowed == 1
        assert any("allowed list" in s.lower() or "outside" in s.lower() for s in ctx.daily_discipline_signals)


# ── _generate_fallback_sections — structure ───────────────────────────────────

class TestFallbackSectionsStructure:
    def _make_ctx(self, **overrides) -> CoachingContext:
        defaults = dict(
            from_date=None, to_date=None,
            total_trades=10, win_rate_pct=60.0, total_net_pnl=200.0,
            profit_factor=1.5, expectancy=20.0, max_drawdown=-150.0,
            followed_plan_rate=None, a_plus_rate=None,
            source_counts={}, top_mistakes=[], mistake_report=None,
        )
        defaults.update(overrides)
        return CoachingContext(**defaults)

    def test_returns_all_four_keys(self):
        ctx = self._make_ctx()
        sections = AICoachService._generate_fallback_sections(ctx)
        assert "summary" in sections
        assert "top_mistakes" in sections
        assert "diagnosis" in sections
        assert "improvement" in sections

    def test_summary_contains_trade_count(self):
        ctx = self._make_ctx(total_trades=15)
        sections = AICoachService._generate_fallback_sections(ctx)
        assert "15" in sections["summary"]

    def test_summary_contains_win_rate(self):
        ctx = self._make_ctx(win_rate_pct=55.0)
        sections = AICoachService._generate_fallback_sections(ctx)
        assert "55.0%" in sections["summary"]

    def test_summary_positive_pnl_prefixed_with_plus(self):
        ctx = self._make_ctx(total_net_pnl=300.0)
        sections = AICoachService._generate_fallback_sections(ctx)
        assert "+$300.00" in sections["summary"]

    def test_summary_negative_pnl_prefixed_with_minus(self):
        ctx = self._make_ctx(total_net_pnl=-150.0)
        sections = AICoachService._generate_fallback_sections(ctx)
        assert "-$150.00" in sections["summary"]

    def test_summary_pf_na_when_none(self):
        ctx = self._make_ctx(profit_factor=None)
        sections = AICoachService._generate_fallback_sections(ctx)
        assert "N/A" in sections["summary"]

    def test_top_mistakes_list_correct_length(self):
        ctx = self._make_ctx(top_mistakes=[
            {"tag": "chasing", "count": 3, "total_cost": -90.0, "after_loss_rate": 0.2},
            {"tag": "fomo",    "count": 2, "total_cost": -60.0, "after_loss_rate": None},
        ])
        sections = AICoachService._generate_fallback_sections(ctx)
        assert len(sections["top_mistakes"]) == 2

    def test_top_mistake_revenge_signal_when_after_loss_high(self):
        ctx = self._make_ctx(top_mistakes=[
            {"tag": "revenge_trade", "count": 4, "total_cost": -200.0, "after_loss_rate": 0.75},
        ])
        sections = AICoachService._generate_fallback_sections(ctx)
        pattern = sections["top_mistakes"][0]["pattern"]
        assert "revenge" in pattern.lower() or "after a loss" in pattern.lower()

    def test_empty_trades_produces_valid_sections(self):
        ctx = self._make_ctx(total_trades=0, win_rate_pct=0.0, total_net_pnl=0.0,
                             profit_factor=None, max_drawdown=0.0)
        sections = AICoachService._generate_fallback_sections(ctx)
        assert sections["summary"]
        assert sections["diagnosis"]
        assert sections["improvement"]


# ── _generate_fallback_sections — diagnosis branches ─────────────────────────

class TestFallbackDiagnosisBranches:
    def _ctx(self, **kw) -> CoachingContext:
        defaults = dict(
            from_date=None, to_date=None,
            total_trades=10, win_rate_pct=60.0, total_net_pnl=100.0,
            profit_factor=1.5, expectancy=10.0, max_drawdown=-100.0,
            followed_plan_rate=None, a_plus_rate=None,
            source_counts={}, top_mistakes=[], mistake_report=None,
        )
        defaults.update(kw)
        return CoachingContext(**defaults)

    def test_dominant_source_drives_diagnosis(self):
        ctx = self._ctx(source_counts={"execution": 8, "psychology": 2})
        sections = AICoachService._generate_fallback_sections(ctx)
        assert "execution discipline" in sections["diagnosis"]

    def test_rr_below_50_diagnosis(self):
        ctx = self._ctx(
            realization_pct=40.0, avg_actual_r=0.8, avg_planned_rr=2.0,
            rr_sample_count=5
        )
        sections = AICoachService._generate_fallback_sections(ctx)
        assert "40%" in sections["diagnosis"] or "40.0%" in sections["diagnosis"]
        assert "leakage" in sections["diagnosis"].lower() or "severe" in sections["diagnosis"].lower()

    def test_rr_above_100_improvement(self):
        # rr_above_100 drives the IMPROVEMENT section (not diagnosis).
        # Diagnosis falls through to else when no stronger signal is present.
        ctx = self._ctx(
            realization_pct=110.0, avg_actual_r=2.2, avg_planned_rr=2.0,
            rr_sample_count=5
        )
        sections = AICoachService._generate_fallback_sections(ctx)
        assert "strong r:r execution" in sections["improvement"].lower() or "110%" in sections["improvement"]

    def test_daily_discipline_diagnosis_branch(self):
        # daily signals present but no stronger signals
        ctx = self._ctx(
            daily_discipline_signals=["2 trades used disallowed setups."],
            daily_disallowed_violations=2,
            daily_outside_allowed=0,
            daily_days_with_violations=1,
            daily_max_exceeded_days=0,
            source_counts={},
        )
        sections = AICoachService._generate_fallback_sections(ctx)
        assert "discipline" in sections["diagnosis"].lower() or "disallowed" in sections["diagnosis"].lower()

    def test_profit_factor_below_1_diagnosis(self):
        ctx = self._ctx(profit_factor=0.8, source_counts={})
        sections = AICoachService._generate_fallback_sections(ctx)
        assert "profit factor" in sections["diagnosis"].lower() or "below 1" in sections["diagnosis"].lower()

    def test_fallback_diagnosis_when_no_signal(self):
        ctx = self._ctx()
        sections = AICoachService._generate_fallback_sections(ctx)
        assert sections["diagnosis"]  # should always produce something


# ── _generate_fallback_sections — improvement branches ───────────────────────

class TestFallbackImprovementBranches:
    def _ctx(self, **kw) -> CoachingContext:
        defaults = dict(
            from_date=None, to_date=None,
            total_trades=10, win_rate_pct=60.0, total_net_pnl=100.0,
            profit_factor=1.5, expectancy=10.0, max_drawdown=-100.0,
            followed_plan_rate=None, a_plus_rate=None,
            source_counts={}, top_mistakes=[], mistake_report=None,
        )
        defaults.update(kw)
        return CoachingContext(**defaults)

    def test_linked_but_deviated_improvement(self):
        ctx = self._ctx(linked_but_deviated_count=2, deviated_total_pnl=-120.0)
        sections = AICoachService._generate_fallback_sections(ctx)
        assert "plan" in sections["improvement"].lower() and "deviated" in sections["improvement"].lower()

    def test_rr_below_80_improvement(self):
        ctx = self._ctx(
            realization_pct=70.0, avg_actual_r=1.4, avg_planned_rr=2.0,
            rr_sample_count=5
        )
        sections = AICoachService._generate_fallback_sections(ctx)
        assert "take-profit" in sections["improvement"].lower() or "tp" in sections["improvement"].lower()

    def test_top_mistake_improvement_when_present(self):
        ctx = self._ctx(top_mistakes=[
            {"tag": "chasing", "count": 5, "total_cost": -150.0, "after_loss_rate": None}
        ])
        sections = AICoachService._generate_fallback_sections(ctx)
        assert "chasing" in sections["improvement"].lower()

    def test_daily_discipline_improvement_when_violations(self):
        ctx = self._ctx(
            daily_discipline_signals=["1 trade used disallowed setups."],
            daily_disallowed_violations=1,
            daily_outside_allowed=0,
        )
        sections = AICoachService._generate_fallback_sections(ctx)
        assert "allowed" in sections["improvement"].lower() or "disallowed" in sections["improvement"].lower()

    def test_no_plan_improvement_when_zero_planned_trades(self):
        ctx = self._ctx(planned_trade_count=0, total_trades=8)
        sections = AICoachService._generate_fallback_sections(ctx)
        assert "pre-trade plan" in sections["improvement"].lower() or "trade plan" in sections["improvement"].lower()

    def test_improvement_always_non_empty(self):
        ctx = self._ctx()
        sections = AICoachService._generate_fallback_sections(ctx)
        assert len(sections["improvement"]) > 0


# ── generate() — fallback path when no API key ───────────────────────────────

class TestGenerateFallbackPath:
    def test_no_api_key_returns_fallback_source(self, monkeypatch):
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        coach = AICoachService()
        trades = [make_trade("T1")]
        result = coach.generate(trades, make_account())
        assert result.source == "fallback"
        assert result.status == "fallback"

    def test_fallback_has_all_four_fields(self, monkeypatch):
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        coach = AICoachService()
        result = coach.generate([make_trade("T1")], make_account())
        assert result.summary
        assert isinstance(result.top_mistakes, list)
        assert result.diagnosis
        assert result.improvement

    def test_empty_trades_does_not_crash(self, monkeypatch):
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        coach = AICoachService()
        result = coach.generate([], make_account())
        assert result.status == "fallback"
        assert result.summary

    def test_model_used_is_fallback_model(self, monkeypatch):
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        coach = AICoachService()
        result = coach.generate([make_trade("T1")], make_account())
        assert result.model_used == AICoachService.FALLBACK_MODEL
