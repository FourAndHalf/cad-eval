"""End-to-end pipeline + report + diff tests using a fake agent (no network,
no real LLM calls) that just copies a pre-built fixture STEP file into the
agent's workdir -- exercises the full task -> agent -> STEP -> checker ->
report wiring without depending on API access.
"""
import shutil
from pathlib import Path

from cad_eval.agents.base import AgentResult
from cad_eval.pipeline import run_all, run_task
from cad_eval.report.diff import diff_runs
from cad_eval.report.writer import write_run
from cad_eval.task.loader import load_task


class FixtureCopyAgent:
    """Always returns the same fixture STEP file, regardless of spec text --
    simulates an agent that ignores perturbations (fails to regenerate)."""

    name = "fixture_copy_agent"
    model_id = None

    def __init__(self, fixture_path: Path):
        self.fixture_path = fixture_path

    def run(self, spec_text: str, workdir: Path) -> AgentResult:
        workdir = Path(workdir)
        workdir.mkdir(parents=True, exist_ok=True)
        dest = workdir / "part.step"
        shutil.copy(self.fixture_path, dest)
        return AgentResult(status="ok", step_path=str(dest))


class AlwaysFailingAgent:
    name = "always_failing_agent"
    model_id = None

    def run(self, spec_text: str, workdir: Path) -> AgentResult:
        return AgentResult(status="execution_error", message="simulated failure")


def test_run_task_base_passes_and_perturbations_tagged_intent_regeneration(fixtures_dir, tasks_dir):
    task = load_task(tasks_dir / "l_bracket_v1.yaml")
    # the fixture always has hole_count=2; base task expects 2 (passes), every
    # perturbation changes what's expected so the static fixture fails them all
    agent = FixtureCopyAgent(fixtures_dir / "valid_l_bracket.step")

    results = run_task(task, agent, Path("/tmp/cad_eval_pipeline_test"))

    base = results[0]
    assert base.variant == "base"
    assert base.overall_status == "pass"

    perturbations = results[1:]
    assert len(perturbations) > 0
    for p in perturbations:
        assert p.variant == "perturbation"
        # not every perturbation necessarily fails (e.g. hole_diameter+1.5 might
        # still be within some other tolerance by coincidence), so just check
        # that failing ones are correctly tagged
        if p.overall_status != "pass":
            assert "intent_regeneration" in p.failure_categories


def test_run_task_agent_failure_produces_agent_failure_status(tasks_dir):
    task = load_task(tasks_dir / "l_bracket_v1.yaml")
    agent = AlwaysFailingAgent()
    results = run_task(task, agent, Path("/tmp/cad_eval_pipeline_test_fail"))
    assert all(r.overall_status == "agent_failure" for r in results)
    assert all(r.agent_status == "execution_error" for r in results)


def test_run_all_and_write_run_produces_json_and_html(fixtures_dir, tasks_dir, tmp_path):
    task = load_task(tasks_dir / "l_bracket_v1.yaml")
    agent = FixtureCopyAgent(fixtures_dir / "valid_l_bracket.step")
    run_result = run_all([task], agent, tmp_path / "run1")
    paths = write_run(run_result, tmp_path / "run1")
    assert paths["json"].exists()
    assert paths["html"].exists()
    assert "l_bracket_v1" in paths["html"].read_text()


def test_diff_detects_regression_between_two_runs(fixtures_dir, tasks_dir, tmp_path):
    task = load_task(tasks_dir / "l_bracket_v1.yaml")

    good_agent = FixtureCopyAgent(fixtures_dir / "valid_l_bracket.step")
    run_a = run_all([task], good_agent, tmp_path / "run_a")

    bad_agent = AlwaysFailingAgent()
    run_b = run_all([task], bad_agent, tmp_path / "run_b")

    diff = diff_runs(run_a, run_b)
    base_row = next(r for r in diff.rows if r.variant == "base")
    assert base_row.transition == "regression"
    assert diff.pass_rate_a is not None and diff.pass_rate_b == 0.0
