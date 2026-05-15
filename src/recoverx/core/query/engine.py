from __future__ import annotations

import logging
from typing import Any

from recoverx.core.indexing.engine import IndexEngine

from .filters import FilterBuilder
from .parser import QueryParser

logger = logging.getLogger("recoverx")


class QueryEngine:
    def __init__(self, index_engine: IndexEngine) -> None:
        self._index = index_engine
        self._filter_builder = FilterBuilder()

    def query(self, query_string: str, limit: int = 100, offset: int = 0) -> list[dict[str, Any]]:
        parser = QueryParser(query_string)
        ast = parser.parse()
        where, params = self._filter_builder.build(ast)
        sql = f"SELECT * FROM events WHERE {where} ORDER BY timestamp DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        rows = self._index.storage.fetchall(sql, tuple(params))
        return [dict(r) for r in rows]

    def count(self, query_string: str) -> int:
        parser = QueryParser(query_string)
        ast = parser.parse()
        where, params = self._filter_builder.build(ast)
        sql = f"SELECT COUNT(*) AS cnt FROM events WHERE {where}"
        row = self._index.storage.fetchone(sql, tuple(params))
        return row["cnt"] if row else 0

    def explain(self, query_string: str) -> dict[str, Any]:
        try:
            parser = QueryParser(query_string)
            ast = parser.parse()
            where, params = self._filter_builder.build(ast)
            return {
                "valid": True,
                "ast": repr(ast),
                "sql_where": where,
                "params": params,
            }
        except (ValueError, IndexError) as e:
            return {
                "valid": False,
                "error": str(e),
                "ast": None,
                "sql_where": None,
                "params": [],
            }
