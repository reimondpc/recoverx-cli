from __future__ import annotations

import re
from typing import Any

from .ast import AndNode, ComparisonNode, FieldNode, LiteralNode, NotNode, OrNode, QueryNode
from .operators import Operator

TOKEN_PATTERN = re.compile(
    r"(\bAND\b|\bOR\b|\bNOT\b|"
    r"==|!=|>=|<=|>|<|"
    r"contains|!contains|starts|ends|in|!in|~|"
    r"'[^']*'|\"[^\"]*\"|"
    r"\b\w+\b|"
    r"[()])"
)

STRING_PATTERN = re.compile(r"^['\"](.*)['\"]$")


class QueryParser:
    def __init__(self, query_string: str) -> None:
        self._tokens = self._tokenize(query_string)
        self._pos = 0

    def parse(self) -> QueryNode:
        if not self._tokens:
            raise ValueError("Empty query")
        result = self._parse_or()
        if self._pos < len(self._tokens):
            raise ValueError(f"Unexpected token at position {self._pos}: {self._tokens[self._pos]}")
        return result

    def _parse_or(self) -> QueryNode:
        left = self._parse_and()
        while self._pos < len(self._tokens) and self._tokens[self._pos] == "OR":
            self._pos += 1
            right = self._parse_and()
            left = OrNode(left, right)
        return left

    def _parse_and(self) -> QueryNode:
        left = self._parse_not()
        while self._pos < len(self._tokens) and self._tokens[self._pos] == "AND":
            self._pos += 1
            right = self._parse_not()
            left = AndNode(left, right)
        return left

    def _parse_not(self) -> QueryNode:
        if self._pos < len(self._tokens) and self._tokens[self._pos] == "NOT":
            self._pos += 1
            node = self._parse_primary()
            return NotNode(node)
        return self._parse_primary()

    def _parse_primary(self) -> QueryNode:
        if self._pos >= len(self._tokens):
            raise ValueError("Unexpected end of query")

        token = self._tokens[self._pos]

        if token == "(":
            self._pos += 1
            node = self._parse_or()
            if self._pos >= len(self._tokens) or self._tokens[self._pos] != ")":
                raise ValueError("Missing closing parenthesis")
            self._pos += 1
            return node

        if token in ("AND", "OR", "NOT"):
            raise ValueError(f"Unexpected operator '{token}' at position {self._pos}")

        return self._parse_comparison()

    def _parse_comparison(self) -> ComparisonNode:
        field_token = self._tokens[self._pos]
        field = FieldNode(field_token.lower())
        self._pos += 1

        if self._pos >= len(self._tokens):
            raise ValueError(f"Expected operator after '{field_token}'")

        op_token = self._tokens[self._pos]
        try:
            operator = Operator.from_string(op_token)
        except ValueError:
            raise ValueError(f"Invalid operator '{op_token}' at position {self._pos}")
        self._pos += 1

        if self._pos >= len(self._tokens):
            raise ValueError(f"Expected value after operator '{op_token}'")

        value_token = self._tokens[self._pos]
        value, value_type = self._parse_literal(value_token)
        self._pos += 1

        return ComparisonNode(
            left=field, operator=operator.value, right=LiteralNode(value, value_type)
        )

    def _parse_literal(self, token: str) -> tuple[Any, str]:
        m = STRING_PATTERN.match(token)
        if m:
            return m.group(1), "string"

        if token.lower() == "true":
            return True, "bool"
        if token.lower() == "false":
            return False, "bool"
        if token.lower() == "null" or token.lower() == "none":
            return None, "null"

        try:
            return int(token), "int"
        except ValueError:
            pass

        try:
            return float(token), "float"
        except ValueError:
            pass

        return token, "string"

    def _tokenize(self, query: str) -> list[str]:
        tokens = TOKEN_PATTERN.findall(query)
        return [t.strip() for t in tokens if t.strip()]
