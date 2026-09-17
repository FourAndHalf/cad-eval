"""Manifold/solid-count topology checks."""
from __future__ import annotations

import cadquery as cq

from cad_eval.report.models import AssertionResult
from cad_eval.task.resolve import ResolvedAssertion


def check_manifold_solid(shape: cq.Shape, assertion: ResolvedAssertion) -> AssertionResult:
    p = assertion.params
    min_count = p.get("min_solid_count", 1)
    max_count = p.get("max_solid_count", 1)
    solids = shape.Solids()
    count = len(solids)
    valid = shape.isValid() if count > 0 else False

    expected = {"min_solid_count": min_count, "max_solid_count": max_count}
    actual = {"solid_count": count, "isValid": valid}

    if count < min_count:
        return AssertionResult(
            id=assertion.id, type=assertion.type, status="fail",
            expected=expected, actual=actual,
            message=f"expected >= {min_count} solid(s), found {count} (open shell or empty geometry)",
        )
    if count > max_count:
        return AssertionResult(
            id=assertion.id, type=assertion.type, status="fail",
            expected=expected, actual=actual,
            message=f"expected <= {max_count} solid(s), found {count} (disjoint bodies)",
        )
    if not valid:
        return AssertionResult(
            id=assertion.id, type=assertion.type, status="fail",
            expected=expected, actual=actual,
            message="solid failed OCC topological validity check (self-intersection or non-manifold geometry)",
        )
    return AssertionResult(
        id=assertion.id, type=assertion.type, status="pass",
        expected=expected, actual=actual, message="ok",
    )
