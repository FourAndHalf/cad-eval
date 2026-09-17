from cad_eval.checker.evaluate import evaluate
from cad_eval.task.loader import load_task
from cad_eval.task.resolve import resolve_task


def test_shaft_keyway_full_evaluation_passes(fixtures_dir, tasks_dir):
    task = load_task(tasks_dir / "shaft_keyway_v1.yaml")
    resolved = resolve_task(task)
    result = evaluate(resolved, fixtures_dir / "shaft_keyway_valid.step")
    failing = [a for a in result.assertions if a.status != "pass"]
    assert not failing, failing
    assert result.overall_status == "pass"

    keyway = next(a for a in result.assertions if a.id == "keyway")
    assert abs(keyway.actual["width"] - 6.0) < 0.01
    assert abs(keyway.actual["depth"] - 3.0) < 0.01
    assert abs(keyway.actual["length"] - 30.0) < 0.01
    assert abs(keyway.actual["position_from_nearer_end"] - 10.0) < 0.01


def test_shaft_keyway_wrong_width_fails(fixtures_dir, tasks_dir):
    task = load_task(tasks_dir / "shaft_keyway_v1.yaml")
    resolved = resolve_task(task)
    result = evaluate(resolved, fixtures_dir / "shaft_keyway_wrong_width.step")
    keyway = next(a for a in result.assertions if a.id == "keyway")
    assert keyway.status == "fail"
    assert abs(keyway.actual["width"] - 9.0) < 0.01
    assert result.overall_status == "fail"
