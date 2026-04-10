from __future__ import annotations

import uuid
from datetime import date
from typing import List, Optional

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from src.main.python.models.daily_plan import DailyPlan, DailyReview
from src.main.python.models.db_models import DailyPlanModel, DailyReviewModel
from src.main.python.utils.logging_utils import get_logger

logger = get_logger(__name__)


def _orm_to_plan(orm: DailyPlanModel) -> DailyPlan:
    return DailyPlan(
        plan_id=orm.plan_id,
        account_id=orm.account_id,
        trading_date=orm.trading_date,
        market_bias=orm.market_bias,
        symbols_in_focus=list(orm.symbols_in_focus) if orm.symbols_in_focus else [],
        key_levels=orm.key_levels,
        major_news=orm.major_news,
        allowed_setups=list(orm.allowed_setups) if orm.allowed_setups else [],
        disallowed_setups=list(orm.disallowed_setups) if orm.disallowed_setups else [],
        daily_max_risk_pct=orm.daily_max_risk_pct,
        max_trades=orm.max_trades,
        behavioral_focus=orm.behavioral_focus,
        special_rule=orm.special_rule,
        created_at=orm.created_at,
        updated_at=orm.updated_at,
    )


def _orm_to_review(orm: DailyReviewModel) -> DailyReview:
    return DailyReview(
        review_id=orm.review_id,
        account_id=orm.account_id,
        trading_date=orm.trading_date,
        plan_id=orm.plan_id,
        total_trades=orm.total_trades,
        total_pnl=orm.total_pnl,
        total_r=orm.total_r,
        planned_trades=orm.planned_trades,
        unplanned_trades=orm.unplanned_trades,
        best_trade_id=orm.best_trade_id,
        worst_trade_id=orm.worst_trade_id,
        biggest_mistake=orm.biggest_mistake,
        emotional_summary=orm.emotional_summary,
        improvement_point=orm.improvement_point,
        notes=orm.notes,
        process_success=orm.process_success,
        pnl_success=orm.pnl_success,
        created_at=orm.created_at,
        updated_at=orm.updated_at,
    )


class DailyPlanRepository:
    """
    CRUD for DailyPlan and DailyReview.
    Caller provides and commits the session.
    """

    def __init__(self, session: Session) -> None:
        self._session = session

    # ── Daily Plan ─────────────────────────────────────────────────────────────

    def create_plan(self, account_id: str, data: DailyPlan) -> DailyPlan:
        orm = DailyPlanModel(
            plan_id=data.plan_id or str(uuid.uuid4()),
            account_id=account_id,
            trading_date=data.trading_date,
            market_bias=data.market_bias,
            symbols_in_focus=data.symbols_in_focus or None,
            key_levels=data.key_levels,
            major_news=data.major_news,
            allowed_setups=data.allowed_setups or None,
            disallowed_setups=data.disallowed_setups or None,
            daily_max_risk_pct=data.daily_max_risk_pct,
            max_trades=data.max_trades,
            behavioral_focus=data.behavioral_focus,
            special_rule=data.special_rule,
        )
        self._session.add(orm)
        self._session.flush()
        return _orm_to_plan(orm)

    def get_plan_by_id(self, plan_id: str) -> Optional[DailyPlan]:
        row = self._session.get(DailyPlanModel, plan_id)
        return _orm_to_plan(row) if row else None

    def get_plan_by_date(self, account_id: str, trading_date: date) -> Optional[DailyPlan]:
        stmt = select(DailyPlanModel).where(
            DailyPlanModel.account_id == account_id,
            DailyPlanModel.trading_date == trading_date,
        )
        row = self._session.execute(stmt).scalar_one_or_none()
        return _orm_to_plan(row) if row else None

    def list_plans(self, account_id: str, from_date: Optional[date] = None, to_date: Optional[date] = None) -> List[DailyPlan]:
        stmt = select(DailyPlanModel).where(DailyPlanModel.account_id == account_id)
        if from_date:
            stmt = stmt.where(DailyPlanModel.trading_date >= from_date)
        if to_date:
            stmt = stmt.where(DailyPlanModel.trading_date <= to_date)
        stmt = stmt.order_by(DailyPlanModel.trading_date.desc())
        rows = self._session.execute(stmt).scalars().all()
        return [_orm_to_plan(r) for r in rows]

    def update_plan(self, plan_id: str, updates: dict) -> Optional[DailyPlan]:
        row = self._session.get(DailyPlanModel, plan_id)
        if not row:
            return None
        for key, value in updates.items():
            if hasattr(row, key) and value is not None:
                setattr(row, key, value)
        self._session.flush()
        return _orm_to_plan(row)

    def delete_plan(self, plan_id: str) -> bool:
        stmt = delete(DailyPlanModel).where(DailyPlanModel.plan_id == plan_id)
        result = self._session.execute(stmt)
        return result.rowcount > 0

    # ── Daily Review ───────────────────────────────────────────────────────────

    def create_review(self, account_id: str, data: DailyReview) -> DailyReview:
        orm = DailyReviewModel(
            review_id=data.review_id or str(uuid.uuid4()),
            account_id=account_id,
            trading_date=data.trading_date,
            plan_id=data.plan_id,
            total_trades=data.total_trades,
            total_pnl=data.total_pnl,
            total_r=data.total_r,
            planned_trades=data.planned_trades,
            unplanned_trades=data.unplanned_trades,
            best_trade_id=data.best_trade_id,
            worst_trade_id=data.worst_trade_id,
            biggest_mistake=data.biggest_mistake,
            emotional_summary=data.emotional_summary,
            improvement_point=data.improvement_point,
            notes=data.notes,
            process_success=data.process_success,
            pnl_success=data.pnl_success,
        )
        self._session.add(orm)
        self._session.flush()
        return _orm_to_review(orm)

    def get_review_by_id(self, review_id: str) -> Optional[DailyReview]:
        row = self._session.get(DailyReviewModel, review_id)
        return _orm_to_review(row) if row else None

    def get_review_by_date(self, account_id: str, trading_date: date) -> Optional[DailyReview]:
        stmt = select(DailyReviewModel).where(
            DailyReviewModel.account_id == account_id,
            DailyReviewModel.trading_date == trading_date,
        )
        row = self._session.execute(stmt).scalar_one_or_none()
        return _orm_to_review(row) if row else None

    def list_reviews(self, account_id: str, from_date: Optional[date] = None, to_date: Optional[date] = None) -> List[DailyReview]:
        stmt = select(DailyReviewModel).where(DailyReviewModel.account_id == account_id)
        if from_date:
            stmt = stmt.where(DailyReviewModel.trading_date >= from_date)
        if to_date:
            stmt = stmt.where(DailyReviewModel.trading_date <= to_date)
        stmt = stmt.order_by(DailyReviewModel.trading_date.desc())
        rows = self._session.execute(stmt).scalars().all()
        return [_orm_to_review(r) for r in rows]

    def update_review(self, review_id: str, updates: dict) -> Optional[DailyReview]:
        row = self._session.get(DailyReviewModel, review_id)
        if not row:
            return None
        for key, value in updates.items():
            if hasattr(row, key) and value is not None:
                setattr(row, key, value)
        self._session.flush()
        return _orm_to_review(row)

    def delete_review(self, review_id: str) -> bool:
        stmt = delete(DailyReviewModel).where(DailyReviewModel.review_id == review_id)
        result = self._session.execute(stmt)
        return result.rowcount > 0
