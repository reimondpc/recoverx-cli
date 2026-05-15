from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any


class ExecutionStep(Enum):
    FILTER_PUSHDOWN = auto()
    INDEX_SCAN = auto()
    TABLE_SCAN = auto()
    SORT = auto()
    LIMIT = auto()
    AGGREGATE = auto()


@dataclass
class QueryPlan:
    original_query: str = ""
    steps: list[ExecutionStep] = field(default_factory=list)
    estimated_rows: int = 0
    use_index: bool = False
    index_columns: list[str] = field(default_factory=list)
    optimized_sql: str = ""
    estimated_cost: float = 0.0

    def add_step(self, step: ExecutionStep) -> None:
        self.steps.append(step)

    def to_dict(self) -> dict[str, Any]:
        return {
            "steps": [s.name for s in self.steps],
            "estimated_rows": self.estimated_rows,
            "use_index": self.use_index,
            "index_columns": self.index_columns,
            "optimized_sql": self.optimized_sql,
            "estimated_cost": self.estimated_cost,
        }


class QueryPlanner:
    INDEXABLE_FIELDS = {"event_type", "source", "timestamp", "filename", "mft_reference", "case_id"}

    def plan(self, query: str, available_indexes: set[str] | None = None) -> QueryPlan:
        plan = QueryPlan(original_query=query, use_index=True)
        indexes = available_indexes if available_indexes is not None else self.INDEXABLE_FIELDS

        plan.add_step(ExecutionStep.FILTER_PUSHDOWN)

        for field in self.INDEXABLE_FIELDS:
            if field in query.lower():
                if field in indexes:
                    plan.add_step(ExecutionStep.INDEX_SCAN)
                    plan.index_columns.append(field)
                else:
                    plan.add_step(ExecutionStep.TABLE_SCAN)

        if "order by" in query.lower() or "sort" in query.lower():
            plan.add_step(ExecutionStep.SORT)
        if "limit" in query.lower():
            plan.add_step(ExecutionStep.LIMIT)
        if "count" in query.lower() or "sum" in query.lower():
            plan.add_step(ExecutionStep.AGGREGATE)

        plan.estimated_rows = self._estimate_rows(query)
        plan.estimated_cost = self._estimate_cost(plan)
        plan.optimized_sql = self._rewrite(query, indexes)
        return plan

    def _estimate_rows(self, query: str) -> int:
        if "event_type" in query.lower():
            return 1000
        if "timestamp" in query.lower():
            return 5000
        return 10000

    def _estimate_cost(self, plan: QueryPlan) -> float:
        cost = 0.0
        for step in plan.steps:
            if step == ExecutionStep.FILTER_PUSHDOWN:
                cost += 0.5
            elif step == ExecutionStep.INDEX_SCAN:
                cost += 1.0
            elif step == ExecutionStep.TABLE_SCAN:
                cost += 10.0
            elif step == ExecutionStep.SORT:
                cost += 5.0
            elif step == ExecutionStep.LIMIT:
                cost += 0.1
            elif step == ExecutionStep.AGGREGATE:
                cost += 2.0
        return cost

    def _rewrite(self, query: str, indexes: set[str]) -> str:
        rewritten = query
        for field in indexes:
            old = f"{field} = ?"
            new = f"{field} = ?"
            if f"indexed_{field}" not in rewritten:
                rewritten = rewritten.replace(old, new)
        return rewritten


def optimize_sql(sql: str, indexes: set[str] | None = None) -> str:
    planner = QueryPlanner()
    plan = planner.plan(sql, indexes)
    return plan.optimized_sql
