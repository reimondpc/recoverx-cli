from __future__ import annotations

from recoverx.core.query.ast import AndNode, ComparisonNode, FieldNode, LiteralNode, NotNode, OrNode
from recoverx.core.query.operators import Operator
from recoverx.core.query.parser import QueryParser


class TestQueryAST:
    def test_literal_node(self):
        n = LiteralNode(value=42, value_type="int")
        assert n.value == 42
        assert "42" in repr(n)

    def test_field_node(self):
        n = FieldNode(name="filename")
        assert n.name == "filename"

    def test_comparison_node(self):
        n = ComparisonNode(
            left=FieldNode("event"), operator="==", right=LiteralNode("FILE_DELETED")
        )
        assert n.left.name == "event"
        assert n.operator == "=="


class TestQueryParser:
    def test_simple_eq(self):
        parser = QueryParser("event == FILE_DELETED")
        ast = parser.parse()
        assert isinstance(ast, ComparisonNode)
        assert ast.left.name == "event"
        assert ast.operator == "=="

    def test_simple_contains(self):
        parser = QueryParser('name contains "test"')
        ast = parser.parse()
        assert isinstance(ast, ComparisonNode)
        assert ast.right.value == "test"

    def test_and_expression(self):
        parser = QueryParser('event == FILE_DELETED AND name contains "doc"')
        ast = parser.parse()
        assert isinstance(ast, AndNode)

    def test_or_expression(self):
        parser = QueryParser('source == "MFT" OR source == "USN"')
        ast = parser.parse()
        assert isinstance(ast, OrNode)

    def test_not_expression(self):
        parser = QueryParser("NOT event == FILE_DELETED")
        ast = parser.parse()
        assert isinstance(ast, NotNode)

    def test_complex_expression(self):
        parser = QueryParser('(event == FILE_CREATED AND source == "MFT") OR event == FILE_DELETED')
        ast = parser.parse()
        assert isinstance(ast, OrNode)

    def test_timestamp_comparison(self):
        parser = QueryParser('timestamp > "2026-01-01"')
        ast = parser.parse()
        assert ast.operator == ">"

    def test_empty_query(self):
        import pytest

        with pytest.raises(ValueError, match="Empty query"):
            QueryParser("").parse()

    def test_missing_operator(self):
        import pytest

        with pytest.raises(ValueError):
            QueryParser("filename").parse()


class TestOperator:
    def test_from_string(self):
        assert Operator.from_string("==") == Operator.EQ
        assert Operator.from_string("!=") == Operator.NEQ
        assert Operator.from_string("contains") == Operator.CONTAINS
        assert Operator.from_string("~") == Operator.LIKE

    def test_to_sql(self):
        assert Operator.EQ.to_sql() == "="
        assert Operator.CONTAINS.to_sql() == "LIKE"
        assert Operator.NOT_CONTAINS.to_sql() == "NOT LIKE"

    def test_supports_lists(self):
        assert Operator.IN.supports_lists
        assert not Operator.EQ.supports_lists


class TestFilterBuilder:
    def test_build_eq(self):
        from recoverx.core.query.filters import FilterBuilder

        parser = QueryParser("event == FILE_DELETED")
        ast = parser.parse()
        builder = FilterBuilder()
        where, params = builder.build(ast)
        assert "event_type" in where
        assert "=" in where

    def test_build_contains(self):
        from recoverx.core.query.filters import FilterBuilder

        parser = QueryParser('name contains ".docx"')
        ast = parser.parse()
        builder = FilterBuilder()
        where, params = builder.build(ast)
        assert "filename" in where
        assert "LIKE" in where
