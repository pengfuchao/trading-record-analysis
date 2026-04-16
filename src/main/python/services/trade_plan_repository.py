from __future__ import annotations

import uuid
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.main.python.models.db_models import TradePlanModel
from src.main.python.models.trade_plan import TradePlan
from src.main.python.utils.logging_utils import get_logger

logger = get_logger(__name__)


def _orm_to_plan(orm: TradePlanModel) -> TradePlan:
    return TradePlan(
        plan_id=orm.plan_id,
        account_id=orm.account_id,
        status=orm.status,
        symbol=orm.symbol,
        intended_direction=orm.intended_direction,
        setup_type=orm.setup_type,
        strategy=orm.strategy,
        bias=orm.bias,
        thesis=orm.thesis,
        entry_logic=orm.entry_logic,
        stop_loss_logic=orm.stop_loss_logic,
        take_profit_logic=orm.take_profit_logic,
        invalidation_logic=orm.invalidation_logic,
        planned_entry_zone=orm.planned_entry_zone,
        planned_stop_loss=orm.planned_stop_loss,
        planned_take_profit=orm.planned_take_profit,
        planned_rr=orm.planned_rr,
        is_a_plus_setup=orm.is_a_plus_setup,
        notes=orm.notes,
        created_at=orm.created_at,
        updated_at=orm.updated_at,
    )


class TradePlanRepository:
    """CRUD for TradePlan. Caller provides and commits the session."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def create(self, account_id: str, data: TradePlan) -> TradePlan:
        orm = TradePlanModel(
            plan_id=data.plan_id or str(uuid.uuid4()),
            account_id=account_id,
            status=data.status or "planned",
            symbol=data.symbol,
            intended_direction=data.intended_direction,
            setup_type=data.setup_type,
            strategy=data.strategy,
            bias=data.bias,
            thesis=data.thesis,
            entry_logic=data.entry_logic,
            stop_loss_logic=data.stop_loss_logic,
            take_profit_logic=data.take_profit_logic,
            invalidation_logic=data.invalidation_logic,
            planned_entry_zone=data.planned_entry_zone,
            planned_stop_loss=data.planned_stop_loss,
            planned_take_profit=data.planned_take_profit,
            planned_rr=data.planned_rr,
            is_a_plus_setup=data.is_a_plus_setup,
            notes=data.notes,
        )
        self._session.add(orm)
        self._session.flush()
        return _orm_to_plan(orm)

    def get_by_id(self, plan_id: str) -> Optional[TradePlan]:
        row = self._session.get(TradePlanModel, plan_id)
        return _orm_to_plan(row) if row else None

    def list_by_account(
        self,
        account_id: str,
        status: Optional[str] = None,
    ) -> List[TradePlan]:
        stmt = (
            select(TradePlanModel)
            .where(TradePlanModel.account_id == account_id)
        )
        if status:
            stmt = stmt.where(TradePlanModel.status == status)
        stmt = stmt.order_by(TradePlanModel.created_at.desc())
        rows = self._session.execute(stmt).scalars().all()
        return [_orm_to_plan(r) for r in rows]

    def update(self, plan_id: str, updates: dict) -> Optional[TradePlan]:
        row = self._session.get(TradePlanModel, plan_id)
        if not row:
            return None
        for key, value in updates.items():
            if hasattr(row, key):
                setattr(row, key, value)
        self._session.flush()
        return _orm_to_plan(row)

    def delete(self, plan_id: str) -> bool:
        row = self._session.get(TradePlanModel, plan_id)
        if not row:
            return False
        self._session.delete(row)
        self._session.flush()
        return True
