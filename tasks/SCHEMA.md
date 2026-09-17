# Task YAML schema

Each file in `tasks/` describes one mechanical part: a natural-language spec
template, typed variables, machine-checkable assertions, and which
variables are perturbable for the robustness tests. See `cad_eval/task/schema.py`
for the authoritative pydantic definitions.

## Top level

```yaml
task_id: my_part_v1
title: "Human-readable title"
description_template: >
  Jinja2 template. {{ variable_name }} interpolates a variable's current
  value (default, or overridden during a perturbation).
variables:
  variable_name: { type: float, default: 10.0, unit: mm }
assertions:
  - id: ...
    type: ...
    params: { ... }
parametric:
  perturbable:
    - variable: variable_name
      deltas:
        - { op: set, value: 20.0 }       # replace with a literal
        - { op: scale, factor: 1.25 }    # multiply the default
        - { op: add, value: 5.0 }        # add to the default
```

Any string field in an assertion's `params` may be a Jinja2 expression over
the task's variables (e.g. `"{{ hole_count }}"`, `"{{ thickness * 0.9 }}"`).
When a variable is perturbed, every assertion referencing it is
automatically re-resolved to the new concrete value -- no duplicated
per-perturbation assertion blocks need to be authored.

## Assertion types

| `type` | key params | checker module |
|---|---|---|
| `manifold_solid` | `min_solid_count`, `max_solid_count` | `checker/topology.py` |
| `hole_pattern` | `expected_count`, `diameter_nominal`, `diameter_tol`, `through`, optional nested `pcd` block | `checker/holes.py` |
| `bounding_box` | `expected: {x, y, z}`, `tolerance` | `checker/geometry.py` |
| `volume` | `expected` (expression), `tolerance_pct` | `checker/geometry.py` |
| `min_wall_thickness` | `min_thickness`, `sample_count` | `checker/wall_thickness.py` |
| `keyway_slot` | `width`, `depth`, `length`, `shaft_diameter`, `position_along_axis_from_end`, plus a `_tol` per field | `checker/keyway.py` |
| `feature_count` | `feature_type`, `expected_count` | reserved for future task types |

### `hole_pattern` with a bolt-circle (PCD)

```yaml
params:
  expected_count: "{{ hole_count }}"
  diameter_nominal: "{{ hole_diameter }}"
  diameter_tol: "{{ hole_diameter_tol }}"
  through: true
  pcd:
    diameter: "{{ pcd }}"
    diameter_tol: 0.15
    even_spacing: true
    angle_tol_deg: 1.0
```

## Important checker assumptions (worth knowing before authoring a task)

- **No shared coordinate convention.** Different agents' STEP exports won't
  share a world origin or axis convention. PCD/position checks recenter on
  the *computed centroid* of the matched hole pattern rather than an
  assumed world origin; keyway position is measured from the *nearer*
  shaft end rather than a fixed end for the same reason.
- **`min_wall_thickness` is approximate**, not a rigorous solve. See the
  docstring in `checker/wall_thickness.py` for exactly what it does and
  where it can be fooled (sampling density, acute-angle walls).
- **`through` for a hole** is approximated by comparing a cylindrical
  face's axial span to the solid's own bounding-box extent along that
  axis, not a full ray-cast. Correct for simple through-holes; could
  misclassify a hole that only passes through an internal rib.
- **`keyway_slot` only handles a simple 3-face pocket** (floor + 2 flat
  side walls). A keyway with rounded ends (common for endmill-cut slots)
  is out of scope for v1.
