from cad_eval.task.loader import load_task
from cad_eval.task.perturb import generate_perturbations


def test_l_bracket_perturbations_cover_all_declared_deltas(tasks_dir):
    task = load_task(tasks_dir / "l_bracket_v1.yaml")
    perturbations = generate_perturbations(task)
    total_deltas = sum(len(p.deltas) for p in task.parametric.perturbable)
    assert len(perturbations) == total_deltas


def test_hole_count_set_delta_rerenders_spec_and_assertions(tasks_dir):
    task = load_task(tasks_dir / "l_bracket_v1.yaml")
    perturbations = generate_perturbations(task)
    set_4 = next(p for p in perturbations if p.perturbed_variable == "hole_count" and p.delta_description.endswith("4"))

    assert "4 through-holes" in set_4.resolved.spec_text
    hole_assertion = next(a for a in set_4.resolved.assertions if a.id == "hole_pattern")
    assert hole_assertion.params["expected_count"] == 4

    # other variables (e.g. vertical_length) should remain at their defaults
    assert set_4.resolved.variables["vertical_length"] == 80.0


def test_volume_expression_reevaluates_for_perturbed_variable(tasks_dir):
    task = load_task(tasks_dir / "l_bracket_v1.yaml")
    perturbations = generate_perturbations(task)
    scaled_length = next(p for p in perturbations if p.perturbed_variable == "vertical_length" and p.delta_description.endswith("100"))

    volume_assertion = next(a for a in scaled_length.resolved.assertions if a.id == "volume_check")
    expected_volume = volume_assertion.params["expected"]

    # hand-computed expected volume at vertical_length=100 (80*1.25), all else default
    vertical_length, horizontal_length, leg_width, thickness = 100.0, 60.0, 40.0, 5.0
    hole_count, hole_diameter = 2, 6.5
    hand_computed = (
        (vertical_length * leg_width + horizontal_length * leg_width - leg_width * leg_width) * thickness
        - hole_count * 3.14159265 * (hole_diameter / 2) ** 2 * thickness
    )
    assert abs(expected_volume - hand_computed) < 1e-3


def test_perturbed_variable_does_not_mutate_base_task_defaults(tasks_dir):
    task = load_task(tasks_dir / "l_bracket_v1.yaml")
    generate_perturbations(task)
    assert task.variables["hole_count"].default == 2
