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
