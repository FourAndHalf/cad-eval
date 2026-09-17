"""Dispatch each resolved assertion to its checker module and aggregate results."""
from __future__ import annotations

from pathlib import Path

from cad_eval.checker import geometry, topology
from cad_eval.checker.step_io import load_step
from cad_eval.report.models import AssertionResult, TaskResult
from cad_eval.task.resolve import ResolvedAssertion, ResolvedTask

try:
    from cad_eval.checker import holes as holes_mod
except ImportError:  # noqa: E722 - available once M2 lands
    holes_mod = None

try:
    from cad_eval.checker import wall_thickness as wall_mod
except ImportError:
    wall_mod = None

try:
    from cad_eval.checker import keyway as keyway_mod
except ImportError:
    keyway_mod = None


_DISPATCH = {
    "manifold_solid": topology.check_manifold_solid,
    "volume": geometry.check_volume,
    "bounding_box": geometry.check_bounding_box,
}
if holes_mod is not None:
    _DISPATCH["hole_pattern"] = holes_mod.check_hole_pattern
if wall_mod is not None:
    _DISPATCH["min_wall_thickness"] = wall_mod.check_min_wall_thickness
if keyway_mod is not None:
    _DISPATCH["keyway_slot"] = keyway_mod.check_keyway_slot

_CATEGORY_BY_TYPE = {
    "manifold_solid": "topological",
    "volume": "dimensional",
    "bounding_box": "dimensional",
    "hole_pattern": "dimensional",
    "min_wall_thickness": "dimensional",
    "keyway_slot": "dimensional",
    "feature_count": "dimensional",
}


def evaluate(resolved_task: ResolvedTask, step_path: str | Path) -> TaskResult:
    """Load `step_path` once and check it against every assertion in `resolved_task`."""
    step_path = Path(step_path)
    assertion_results: list[AssertionResult] = []
    failure_categories: set[str] = set()

    try:
        shape = load_step(step_path)
    except Exception as exc:  # noqa: BLE001 - any STEP-load failure fails every assertion
        for a in resolved_task.assertions:
            assertion_results.append(
                AssertionResult(
                    id=a.id, type=a.type, status="error",
                    message=f"could not load STEP file: {exc}",
                )
            )
        return TaskResult(
            task_id=resolved_task.task_id,
            overall_status="fail",
            failure_categories=["topological"],
            assertions=assertion_results,
            step_path=str(step_path),
        )

    for a in resolved_task.assertions:
        checker_fn = _DISPATCH.get(a.type)
        if checker_fn is None:
            assertion_results.append(
                AssertionResult(id=a.id, type=a.type, status="error", message=f"no checker implemented for type={a.type!r}")
            )
            continue
        try:
            result = checker_fn(shape, a)
        except Exception as exc:  # noqa: BLE001 - one bad assertion must not crash the task result
            result = AssertionResult(id=a.id, type=a.type, status="error", message=f"checker raised: {exc}")
        assertion_results.append(result)
        if result.status in ("fail", "error"):
            failure_categories.add(_CATEGORY_BY_TYPE.get(a.type, "dimensional"))

    overall_status = "pass" if all(r.status == "pass" for r in assertion_results) else "fail"

    return TaskResult(
        task_id=resolved_task.task_id,
        overall_status=overall_status,
        failure_categories=sorted(failure_categories),
        assertions=assertion_results,
        step_path=str(step_path),
    )
