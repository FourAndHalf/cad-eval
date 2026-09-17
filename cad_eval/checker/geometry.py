"""Volume and bounding-box checks."""
from __future__ import annotations

import cadquery as cq

from cad_eval.report.models import AssertionResult
from cad_eval.task.resolve import ResolvedAssertion


def check_volume(shape: cq.Shape, assertion: ResolvedAssertion) -> AssertionResult:
    p = assertion.params
    expected = float(p["expected"])
    tolerance_pct = float(p["tolerance_pct"])
    actual_volume = shape.Volume()

    if expected == 0:
        pct_err = float("inf") if actual_volume else 0.0
    else:
        pct_err = abs(actual_volume - expected) / abs(expected) * 100.0

    status = "pass" if pct_err <= tolerance_pct else "fail"
    return AssertionResult(
        id=assertion.id, type=assertion.type, status=status,
        expected={"volume_mm3": expected, "tolerance_pct": tolerance_pct},
        actual={"volume_mm3": actual_volume, "pct_error": pct_err},
        message="ok" if status == "pass" else f"volume off by {pct_err:.2f}% (tolerance {tolerance_pct}%)",
    )


def check_bounding_box(shape: cq.Shape, assertion: ResolvedAssertion) -> AssertionResult:
    p = assertion.params
    expected = p["expected"]
    tolerance = float(p["tolerance"])
    bb = shape.BoundingBox()
    actual = {"x": bb.xlen, "y": bb.ylen, "z": bb.zlen}

    errors = {}
    for axis in ("x", "y", "z"):
        exp_val = float(expected[axis])
        diff = abs(actual[axis] - exp_val)
        if diff > tolerance:
            errors[axis] = {"expected": exp_val, "actual": actual[axis], "diff": diff}

    status = "pass" if not errors else "fail"
    return AssertionResult(
        id=assertion.id, type=assertion.type, status=status,
        expected={k: float(v) for k, v in expected.items()} | {"tolerance": tolerance},
        actual=actual,
        message="ok" if status == "pass" else f"axis mismatch: {errors}",
    )
