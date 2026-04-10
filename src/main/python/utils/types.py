from __future__ import annotations

import json
from typing import Any, List, Optional

from sqlalchemy import Text
from sqlalchemy.types import TypeDecorator


class StringList(TypeDecorator):
    """
    Cross-database list-of-strings column type.

    Stores values as a JSON array in a TEXT column — works on SQLite, PostgreSQL,
    and any other SQLAlchemy-supported backend.

    Round-trip contract:
      None  →  NULL in DB  →  None
      []    →  NULL in DB  →  None   (empty list stored as NULL, same as ARRAY behaviour)
      ["a"] →  '["a"]'     →  ["a"]
    """

    impl = Text
    cache_ok = True

    def process_bind_param(self, value: Optional[List[str]], dialect: Any) -> Optional[str]:
        if not value:          # None or empty list → store as NULL
            return None
        return json.dumps(value)

    def process_result_value(self, value: Optional[str], dialect: Any) -> Optional[List[str]]:
        if value is None:
            return None
        return json.loads(value)
