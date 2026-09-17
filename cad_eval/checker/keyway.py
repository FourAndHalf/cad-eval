"""Keyway/slot detection on a shaft.

A keyway is modeled as a rectangular pocket milled into a cylindrical
shaft: a floor face (planar, normal perpendicular to the shaft axis,
offset radially inward) flanked by two parallel side-wall faces (planar,
normals antiparallel to each other, also perpendicular to the axis).

Detection strategy, independent of which world axis happens to be "up"
(agent STEP exports won't share a coordinate convention):

1. Find the shaft's outer cylindrical surface: the largest-radius
   FORWARD-oriented (convex) cylindrical face -- same orientation signal
   used for hole detection in `holes.py`, but selecting the convex wall
   instead of excluding it.
2. Among planar faces whose normal is perpendicular to the shaft axis
   (this naturally excludes the shaft's own end caps and the keyway
   pocket's own axial end-walls, all of whose normals are parallel to
   the axis), find the pair whose normals are antiparallel -- these are
   the two side walls. The remaining face is the floor.
3. Width = perpendicular distance between the two side-wall planes.
   Depth = shaft radius minus the floor plane's perpendicular distance
   from the axis line. Length = the floor face's extent along the axis.
   Position = distance from the *nearer* shaft end to the keyway's start
   (checked against the nearer end rather than a fixed end, since a
   symmetric NL spec like "10mm from one end" doesn't pin which end the
   agent measures from -- a documented v1 simplification).

Only a single simple keyway (3 planar faces: 1 floor + 2 side walls) is
handled; a keyway with rounded ends (common for endmill-cut slots) would
add extra faces and is out of scope for v1.
"""
from __future__ import annotations

import cadquery as cq
import numpy as np
from OCP.BRepAdaptor import BRepAdaptor_Surface
from OCP.GeomAbs import GeomAbs_Cylinder, GeomAbs_Plane
from OCP.TopAbs import TopAbs_FORWARD, TopAbs_REVERSED

from cad_eval.report.models import AssertionResult
from cad_eval.task.resolve import ResolvedAssertion

_ANTIPARALLEL_TOL = 0.05  # dot product tolerance for "opposite normals"
_PERPENDICULAR_TOL = 0.05  # dot product tolerance for "normal perpendicular to axis"


def _find_shaft_axis(shape: cq.Shape) -> tuple[np.ndarray, np.ndarray, float] | None:
    """Returns (axis_location, axis_direction, radius) of the largest convex
    (FORWARD-oriented) cylindrical face, or None if no such face exists."""
    best = None
    for f in shape.Faces():
        adaptor = BRepAdaptor_Surface(f.wrapped)
        if adaptor.GetType() != GeomAbs_Cylinder:
            continue
        if f.wrapped.Orientation() != TopAbs_FORWARD:
            continue
        cyl = adaptor.Cylinder()
        radius = cyl.Radius()
        if best is None or radius > best[2]:
            ax = cyl.Axis()
            loc = np.array([ax.Location().X(), ax.Location().Y(), ax.Location().Z()])
            direction = np.array([ax.Direction().X(), ax.Direction().Y(), ax.Direction().Z()])
            direction = direction / np.linalg.norm(direction)
            best = (loc, direction, radius)
    return best


def _planar_faces_perpendicular_to_axis(shape: cq.Shape, axis_dir: np.ndarray) -> list[dict]:
    out = []
    for f in shape.Faces():
        adaptor = BRepAdaptor_Surface(f.wrapped)
        if adaptor.GetType() != GeomAbs_Plane:
            continue
        plane = adaptor.Plane()
        n = plane.Axis().Direction()
        normal = np.array([n.X(), n.Y(), n.Z()])
        normal = normal / np.linalg.norm(normal)
        if f.wrapped.Orientation() == TopAbs_REVERSED:
            normal = -normal  # analytic surface normal isn't orientation-adjusted
        if abs(float(np.dot(normal, axis_dir))) > _PERPENDICULAR_TOL:
            continue  # parallel to axis (end cap or pocket end-wall), not floor/side-wall
        cf = cq.Face(f.wrapped)
        center = cf.Center()
        bb = cf.BoundingBox()
        out.append({
            "normal": normal,
            "point": np.array([center.x, center.y, center.z]),
            "bbox": bb,
        })
    return out


