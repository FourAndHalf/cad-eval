"""Hand-build ground-truth STEP fixtures with CadQuery so checker unit tests
have known-exact expected values (never trust LLM output as ground truth).

Run once: `python tests/fixtures/generate_fixtures.py`
"""
from pathlib import Path

import cadquery as cq

FIXTURES = Path(__file__).parent


def valid_l_bracket():
    """Matches tasks/l_bracket_v1.yaml defaults exactly: vertical_length=80,
    horizontal_length=60, leg_width=40, thickness=5, hole_count=2,
    hole_diameter=6.5, hole_edge_margin=15."""
    vertical_length, horizontal_length, leg_width, thickness = 80.0, 60.0, 40.0, 5.0
    pts = [
        (0, 0), (horizontal_length, 0), (horizontal_length, leg_width),
        (leg_width, leg_width), (leg_width, vertical_length), (0, vertical_length),
    ]
    profile = cq.Workplane("XY").polyline(pts).close()
    hole_x = leg_width / 2  # 20
    hole_ys = [15.0, vertical_length - 15.0]  # 15, 65 - edge margin from each end

    wp = profile.extrude(thickness)
    wp = wp.faces(">Z").workplane(centerOption="CenterOfBoundBox")
    # workplane center after CenterOfBoundBox is the bbox center: (horizontal_length/2, vertical_length/2)
    cx, cy = horizontal_length / 2, vertical_length / 2
    rel_points = [(hole_x - cx, y - cy) for y in hole_ys]
    wp = wp.pushPoints(rel_points).hole(6.5)
    cq.exporters.export(wp, str(FIXTURES / "valid_l_bracket.step"))


def two_disjoint_solids():
    w1 = cq.Workplane("XY").box(20, 20, 5)
    w2 = cq.Workplane("XY").center(100, 0).box(20, 20, 5)
    comp = cq.Compound.makeCompound([w1.val(), w2.val()])
    cq.exporters.export(comp, str(FIXTURES / "two_disjoint_solids.step"))


def open_shell():
    box = cq.Workplane("XY").box(20, 20, 5).val()
    faces = box.Faces()
    shell = cq.Shell.makeShell(faces[:-1])  # drop one face -> not closed -> 0 solids
    comp = cq.Compound.makeCompound([shell])
    cq.exporters.export(comp, str(FIXTURES / "open_shell.step"))


def thin_wall_box():
    """A hollow box with one wall intentionally thinner (0.5mm) than the rest (3mm)."""
    outer = cq.Workplane("XY").box(40, 40, 20)
    inner = cq.Workplane("XY").center(0.5, 0).box(40 - 2 * 3, 40 - 2 * 0.5, 20 - 2 * 3)
    hollow = outer.cut(inner)
    cq.exporters.export(hollow, str(FIXTURES / "thin_wall_box.step"))


def healthy_wall_box():
    """A hollow box with uniform 3mm walls."""
    outer = cq.Workplane("XY").box(40, 40, 20)
    inner = cq.Workplane("XY").box(40 - 2 * 3, 40 - 2 * 3, 20 - 2 * 3)
    hollow = outer.cut(inner)
    cq.exporters.export(hollow, str(FIXTURES / "healthy_wall_box.step"))


def bolt_circle_flange():
    """4 holes, 6.4mm dia, on 50mm PCD, matching tasks/bolt_circle_flange_v1.yaml defaults."""
    outer_diameter, thickness, bore_diameter = 100.0, 8.0, 30.0
    hole_count, hole_diameter, pcd = 4, 6.4, 50.0
    wp = (
        cq.Workplane("XY")
        .circle(outer_diameter / 2)
        .extrude(thickness)
        .faces(">Z")
        .workplane()
        .hole(bore_diameter)
        .faces(">Z")
        .workplane()
        .polarArray(pcd / 2, 0, 360, hole_count)
        .hole(hole_diameter)
    )
    cq.exporters.export(wp, str(FIXTURES / "bolt_circle_flange_valid.step"))


def wrong_hole_count_flange():
    outer_diameter, thickness, bore_diameter = 100.0, 8.0, 30.0
    hole_count, hole_diameter, pcd = 6, 6.4, 50.0  # 6 instead of expected 4
    wp = (
        cq.Workplane("XY")
        .circle(outer_diameter / 2)
        .extrude(thickness)
        .faces(">Z")
        .workplane()
        .hole(bore_diameter)
        .faces(">Z")
        .workplane()
        .polarArray(pcd / 2, 0, 360, hole_count)
        .hole(hole_diameter)
    )
    cq.exporters.export(wp, str(FIXTURES / "wrong_hole_count_flange.step"))


if __name__ == "__main__":
    valid_l_bracket()
    two_disjoint_solids()
    open_shell()
    thin_wall_box()
    healthy_wall_box()
    bolt_circle_flange()
    wrong_hole_count_flange()
    print("fixtures written to", FIXTURES)
