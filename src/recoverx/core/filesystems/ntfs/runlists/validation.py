from __future__ import annotations

from dataclasses import dataclass

from .mapping import DataRun


@dataclass
class RunlistIssue:
    code: str = ""
    message: str = ""
    severity: str = "warning"

    def to_dict(self) -> dict:
        return {
            "code": self.code,
            "message": self.message,
            "severity": self.severity,
        }


def validate_runlist(
    resolved: list[DataRun],
    total_clusters: int,
    volume_clusters: int = 0,
) -> list[RunlistIssue]:
    issues: list[RunlistIssue] = []

    if not resolved:
        issues.append(
            RunlistIssue(
                code="EMPTY_RUNLIST",
                message="Runlist is empty — no data runs to execute",
                severity="error",
            )
        )
        return issues

    seen_lcn_ranges: list[tuple[int, int]] = []
    prev_vcn_end = -1

    for i, run in enumerate(resolved):
        if run.cluster_count == 0:
            issues.append(
                RunlistIssue(
                    code="ZERO_CLUSTER_COUNT",
                    message=f"Run {i}: cluster_count is zero",
                    severity="error",
                )
            )
            continue

        if run.cluster_count > 1_000_000:
            issues.append(
                RunlistIssue(
                    code="IMPOSSIBLE_SIZE",
                    message=f"Run {i}: impossible cluster count {run.cluster_count}",
                    severity="error",
                )
            )

        if run.vcn_start <= prev_vcn_end:
            issues.append(
                RunlistIssue(
                    code="VCN_OVERLAP",
                    message=f"Run {i}: VCN range overlaps previous run "
                    f"({run.vcn_start} <= {prev_vcn_end})",
                    severity="error",
                )
            )
        prev_vcn_end = run.vcn_end

        if run.is_sparse:
            continue

        lcn_start = run.lcn
        lcn_end = run.lcn + run.cluster_count - 1

        if lcn_start < 0:
            issues.append(
                RunlistIssue(
                    code="INVALID_LCN",
                    message=f"Run {i}: negative LCN {lcn_start}",
                    severity="error",
                )
            )

        if volume_clusters > 0 and lcn_end >= volume_clusters:
            issues.append(
                RunlistIssue(
                    code="LCN_OUT_OF_BOUNDS",
                    message=f"Run {i}: LCN range [{lcn_start}, {lcn_end}] "
                    f"exceeds volume ({volume_clusters} clusters)",
                    severity="error",
                )
            )

        for j, (seen_start, seen_end) in enumerate(seen_lcn_ranges):
            if lcn_start <= seen_end and lcn_end >= seen_start:
                issues.append(
                    RunlistIssue(
                        code="LCN_OVERLAP",
                        message=f"Run {i}: LCN range [{lcn_start}, {lcn_end}] "
                        f"overlaps run {j} range [{seen_start}, {seen_end}]",
                        severity="error",
                    )
                )
        seen_lcn_ranges.append((lcn_start, lcn_end))

    if total_clusters > 0:
        last_vcn = resolved[-1].vcn_end if resolved else 0
        if last_vcn >= total_clusters:
            issues.append(
                RunlistIssue(
                    code="VCN_EXCEEDS_TOTAL",
                    message=f"Last VCN {last_vcn} exceeds total clusters {total_clusters}",
                    severity="error",
                )
            )

    return issues


def check_circular_runs(resolved: list[DataRun]) -> list[RunlistIssue]:
    issues: list[RunlistIssue] = []
    seen_lcns: set[int] = set()
    for i, run in enumerate(resolved):
        if run.is_sparse or run.lcn < 0:
            continue
        for c in range(run.lcn, run.lcn + run.cluster_count):
            if c in seen_lcns:
                issues.append(
                    RunlistIssue(
                        code="CIRCULAR_RUN",
                        message=f"Run {i}: LCN {c} already referenced by an earlier run",
                        severity="error",
                    )
                )
                break
            seen_lcns.add(c)
    return issues


def validate_data_run_integrity(
    resolved: list[DataRun],
    real_size: int,
    initialised_size: int,
    cluster_size: int,
) -> list[RunlistIssue]:
    issues: list[RunlistIssue] = []
    virtual_size = 0
    if resolved:
        virtual_size = (resolved[-1].vcn_end + 1) * cluster_size

    if real_size > virtual_size:
        issues.append(
            RunlistIssue(
                code="REAL_SIZE_EXCEEDS_VIRTUAL",
                message=f"real_size ({real_size}) > virtual_size ({virtual_size})",
                severity="error",
            )
        )

    if initialised_size > real_size:
        issues.append(
            RunlistIssue(
                code="INITIALISED_EXCEEDS_REAL",
                message=f"initialised_size ({initialised_size}) > real_size ({real_size})",
                severity="warning",
            )
        )

    return issues
