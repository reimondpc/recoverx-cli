from __future__ import annotations

from dataclasses import dataclass
from typing import Any


class QueryNode:
    pass


@dataclass
class LiteralNode(QueryNode):
    value: Any
    value_type: str = "string"

    def __repr__(self) -> str:
        if self.value_type == "string":
            return f"'{self.value}'"
        return str(self.value)


@dataclass
class FieldNode(QueryNode):
    name: str

    def __repr__(self) -> str:
        return self.name


@dataclass
class ComparisonNode(QueryNode):
    left: FieldNode
    operator: str
    right: LiteralNode

    def __repr__(self) -> str:
        return f"{self.left} {self.operator} {self.right}"


@dataclass
class AndNode(QueryNode):
    left: QueryNode
    right: QueryNode

    def __repr__(self) -> str:
        return f"({self.left} AND {self.right})"


@dataclass
class OrNode(QueryNode):
    left: QueryNode
    right: QueryNode

    def __repr__(self) -> str:
        return f"({self.left} OR {self.right})"


@dataclass
class NotNode(QueryNode):
    node: QueryNode

    def __repr__(self) -> str:
        return f"NOT ({self.node})"
