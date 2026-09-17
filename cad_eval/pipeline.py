"""Top-level orchestration: task -> agent -> STEP -> checker -> TaskResult(s).

Runs each task's base spec plus every declared perturbation through the
same agent, then tags a perturbation `intent_regeneration` when its base
task passed but the perturbation didn't -- the headline signal the whole
harness exists to produce.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path

from cad_eval.agents.base import Agent, AgentResult
from cad_eval.checker.evaluate import evaluate
from cad_eval.report.models import RunResult, TaskResult
from cad_eval.task.perturb import generate_perturbations
from cad_eval.task.resolve import ResolvedTask, resolve_task
from cad_eval.task.schema import TaskSpec


def _task_result_for(
    resolved: ResolvedTask,
    agent_result: AgentResult,
    variant: str,
    perturbed_variable: str | None,
    delta_description: str | None,
) -> TaskResult:
    if agent_result.status != "ok":
        return TaskResult(
            task_id=resolved.task_id,
            variant=variant,
            perturbed_variable=perturbed_variable,
            delta_description=delta_description,
            agent_status=agent_result.status,
            overall_status="agent_failure",
            failure_categories=["agent_failure"],
            step_path=agent_result.step_path,
            agent_stdout_tail=agent_result.stdout_tail,
            agent_stderr_tail=agent_result.stderr_tail,
            duration_sec=agent_result.duration_sec,
        )

    result = evaluate(resolved, agent_result.step_path)
    result.variant = variant
    result.perturbed_variable = perturbed_variable
    result.delta_description = delta_description
    result.agent_status = "ok"
    result.agent_stdout_tail = agent_result.stdout_tail
    result.agent_stderr_tail = agent_result.stderr_tail
    result.duration_sec = agent_result.duration_sec
    return result


def run_task(task: TaskSpec, agent: Agent, run_dir: Path) -> list[TaskResult]:
    """Run `task`'s base spec and every declared perturbation through `agent`."""
    task_dir = run_dir / task.task_id
    results: list[TaskResult] = []

    resolved_base = resolve_task(task)
    base_agent_result = agent.run(resolved_base.spec_text, task_dir / "base")
    base_result = _task_result_for(resolved_base, base_agent_result, "base", None, None)
    results.append(base_result)

    for i, perturbation in enumerate(generate_perturbations(task)):
        workdir = task_dir / f"perturb_{i}_{perturbation.perturbed_variable}"
        agent_result = agent.run(perturbation.resolved.spec_text, workdir)
        results.append(
            _task_result_for(
                perturbation.resolved, agent_result, "perturbation",
                perturbation.perturbed_variable, perturbation.delta_description,
            )
        )

    if base_result.overall_status == "pass":
        for r in results[1:]:
            if r.overall_status != "pass" and "intent_regeneration" not in r.failure_categories:
                r.failure_categories = [*r.failure_categories, "intent_regeneration"]

    return results


def run_all(tasks: list[TaskSpec], agent: Agent, run_dir: str | Path) -> RunResult:
    run_dir = Path(run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)

    all_results: list[TaskResult] = []
    for task in tasks:
        all_results.extend(run_task(task, agent, run_dir))

    return RunResult(
        run_id=uuid.uuid4().hex[:12],
        timestamp=datetime.now(timezone.utc).isoformat(),
        agent_name=getattr(agent, "name", agent.__class__.__name__),
        model_id=getattr(agent, "model_id", None),
        tasks=all_results,
    )
