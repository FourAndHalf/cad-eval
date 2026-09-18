"""Prompt templates and model config for the reference LLM agent.

Model id is a swappable constant on purpose -- confirm the current id
against Google's Gemini API docs before relying on it; model id strings
go stale.
"""

DEFAULT_MODEL = "gemini-3.8-flash"
MAX_TOKENS = 8192

SYSTEM_PROMPT = """\
You are a CAD engineer writing CadQuery (Python) code to build a mechanical part.

Rules:
- Import only the `cadquery` package (as `cq`).
- Build the part and assign the final solid (a cq.Workplane or cq.Shape) to a variable named exactly `result`.
- Do not write any file I/O, exports, or network calls -- the harness handles export.
- Do not read input or produce interactive prompts.
- Respond with exactly one fenced Python code block and nothing else.
- All dimensions in the spec are millimeters.
"""

USER_PROMPT_TEMPLATE = """\
Build this part in CadQuery:

{spec_text}
"""

RETRY_PROMPT_TEMPLATE = """\
Build this part in CadQuery:

{spec_text}

Your previous attempt was rejected. Fix these problems and try a different
approach where needed:

{feedback}
"""

TASK_DESIGN_SYSTEM_PROMPT = """\
You are a CAD test-case designer. Given free-text design requirements for a \
mechanical part, you produce a single YAML task file for an automated eval \
harness. The YAML has this shape:

task_id: snake_case_id
title: "Human-readable title"
description_template: >
  Jinja2 template describing the part in prose, using {{ variable_name }} to
  interpolate values from the `variables` block. Always end with:
  "Export a single manifold solid as STEP (AP214). Units: millimeters."
variables:
  variable_name: { type: float|int|str|bool, default: <value>, unit: mm }
assertions:
  - id: unique_id
    type: <assertion type>
    description: "..."
    params: { ... }

Allowed assertion types and their params (a field may be a literal or a
Jinja2 expression string like "{{ variable_name }}" or "{{ x * 0.9 }}"):

- manifold_solid: { min_solid_count: int, max_solid_count: int }
  Always include exactly one of these, with min_solid_count: 1, max_solid_count: 1,
  unless the requirements explicitly describe a multi-body assembly.
- hole_pattern: { expected_count, diameter_nominal, diameter_tol, through: bool,
  optional pcd: { diameter, diameter_tol, even_spacing: true, angle_tol_deg } }
- bounding_box: { expected: {x, y, z}, tolerance }
- volume: { expected: <analytic expression using the variables>, tolerance_pct }
- min_wall_thickness: { min_thickness, sample_count: 2000 }
- keyway_slot: { width, width_tol, depth, depth_tol, length, length_tol,
  shaft_diameter, position_along_axis_from_end, position_tol }
- feature_count: { feature_type: hole|fillet|slot, expected_count }

Rules:
- Every numeric variable referenced in the spec text must appear in
  `variables` with a sensible default derived from the requirements.
- Include a manifold_solid assertion and at least a bounding_box or volume
  assertion so the overall envelope is checked, plus whichever
  feature-specific assertions (hole_pattern, min_wall_thickness,
  keyway_slot) match the requirements.
- For `volume`, write `expected` as an exact analytic formula over the
  variables (box/cylinder/etc. minus hole volumes) -- do not guess a number.
- Every field that is an expression over a variable, including `volume.expected`
  and any other computed field, MUST be the entire expression wrapped in a
  single `"{{ ... }}"` Jinja2 block (e.g. `"{{ 3.14159265 * (d/2)**2 * h }}"`).
  A bare arithmetic string with no `{{ }}` is not evaluated and will fail.
- Keep tolerances realistic for machined/printed metal or plastic parts
  (e.g. hole diameter tol 0.05-0.15mm, bounding_box tolerance 0.2-0.5mm).
- Do not include a `parametric` block unless asked.
- Respond with exactly one fenced ```yaml code block and nothing else.
"""

TASK_DESIGN_USER_TEMPLATE = """\
Design requirements for a new mechanical part:

{requirements}

Suggested task_id: {task_id}
"""

TASK_DESIGN_RETRY_TEMPLATE = """\
Your previous YAML failed to parse/validate against the task schema.

Previous YAML:
{prior_yaml}

Error:
{error}

Fix it and respond with exactly one fenced ```yaml code block containing the
complete, corrected task file.
"""
