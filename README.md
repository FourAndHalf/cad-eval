# cad-eval

A design-intent eval harness for CAD-generating agents (LLMs writing
parametric CAD code, or a kernel-backed agent). Instead of comparing
output to a reference mesh, each task carries machine-checkable
engineering assertions -- hole tolerances, wall thickness, manifold
topology, volume -- checked against a STEP file with CadQuery/OpenCascade
as the reference evaluator.

The differentiating idea: after an agent builds a part, the harness
**perturbs a driving dimension in the task's natural-language spec**
(hole count 4->6, length +20%) and re-runs the *same agent* end-to-end,
then re-checks the new output against a correspondingly-adjusted assertion
set. This distinguishes an agent that understood the part's parametric
design intent from one that sculpted a static lookalike shape.

The harness only ever touches STEP files at its boundary -- it doesn't
care what produced them. Today that's an LLM writing CadQuery code
(the bundled reference agent); it would work unmodified against any other
agent, including one backed by a different CAD kernel.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

`cadquery` (and its `cadquery-ocp` / OpenCascade dependency) ship prebuilt
PyPI wheels for Linux/macOS/Windows on Python 3.11+, so a plain `pip
install` works without conda. If wheel resolution fails on an unusual
platform (e.g. musl/Alpine), fall back to:
`conda create -n cadeval python=3.12 -c conda-forge cadquery`.

To run the reference LLM agent, set an API key:

```bash
cp .env.example .env   # then edit .env, or export GEMINI_API_KEY directly
```

## Quickstart

```bash
# Check a STEP file against a task's assertions, no agent involved --
# this is the kernel-agnostic entrypoint any agent (including a future
# non-LLM one) would drive directly.
cad-eval check --task tasks/l_bracket_v1.yaml --step tests/fixtures/valid_l_bracket.step

# See exactly what a perturbation does to the spec text and assertions,
# without running an agent.
cad-eval perturb --task tasks/l_bracket_v1.yaml

# Run the reference agent (needs GEMINI_API_KEY) against every task,
# base spec + every declared perturbation, and write a report.
cad-eval run --all
# -> runs/<timestamp>/results.json, runs/<timestamp>/report.html

# Compare two runs (e.g. before/after a prompt change) and see exactly
# which tasks regressed, improved, or held.
cad-eval report diff runs/<run_a>/results.json runs/<run_b>/results.json
```

## Layout

```
cad_eval/
  task/       task YAML schema, loader, Jinja2 resolver, perturbation engine
  checker/    STEP-based assertion checkers (topology, geometry, holes, wall thickness, keyway)
  agents/     the Agent protocol + a reference Gemini-backed CadQuery agent, sandboxed
  report/     result models, JSON + HTML report writer, run-to-run diff
  pipeline.py orchestrates task -> agent -> STEP -> checker -> report
  cli.py
tasks/        5 task YAMLs (v1); SCHEMA.md documents the assertion DSL
tests/        checker unit tests against hand-built fixture STEP files
              (ground truth is never trusted from LLM output)
```

## Task set (v1)

L-bracket (mounting holes), bolt-circle flange (PCD + concentric bore),
shaft with keyway, rectangular enclosure lid (corner holes + wall
thickness), and a cylindrical bushing/spacer (through-bore). v1
deliberately stayed small (5 tasks) to get the full pipeline -- checker,
perturbation engine, reference agent, report/diff -- working end-to-end
and well-tested first. Every task added past this point is a YAML file
following `tasks/SCHEMA.md`'s pattern, not new plumbing; growing toward
the original 30-50 target is straightforward from here.

## Known limitations (scoped deliberately, not accidentally)

- **`min_wall_thickness` is approximate.** It ray-casts inward from
  sampled mesh points along local surface normals; it can miss a wall
  thinner than the mesh sampling density, and underestimates true minimum
  thickness at two walls meeting at a sharp non-parallel angle. See the
  docstring in `checker/wall_thickness.py`.
- **Perturbations are single-variable only** (not combinatorial), so a
  failure can be attributed to one specific change. Multi-variable
  perturbation is a natural v2 extension.
- **No shared STEP coordinate convention is assumed.** PCD/position
  checks recenter on the computed hole-pattern centroid; keyway position
  is measured from the nearer shaft end. See `tasks/SCHEMA.md`.
- **The agent sandbox is a subprocess with timeout + resource limits, not
  a container.** No network isolation. Real isolation (e.g. a
  network-disabled container) is the natural next step before running
  this against untrusted agents at scale.
- **`keyway_slot` only handles a simple 3-face pocket** (flat floor + 2
  flat side walls), not a rounded-end endmill slot.
- **No live end-to-end run against the real Gemini API happened in this
  environment** as of the last check-in. The agent's code-generation,
  sandboxing, and STEP-export path are covered by unit tests that mock
  the LLM call and by a hand-written stand-in response that runs for
  real through the sandbox; the actual model call is standard `google-genai`
  SDK usage and worth a live smoke test with `GEMINI_API_KEY` set.

## Why this design (context for reviewers)

The checker's only contract with an agent is "produce a STEP file for
this spec" -- so swapping the reference LLM agent for a different agent,
including one backed by a different CAD kernel, requires no changes to
the checker, the assertion DSL, or the perturbation engine. The
assertion DSL treats numeric fields as Jinja2 expressions over named
variables specifically so that perturbing a variable and re-rendering
auto-adjusts every assertion that depends on it, rather than requiring a
hand-duplicated assertion block per perturbation -- that mechanism is
what makes the parametric-robustness signal (base pass rate vs.
perturbation pass rate, and the `intent_regeneration` failure category)
cheap to compute across an arbitrarily large task set.
