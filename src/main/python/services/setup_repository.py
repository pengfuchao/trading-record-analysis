from __future__ import annotations

from typing import List, Optional

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from src.main.python.models.db_models import SetupDefinitionModel
from src.main.python.models.setup import SetupDefinition
from src.main.python.utils.db_converters import orm_to_setup, setup_to_orm
from src.main.python.utils.logging_utils import get_logger

logger = get_logger(__name__)


class SetupRepository:
    """
    CRUD operations for SetupDefinition objects against the setup_definitions table.
    Does NOT manage Session lifecycle — caller provides and commits the session.
    """

    def __init__(self, session: Session) -> None:
        self._session = session

    def save(self, setup: SetupDefinition) -> SetupDefinition:
        """Upsert setup by primary key. Returns saved SetupDefinition."""
        orm_obj = setup_to_orm(setup)
        merged = self._session.merge(orm_obj)
        self._session.flush()
        return orm_to_setup(merged)

    def get_by_id(self, setup_id: str) -> Optional[SetupDefinition]:
        stmt = select(SetupDefinitionModel).where(SetupDefinitionModel.setup_id == setup_id)
        row = self._session.execute(stmt).scalar_one_or_none()
        return orm_to_setup(row) if row else None

    def list_all(self) -> List[SetupDefinition]:
        """Return all setups ordered by name."""
        stmt = select(SetupDefinitionModel).order_by(SetupDefinitionModel.name.asc())
        rows = self._session.execute(stmt).scalars().all()
        return [orm_to_setup(r) for r in rows]

    def list_by_strategy_group(self, strategy_group: str) -> List[SetupDefinition]:
        stmt = (
            select(SetupDefinitionModel)
            .where(SetupDefinitionModel.strategy_group == strategy_group)
            .order_by(SetupDefinitionModel.name.asc())
        )
        rows = self._session.execute(stmt).scalars().all()
        return [orm_to_setup(r) for r in rows]

    def delete(self, setup_id: str) -> bool:
        """Returns True if a row was deleted, False if setup_id not found."""
        stmt = delete(SetupDefinitionModel).where(SetupDefinitionModel.setup_id == setup_id)
        result = self._session.execute(stmt)
        return result.rowcount > 0
