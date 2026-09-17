"""Diff two RunResults -- the mechanism for "a prompt or model change shows
a clear diff between two report runs"."""
from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel

from cad_eval.report.models import RunResult, TaskResult


class DiffRow(BaseModel):
    key: str
    task_id: str
    variant: str
    perturbed_variable: str | None
    status_a: str | None
    status_b: str | None
    transition: str  # "regression" | "improvement" | "unchanged_pass" | "unchanged_fail" | "added" | "removed"


class RunDiff(BaseModel):
    run_a_id: str
    run_b_id: str
    rows: list[DiffRow]
    pass_rate_a: float | None
    pass_rate_b: float | None


def _key(t: TaskResult) -> str:
    return f"{t.task_id}::{t.variant}::{t.perturbed_variable or ''}::{t.delta_description or ''}"


def _pass_rate(tasks: list[TaskResult]) -> float | None:
    if not tasks:
        return None
    return sum(1 for t in tasks if t.overall_status == "pass") / len(tasks) * 100.0


def _transition(status_a: str | None, status_b: str | None) -> str:
    if status_a is None:
        return "added"
    if status_b is None:
        return "removed"
    a_pass, b_pass = status_a == "pass", status_b == "pass"
    if a_pass and not b_pass:
        return "regression"
    if not a_pass and b_pass:
        return "improvement"
    return "unchanged_pass" if a_pass else "unchanged_fail"


def diff_runs(run_a: RunResult, run_b: RunResult) -> RunDiff:
    by_key_a = {_key(t): t for t in run_a.tasks}
    by_key_b = {_key(t): t for t in run_b.tasks}

    rows = []
    for key in sorted(set(by_key_a) | set(by_key_b)):
        a, b = by_key_a.get(key), by_key_b.get(key)
        ref = a or b
        rows.append(DiffRow(
            key=key, task_id=ref.task_id, variant=ref.variant, perturbed_variable=ref.perturbed_variable,
            status_a=a.overall_status if a else None,
            status_b=b.overall_status if b else None,
            transition=_transition(a.overall_status if a else None, b.overall_status if b else None),
        ))

    return RunDiff(
        run_a_id=run_a.run_id, run_b_id=run_b.run_id, rows=rows,
        pass_rate_a=_pass_rate(run_a.tasks), pass_rate_b=_pass_rate(run_b.tasks),
    )


def load_run(path: str | Path) -> RunResult:
    return RunResult.model_validate_json(Path(path).read_text())
