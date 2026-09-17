from cad_eval.checker.wall_thickness import check_min_wall_thickness
from cad_eval.checker.step_io import load_step
from cad_eval.task.resolve import ResolvedAssertion


def _assertion(min_thickness: float) -> ResolvedAssertion:
    return ResolvedAssertion(
        id="min_wall", type="min_wall_thickness",
        params={"min_thickness": min_thickness, "sample_count": 2000},
    )


def test_thin_wall_box_fails_at_2mm_requirement(fixtures_dir):
    shape = load_step(fixtures_dir / "thin_wall_box.step")
    result = check_min_wall_thickness(shape, _assertion(2.0))
    assert result.status == "fail"
    assert result.actual["approx_min_thickness"] < 1.0


def test_healthy_wall_box_passes_at_2mm_requirement(fixtures_dir):
    shape = load_step(fixtures_dir / "healthy_wall_box.step")
    result = check_min_wall_thickness(shape, _assertion(2.0))
    assert result.status == "pass"
    assert 2.5 < result.actual["approx_min_thickness"] <= 3.01
