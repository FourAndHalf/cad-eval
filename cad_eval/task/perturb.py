"""Perturbation engine: the parametric-robustness half of the harness.

For each variable declared perturbable in a task's `parametric` block, and
each delta rule on it, produce an independent PerturbedTask: the same task
with exactly one variable changed, its spec text re-rendered, and its
assertions re-resolved against the new value. v1 scope is single-variable
perturbations only (not combinatorial) so a failure can be attributed to
one specific change.
"""
from __future__ import annotations

from pydantic import BaseModel

from cad_eval.task.resolve import ResolvedTask, resolve_task
from cad_eval.task.schema import Delta, TaskSpec


class PerturbedTask(BaseModel):
    base_task_id: str
    perturbed_variable: str
    delta_description: str
    resolved: ResolvedTask


def _apply_delta(default_value, delta: Delta):
    if delta.op == "set":
        return delta.value
    if delta.op == "scale":
        return default_value * delta.factor
    if delta.op == "add":
        return default_value + delta.value
    raise ValueError(f"unknown delta op: {delta.op!r}")


def _describe_delta(variable: str, old_value, new_value) -> str:
    def fmt(v):
        return f"{v:g}" if isinstance(v, float) else str(v)
    return f"{variable}: {fmt(old_value)} -> {fmt(new_value)}"


def generate_perturbations(task: TaskSpec) -> list[PerturbedTask]:
    defaults = {name: v.default for name, v in task.variables.items()}
    perturbations: list[PerturbedTask] = []

    for perturbable in task.parametric.perturbable:
        var_name = perturbable.variable
        old_value = defaults[var_name]
        for delta in perturbable.deltas:
            new_value = _apply_delta(old_value, delta)
            variables = dict(defaults)
            variables[var_name] = new_value
            resolved = resolve_task(task, variables)
            perturbations.append(
                PerturbedTask(
                    base_task_id=task.task_id,
                    perturbed_variable=var_name,
                    delta_description=_describe_delta(var_name, old_value, new_value),
                    resolved=resolved,
                )
            )
    return perturbations
