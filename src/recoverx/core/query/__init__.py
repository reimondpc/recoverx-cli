"""Forensic query engine for structured and ad-hoc searches.

Provides a simple query language parser, AST representation,
filter builder, and execution engine for searching indexed
forensic data.
"""

from __future__ import annotations

from .ast import AndNode, ComparisonNode, FieldNode, LiteralNode, NotNode, OrNode, QueryNode
from .engine import QueryEngine
from .filters import FilterBuilder
from .operators import Operator
from .parser import QueryParser

__all__ = [
    "QueryEngine",
    "QueryParser",
    "FilterBuilder",
    "Operator",
    "QueryNode",
    "ComparisonNode",
    "AndNode",
    "OrNode",
    "NotNode",
    "FieldNode",
    "LiteralNode",
]
