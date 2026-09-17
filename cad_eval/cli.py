"""cad-eval CLI."""
from __future__ import annotations

import json
from pathlib import Path

import click

from cad_eval.task.loader import load_task
from cad_eval.task.perturb import generate_perturbations
from cad_eval.task.resolve import resolve_task


@click.group()
def main():
    """Design-intent eval harness for CAD agents."""


@main.command()
@click.option("--task", "task_path", required=True, type=click.Path(exists=True), help="Task YAML file")
def perturb(task_path):
    """Print the re-rendered spec text and resolved assertions for every declared perturbation, without running an agent."""
    task = load_task(task_path)
    click.echo(f"=== base: {task.task_id} ===")
    resolved_base = resolve_task(task)
    click.echo(resolved_base.spec_text.strip())
    click.echo()

    for p in generate_perturbations(task):
        click.echo(f"--- perturbation: {p.delta_description} ---")
        click.echo(p.resolved.spec_text.strip())
        click.echo(json.dumps([a.model_dump() for a in p.resolved.assertions], indent=2))
        click.echo()


@main.command()
@click.option("--task", "task_path", type=click.Path(exists=True), help="Single task YAML file")
@click.option("--all", "run_all_flag", is_flag=True, help="Run every task in tasks/")
@click.option("--tasks-dir", default="tasks", type=click.Path(exists=True), help="Directory of task YAML files (used with --all)")
@click.option("--out", "out_dir", default=None, help="Output directory (default: runs/<timestamp>)")
def run(task_path, run_all_flag, tasks_dir, out_dir):
    """Run the reference agent against one task or all tasks, checking base + every perturbation, and write a report."""
    import datetime

    from cad_eval.agents.reference_llm_agent import ReferenceLLMAgent
    from cad_eval.pipeline import run_all
    from cad_eval.report.writer import write_run
    from cad_eval.task.loader import load_all_tasks, load_task

    if not task_path and not run_all_flag:
        raise click.UsageError("pass --task <file> or --all")

    tasks = load_all_tasks(tasks_dir) if run_all_flag else [load_task(task_path)]
    out_dir = out_dir or f"runs/{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}"

    agent = ReferenceLLMAgent()
    result = run_all(tasks, agent, out_dir)
    paths = write_run(result, out_dir)

    click.echo(f"run {result.run_id}: {sum(1 for t in result.tasks if t.overall_status == 'pass')}/{len(result.tasks)} passed")
    click.echo(f"json:  {paths['json']}")
    click.echo(f"html:  {paths['html']}")


@main.group("report")
def report_group():
    """Report utilities."""


@report_group.command("diff")
@click.argument("run_a_path", type=click.Path(exists=True))
@click.argument("run_b_path", type=click.Path(exists=True))
@click.option("--out", "out_path", default=None, help="Write an HTML diff report to this path")
def report_diff(run_a_path, run_b_path, out_path):
    """Diff two results.json runs and print a pass/fail transition table."""
    from cad_eval.report.diff import diff_runs, load_run

    diff = diff_runs(load_run(run_a_path), load_run(run_b_path))
    click.echo(f"{diff.run_a_id} -> {diff.run_b_id}")
    click.echo(f"pass rate: {diff.pass_rate_a:.1f}% -> {diff.pass_rate_b:.1f}%"
               if diff.pass_rate_a is not None and diff.pass_rate_b is not None else "pass rate: n/a")
    for row in diff.rows:
        marker = {"regression": "REGRESSION", "improvement": "improved", "added": "added", "removed": "removed"}.get(row.transition, "")
        click.echo(f"  [{row.transition:>15}] {marker:>10} {row.key}  ({row.status_a} -> {row.status_b})")

    if out_path:
        Path(out_path).write_text(
            "<pre>" + "\n".join(
                f"{r.transition:>15}  {r.key}  ({r.status_a} -> {r.status_b})" for r in diff.rows
            ) + "</pre>"
        )
        click.echo(f"written: {out_path}")


@main.command()
@click.option("--task", "task_path", required=True, type=click.Path(exists=True), help="Task YAML file")
@click.option("--step", "step_path", required=True, type=click.Path(exists=True), help="STEP file to check")
def check(task_path, step_path):
    """Check a STEP file against a task's assertions (no agent invoked) --
    the entrypoint any agent, including a future non-LLM one, can drive
    directly against the kernel-agnostic checker."""
    from cad_eval.checker.evaluate import evaluate

    task = load_task(task_path)
    resolved = resolve_task(task)
    result = evaluate(resolved, step_path)
    click.echo(result.model_dump_json(indent=2))
    raise SystemExit(0 if result.overall_status == "pass" else 1)


if __name__ == "__main__":
    main()
