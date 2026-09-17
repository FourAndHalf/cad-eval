from cad_eval.checker.evaluate import evaluate
from cad_eval.task.loader import load_task
from cad_eval.task.resolve import resolve_task


def test_valid_l_bracket_passes_manifold_and_volume(fixtures_dir, tasks_dir):
    task = load_task(tasks_dir / "l_bracket_v1.yaml")
    resolved = resolve_task(task)
    result = evaluate(resolved, fixtures_dir / "valid_l_bracket.step")

    by_id = {a.id: a for a in result.assertions}
    assert by_id["is_manifold_solid"].status == "pass"
    assert by_id["bbox_overall"].status == "pass"
    assert by_id["volume_check"].status == "pass", by_id["volume_check"].message


def test_two_disjoint_solids_fails_manifold_check(fixtures_dir, tasks_dir):
    task = load_task(tasks_dir / "l_bracket_v1.yaml")
    resolved = resolve_task(task)
    result = evaluate(resolved, fixtures_dir / "two_disjoint_solids.step")

    by_id = {a.id: a for a in result.assertions}
    assert by_id["is_manifold_solid"].status == "fail"
    assert by_id["is_manifold_solid"].actual["solid_count"] == 2
    assert "topological" in result.failure_categories
    assert result.overall_status == "fail"


def test_open_shell_fails_manifold_check(fixtures_dir, tasks_dir):
    task = load_task(tasks_dir / "l_bracket_v1.yaml")
    resolved = resolve_task(task)
    result = evaluate(resolved, fixtures_dir / "open_shell.step")

    by_id = {a.id: a for a in result.assertions}
    assert by_id["is_manifold_solid"].status == "fail"
    assert by_id["is_manifold_solid"].actual["solid_count"] == 0
    assert result.overall_status == "fail"
