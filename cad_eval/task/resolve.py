"""Resolve a TaskSpec's Jinja2-templated spec text and assertion params
against a concrete variable-value dict, producing plain numeric values the
checker can consume directly.

Shared by base-task evaluation (variables = declared defaults) and the
perturbation engine (variables = defaults with one variable overridden).
"""
from __future__ import annotations

from pydantic import BaseModel, Field

from jinja2 import Environment, StrictUndefined

from cad_eval.task.schema import TaskSpec

_env = Environment(undefined=StrictUndefined)


class ResolvedAssertion(BaseModel):
    id: str
    type: str
    description: str = ""
    params: dict = Field(default_factory=dict)


class ResolvedTask(BaseModel):
    task_id: str
    title: str
    spec_text: str
    variables: dict
    assertions: list[ResolvedAssertion]


def _render_scalar(val, context: dict):
    if isinstance(val, str) and "{{" in val:
        rendered = _env.from_string(val).render(**context)
        try:
            f = float(rendered)
            return int(f) if f.is_integer() and "." not in rendered else f
        except ValueError:
            return rendered
    return val


def _resolve_value(val, context: dict):
    if isinstance(val, dict):
        return {k: _resolve_value(v, context) for k, v in val.items()}
    if isinstance(val, list):
        return [_resolve_value(v, context) for v in val]
    if isinstance(val, BaseModel):
        return _resolve_value(val.model_dump(), context)
    return _render_scalar(val, context)


def resolve_task(task: TaskSpec, variables: dict | None = None) -> ResolvedTask:
    """Resolve `task` against `variables` (defaults to each variable's declared default)."""
    context = variables if variables is not None else {
        name: v.default for name, v in task.variables.items()
    }

    spec_text = _env.from_string(task.description_template).render(**context)

    resolved_assertions = []
    for a in task.assertions:
        params = _resolve_value(a.params, context)
        description = _env.from_string(a.description).render(**context) if a.description else ""
        resolved_assertions.append(
            ResolvedAssertion(id=a.id, type=a.type, description=description, params=params)
        )

    return ResolvedTask(
        task_id=task.task_id,
        title=task.title,
        spec_text=spec_text,
        variables=context,
        assertions=resolved_assertions,
    )
