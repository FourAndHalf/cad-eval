from cad_eval.checker.evaluate import evaluate
from cad_eval.task.loader import load_task
from cad_eval.task.resolve import resolve_task


def test_enclosure_lid_full_evaluation_passes(fixtures_dir, tasks_dir):
    task = load_task(tasks_dir / "enclosure_lid_v1.yaml")
    resolved = resolve_task(task)
    result = evaluate(resolved, fixtures_dir / "enclosure_lid_valid.step")
    failing = [a for a in result.assertions if a.status != "pass"]
    assert not failing, failing
    assert result.overall_status == "pass"


def test_bushing_spacer_full_evaluation_passes(fixtures_dir, tasks_dir):
    task = load_task(tasks_dir / "bushing_spacer_v1.yaml")
    resolved = resolve_task(task)
    result = evaluate(resolved, fixtures_dir / "bushing_spacer_valid.step")
    failing = [a for a in result.assertions if a.status != "pass"]
    assert not failing, failing
    assert result.overall_status == "pass"
