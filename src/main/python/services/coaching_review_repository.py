from __future__ import annotations

import json
from datetime import datetime
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.main.python.models.db_models import CoachingReviewModel
from src.main.python.utils.logging_utils import get_logger

logger = get_logger(__name__)


class CoachingReviewRepository:
    """
    CRUD operations for CoachingReviewModel.
    Caller provides and manages the session lifecycle.
    """

    def __init__(self, session: Session) -> None:
        self._session = session

    def save(self, review: CoachingReviewModel) -> CoachingReviewModel:
        self._session.add(review)
        self._session.flush()
        logger.info(
            "Saved coaching review review_id=%s account=%s source=%s status=%s",
            review.review_id, review.account_id, review.source, review.status,
        )
        return review

    def get_by_id(self, review_id: str) -> Optional[CoachingReviewModel]:
        return self._session.get(CoachingReviewModel, review_id)

    def list_by_account(self, account_id: str, limit: int = 20) -> List[CoachingReviewModel]:
        """Return most recent coaching reviews for an account, newest first."""
        stmt = (
            select(CoachingReviewModel)
            .where(CoachingReviewModel.account_id == account_id)
            .order_by(CoachingReviewModel.generated_at.desc())
            .limit(limit)
        )
        return list(self._session.execute(stmt).scalars().all())
