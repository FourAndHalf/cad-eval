"""Load and validate a task YAML file into a TaskSpec."""
from __future__ import annotations

from pathlib import Path

import yaml

from cad_eval.task.schema import TaskSpec


def load_task(path: str | Path) -> TaskSpec:
    path = Path(path)
    raw = yaml.safe_load(path.read_text())
    return TaskSpec.model_validate(raw)


def load_all_tasks(tasks_dir: str | Path) -> list[TaskSpec]:
    tasks_dir = Path(tasks_dir)
    return [load_task(p) for p in sorted(tasks_dir.glob("*.yaml"))]
