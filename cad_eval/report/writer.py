"""Write a RunResult to results.json and a human-readable report.html."""
from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from cad_eval.report.models import RunResult

_TEMPLATES_DIR = Path(__file__).parent / "templates"


def _pass_rate(results) -> float | None:
    if not results:
        return None
    return sum(1 for r in results if r.overall_status == "pass") / len(results) * 100.0


def compute_summary(run: RunResult) -> dict:
    base = [t for t in run.tasks if t.variant == "base"]
    perturbations = [t for t in run.tasks if t.variant == "perturbation"]
    return {
        "overall_pass_rate": _pass_rate(run.tasks),
        "base_pass_rate": _pass_rate(base),
        "perturbation_pass_rate": _pass_rate(perturbations),
        "total_tasks": len(run.tasks),
        "base_count": len(base),
        "perturbation_count": len(perturbations),
        "intent_regeneration_failures": sum(
            1 for t in perturbations if "intent_regeneration" in t.failure_categories
        ),
    }


def write_run(run: RunResult, out_dir: str | Path) -> dict[str, Path]:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    json_path = out_dir / "results.json"
    json_path.write_text(run.model_dump_json(indent=2))

    env = Environment(loader=FileSystemLoader(str(_TEMPLATES_DIR)), autoescape=select_autoescape())
    template = env.get_template("summary.html.j2")
    html = template.render(run=run, summary=compute_summary(run))
    html_path = out_dir / "report.html"
    html_path.write_text(html)

    return {"json": json_path, "html": html_path}
