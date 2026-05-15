from __future__ import annotations

from enum import Enum


class Operator(str, Enum):
    EQ = "=="
    NEQ = "!="
    GT = ">"
    GTE = ">="
    LT = "<"
    LTE = "<="
    CONTAINS = "contains"
    NOT_CONTAINS = "!contains"
    STARTS_WITH = "starts"
    ENDS_WITH = "ends"
    IN = "in"
    NOT_IN = "!in"
    LIKE = "~"

    @classmethod
    def from_string(cls, s: str) -> Operator:
        op_map = {
            "==": cls.EQ,
            "!=": cls.NEQ,
            ">": cls.GT,
            ">=": cls.GTE,
            "<": cls.LT,
            "<=": cls.LTE,
            "contains": cls.CONTAINS,
            "!contains": cls.NOT_CONTAINS,
            "starts": cls.STARTS_WITH,
            "ends": cls.ENDS_WITH,
            "in": cls.IN,
            "!in": cls.NOT_IN,
            "~": cls.LIKE,
        }
        if s in op_map:
            return op_map[s]
        raise ValueError(f"Unknown operator: {s}")

    def to_sql(self) -> str:
        sql_map = {
            self.EQ: "=",
            self.NEQ: "!=",
            self.GT: ">",
            self.GTE: ">=",
            self.LT: "<",
            self.LTE: "<=",
            self.CONTAINS: "LIKE",
            self.NOT_CONTAINS: "NOT LIKE",
            self.LIKE: "LIKE",
        }
        return sql_map.get(self, "=")

    @property
    def supports_lists(self) -> bool:
        return self in (self.IN, self.NOT_IN)
