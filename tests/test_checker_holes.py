from cad_eval.checker.evaluate import evaluate
from cad_eval.task.loader import load_task
from cad_eval.task.resolve import resolve_task


def test_l_bracket_hole_pattern_passes(fixtures_dir, tasks_dir):
    task = load_task(tasks_dir / "l_bracket_v1.yaml")
    resolved = resolve_task(task)
    result = evaluate(resolved, fixtures_dir / "valid_l_bracket.step")
    by_id = {a.id: a for a in result.assertions}
    assert by_id["hole_pattern"].status == "pass", by_id["hole_pattern"].message
    assert by_id["hole_pattern"].actual["matched_count"] == 2


def test_flange_bore_and_bolt_circle_pass(fixtures_dir, tasks_dir):
    task = load_task(tasks_dir / "bolt_circle_flange_v1.yaml")
    resolved = resolve_task(task)
    result = evaluate(resolved, fixtures_dir / "bolt_circle_flange_valid.step")
    by_id = {a.id: a for a in result.assertions}
    assert by_id["bore"].status == "pass", by_id["bore"].message
    assert by_id["bolt_circle"].status == "pass", by_id["bolt_circle"].message
    assert abs(by_id["bolt_circle"].actual["pcd"] - 50.0) < 0.2
    assert result.overall_status == "pass"


def test_flange_wrong_hole_count_fails(fixtures_dir, tasks_dir):
    task = load_task(tasks_dir / "bolt_circle_flange_v1.yaml")
    resolved = resolve_task(task)
    result = evaluate(resolved, fixtures_dir / "wrong_hole_count_flange.step")
    by_id = {a.id: a for a in result.assertions}
    assert by_id["bolt_circle"].status == "fail"
    assert by_id["bolt_circle"].actual["matched_count"] == 6
    assert "dimensional" in result.failure_categories