def check_keyway_slot(shape: cq.Shape, assertion: ResolvedAssertion) -> AssertionResult:
    p = assertion.params
    expected_width = float(p["width"])
    expected_depth = float(p["depth"])
    expected_length = float(p["length"])
    expected_position = float(p["position_along_axis_from_end"])
    width_tol = float(p["width_tol"])
    depth_tol = float(p["depth_tol"])
    length_tol = float(p["length_tol"])
    position_tol = float(p.get("position_tol", 0.5))

    expected = {
        "width": expected_width, "depth": expected_depth, "length": expected_length,
        "position_from_nearer_end": expected_position,
    }

    axis = _find_shaft_axis(shape)
    if axis is None:
        return AssertionResult(
            id=assertion.id, type=assertion.type, status="fail", expected=expected,
            message="no convex cylindrical (shaft) surface found",
        )
    axis_loc, axis_dir, shaft_radius = axis

    candidates = _planar_faces_perpendicular_to_axis(shape, axis_dir)
    if len(candidates) < 3:
        return AssertionResult(
            id=assertion.id, type=assertion.type, status="fail", expected=expected,
            actual={"candidate_planar_faces": len(candidates)},
            message=f"expected a floor + 2 side-wall faces perpendicular to the shaft axis, found {len(candidates)}",
        )

    # find the pair of faces with antiparallel normals -> the two side walls
    side_wall_pair = None
    for i in range(len(candidates)):
        for j in range(i + 1, len(candidates)):
            dot = float(np.dot(candidates[i]["normal"], candidates[j]["normal"]))
            if dot < -(1 - _ANTIPARALLEL_TOL):
                side_wall_pair = (candidates[i], candidates[j])
                break
        if side_wall_pair:
            break

    if side_wall_pair is None:
        return AssertionResult(
            id=assertion.id, type=assertion.type, status="fail", expected=expected,
            actual={"candidate_planar_faces": len(candidates)},
            message="could not identify two parallel side-wall faces among candidate planar faces",
        )

    remaining = [c for c in candidates if c is not side_wall_pair[0] and c is not side_wall_pair[1]]
    floor = remaining[0] if remaining else None
    if floor is None:
        return AssertionResult(
            id=assertion.id, type=assertion.type, status="fail", expected=expected,
            message="found side walls but no distinct floor face",
        )

    sw1, sw2 = side_wall_pair
    actual_width = abs(float(np.dot(sw2["point"] - sw1["point"], sw1["normal"])))

    floor_dist_from_axis = abs(float(np.dot(floor["point"] - axis_loc, floor["normal"])))
    actual_depth = shaft_radius - floor_dist_from_axis

    corners = np.array([
        [floor["bbox"].xmin, floor["bbox"].ymin, floor["bbox"].zmin],
        [floor["bbox"].xmax, floor["bbox"].ymax, floor["bbox"].zmax],
    ])
    proj = corners @ axis_dir
    floor_a_min, floor_a_max = float(min(proj)), float(max(proj))
    actual_length = floor_a_max - floor_a_min

    shaft_bb = shape.BoundingBox()
    shaft_corners = np.array([
        [shaft_bb.xmin, shaft_bb.ymin, shaft_bb.zmin], [shaft_bb.xmax, shaft_bb.ymin, shaft_bb.zmin],
        [shaft_bb.xmin, shaft_bb.ymax, shaft_bb.zmin], [shaft_bb.xmin, shaft_bb.ymin, shaft_bb.zmax],
        [shaft_bb.xmax, shaft_bb.ymax, shaft_bb.zmax], [shaft_bb.xmax, shaft_bb.ymax, shaft_bb.zmin],
        [shaft_bb.xmax, shaft_bb.ymin, shaft_bb.zmax], [shaft_bb.xmin, shaft_bb.ymax, shaft_bb.zmax],
    ])
    shaft_proj = shaft_corners @ axis_dir
    shaft_a_min, shaft_a_max = float(shaft_proj.min()), float(shaft_proj.max())

    dist_from_start = floor_a_min - shaft_a_min
    dist_from_end = shaft_a_max - floor_a_max
    actual_position = min(dist_from_start, dist_from_end)

    actual = {
        "width": round(actual_width, 4), "depth": round(actual_depth, 4),
        "length": round(actual_length, 4), "position_from_nearer_end": round(actual_position, 4),
    }

    errors = []
    if abs(actual_width - expected_width) > width_tol:
        errors.append(f"width {actual_width:.3f} vs expected {expected_width}+/-{width_tol}")
    if abs(actual_depth - expected_depth) > depth_tol:
        errors.append(f"depth {actual_depth:.3f} vs expected {expected_depth}+/-{depth_tol}")
    if abs(actual_length - expected_length) > length_tol:
        errors.append(f"length {actual_length:.3f} vs expected {expected_length}+/-{length_tol}")
    if abs(actual_position - expected_position) > position_tol:
        errors.append(f"position {actual_position:.3f} vs expected {expected_position}+/-{position_tol}")

    if errors:
        return AssertionResult(
            id=assertion.id, type=assertion.type, status="fail",
            expected=expected, actual=actual, message="; ".join(errors),
        )
    return AssertionResult(
        id=assertion.id, type=assertion.type, status="pass", expected=expected, actual=actual, message="ok",
    )
