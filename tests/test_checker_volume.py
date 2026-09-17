from cad_eval.checker.evaluate import evaluate
from cad_eval.task.loader import load_task
from cad_eval.task.resolve import resolve_task


def test_l_bracket_full_evaluation_passes(fixtures_dir, tasks_dir):
    task = load_task(tasks_dir / "l_bracket_v1.yaml")
    resolved = resolve_task(task)
    result = evaluate(resolved, fixtures_dir / "valid_l_bracket.step")
    failing = [a for a in result.assertions if a.status != "pass"]
    assert not failing, failing
    assert result.overall_status == "pass"


def test_bolt_circle_flange_full_evaluation_passes(fixtures_dir, tasks_dir):
    task = load_task(tasks_dir / "bolt_circle_flange_v1.yaml")
    resolved = resolve_task(task)
    result = evaluate(resolved, fixtures_dir / "bolt_circle_flange_valid.step")
    failing = [a for a in result.assertions if a.status != "pass"]
    assert not failing, failing
    assert result.overall_status == "pass"
