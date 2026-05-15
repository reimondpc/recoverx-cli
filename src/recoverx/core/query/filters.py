from __future__ import annotations

from typing import Any

from .ast import AndNode, ComparisonNode, NotNode, OrNode, QueryNode


class FilterBuilder:
    FIELD_MAP: dict[str, str] = {
        "event": "event_type",
        "type": "event_type",
        "event_type": "event_type",
        "source": "source",
        "filename": "filename",
        "name": "filename",
        "timestamp": "timestamp",
        "time": "timestamp",
        "mft": "mft_reference",
        "mft_ref": "mft_reference",
        "parent_mft": "parent_mft_reference",
        "confidence": "confidence",
        "size": "file_size",
        "file_size": "file_size",
        "previous_name": "previous_filename",
        "old_name": "previous_filename",
        "sha256": "sha256",
        "hash": "sha256",
    }

    def __init__(self) -> None:
        self._clauses: list[str] = []
        self._params: list[Any] = []

    def build(self, node: QueryNode) -> tuple[str, list[Any]]:
        self._clauses = []
        self._params = []
        self._visit(node)
        where = " AND ".join(self._clauses) if self._clauses else "1=1"
        return where, self._params

    def _visit(self, node: QueryNode) -> None:
        if isinstance(node, ComparisonNode):
            self._handle_comparison(node)
        elif isinstance(node, AndNode):
            left_clauses = self._clauses.copy()
            left_params = self._params.copy()
            self._clauses = []
            self._params = []
            self._visit(node.left)
            right_clauses = self._clauses
            right_params = self._params

            self._clauses = left_clauses
            self._params = left_params
            self._clauses.append(f"({' AND '.join(right_clauses)})")
            self._params.extend(right_params)

        elif isinstance(node, OrNode):
            left_clauses = self._clauses.copy()
            left_params = self._params.copy()
            self._clauses = []
            self._params = []
            self._visit(node.left)
            right_clauses = self._clauses
            right_params = self._params

            self._clauses = left_clauses
            self._params = left_params
            self._clauses.append(f"({' OR '.join(right_clauses)})")
            self._params.extend(right_params)

        elif isinstance(node, NotNode):
            self._clauses.append("NOT (")
            saved_clauses = self._clauses.copy()
            saved_params = self._params.copy()
            self._clauses = []
            self._params = []
            self._visit(node.node)
            self._clauses = saved_clauses + self._clauses
            self._params = saved_params + self._params
            self._clauses.append(")")

    def _handle_comparison(self, node: ComparisonNode) -> None:
        field_name = self.FIELD_MAP.get(node.left.name, node.left.name)
        op = node.operator
        value = node.right.value
        if op == "==":
            self._clauses.append(f"{field_name} = ?")
            self._params.append(value)
        elif op == "!=":
            self._clauses.append(f"{field_name} != ?")
            self._params.append(value)
        elif op == ">":
            self._clauses.append(f"{field_name} > ?")
            self._params.append(value)
        elif op == ">=":
            self._clauses.append(f"{field_name} >= ?")
            self._params.append(value)
        elif op == "<":
            self._clauses.append(f"{field_name} < ?")
            self._params.append(value)
        elif op == "<=":
            self._clauses.append(f"{field_name} <= ?")
            self._params.append(value)
        elif op == "contains":
            self._clauses.append(f"{field_name} LIKE ?")
            self._params.append(f"%{value}%")
        elif op == "!contains":
            self._clauses.append(f"{field_name} NOT LIKE ?")
            self._params.append(f"%{value}%")
        elif op == "starts":
            self._clauses.append(f"{field_name} LIKE ?")
            self._params.append(f"{value}%")
        elif op == "ends":
            self._clauses.append(f"{field_name} LIKE ?")
            self._params.append(f"%{value}")
        elif op == "~":
            self._clauses.append(f"{field_name} LIKE ?")
            self._params.append(value)
        else:
            self._clauses.append(f"{field_name} = ?")
            self._params.append(value)
