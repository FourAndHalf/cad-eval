"""Hole-pattern detection: cylindrical-face grouping, through/blind
classification, and bolt-circle (PCD) extraction.

Approach, and its known limitations (documented rather than hidden):

- A "hole" is any cylindrical face whose OCC face orientation is REVERSED.
  In a solid, a face's analytic surface normal (for a cylinder, radially
  outward) is flipped by REVERSED orientation; physically this means
  material sits *outside* the cylinder and void *inside* it -- exactly
  what a drilled hole/bore looks like. A convex outer cylindrical wall
  (e.g. a flange's OD) has FORWARD orientation and is excluded. This is a
  reliable, cheap signal that avoids needing a full solid-angle or
  ray-casting classification.
- Different agents may model "the same" hole as one full-cylinder face or
  as several split faces (e.g. at a seam). Faces are grouped by axis line
  (canonicalized to the point on the line closest to the global origin,
  independent of the arbitrary point OCC reports) + radius, so split faces
  of one hole merge into a single detected hole.
- "Through" is approximated by comparing the cylindrical face's axial
  (V-parameter) span to the solid's own extent along that axis, rather
  than a full ray-cast through the solid. This is cheap and correct for
  simple through-holes; a hole passing through an internal rib (not just
  the outer wall) could be misclassified. Flagged as a v1 scoping choice.
- PCD/position checks recenter on the *computed centroid* of the matched
  hole group, not on an assumed world-origin/coordinate convention --
  different agents' STEP exports will not share an origin convention.
"""
from __future__ import annotations

import math

import cadquery as cq
import numpy as np
from OCP.BRepAdaptor import BRepAdaptor_Surface
from OCP.GeomAbs import GeomAbs_Cylinder
from OCP.TopAbs import TopAbs_REVERSED

from cad_eval.report.models import AssertionResult
from cad_eval.task.resolve import ResolvedAssertion

_RADIUS_GROUP_TOL = 0.05  # mm; merges split faces of the same physical hole
_AXIS_POS_GROUP_TOL = 0.5  # mm
_AXIS_ANGLE_GROUP_TOL_DEG = 2.0


def _canonical_axis_point(loc: np.ndarray, direction: np.ndarray) -> np.ndarray:
    """Point on the axis line closest to the global origin -- a
    representative point independent of where OCC happened to place `loc`."""
    t = float(np.dot(loc, direction))
    return loc - t * direction


def _find_cylindrical_hole_faces(shape: cq.Shape) -> list[dict]:
    out = []
    for f in shape.Faces():
        adaptor = BRepAdaptor_Surface(f.wrapped)
        if adaptor.GetType() != GeomAbs_Cylinder:
            continue
        if f.wrapped.Orientation() != TopAbs_REVERSED:
            continue  # convex outer wall, not a hole
        cyl = adaptor.Cylinder()
        ax = cyl.Axis()
        loc = np.array([ax.Location().X(), ax.Location().Y(), ax.Location().Z()])
        direction = np.array([ax.Direction().X(), ax.Direction().Y(), ax.Direction().Z()])
        direction = direction / np.linalg.norm(direction)
        vmin, vmax = adaptor.FirstVParameter(), adaptor.LastVParameter()
        out.append({
            "radius": cyl.Radius(),
            "loc": loc,
            "dir": direction,
            "canon": _canonical_axis_point(loc, direction),
            "vspan": abs(vmax - vmin),
        })
    return out


def _axes_match(g: dict, cf: dict) -> bool:
    # directions may point either way along the same line; compare via abs(dot)
    cos_angle = abs(float(np.dot(g["dir"], cf["dir"])))
    cos_angle = min(1.0, cos_angle)
    angle_deg = math.degrees(math.acos(cos_angle))
    if angle_deg > _AXIS_ANGLE_GROUP_TOL_DEG:
        return False
    pos_diff = np.linalg.norm(g["canon"] - cf["canon"])
    return pos_diff <= _AXIS_POS_GROUP_TOL


def _group_holes(cyl_faces: list[dict]) -> list[dict]:
    groups: list[dict] = []
    for cf in cyl_faces:
        match = None
        for g in groups:
            if abs(g["radius"] - cf["radius"]) <= _RADIUS_GROUP_TOL and _axes_match(g, cf):
                match = g
                break
        if match is not None:
            match["vspan"] = max(match["vspan"], cf["vspan"])
        else:
            groups.append({
                "radius": cf["radius"], "dir": cf["dir"], "canon": cf["canon"], "vspan": cf["vspan"],
            })
    return groups


def _axial_extent(shape: cq.Shape, direction: np.ndarray) -> float:
    """Solid's extent projected onto `direction`, used as the through-hole
    reference depth (approximate: uses the overall bounding box, not a
    per-hole local wall thickness)."""
    bb = shape.BoundingBox()
    corners = np.array([
        [bb.xmin, bb.ymin, bb.zmin], [bb.xmax, bb.ymin, bb.zmin],
        [bb.xmin, bb.ymax, bb.zmin], [bb.xmin, bb.ymin, bb.zmax],
        [bb.xmax, bb.ymax, bb.zmax], [bb.xmax, bb.ymax, bb.zmin],
        [bb.xmax, bb.ymin, bb.zmax], [bb.xmin, bb.ymax, bb.zmax],
    ])
    projections = corners @ direction
    return float(projections.max() - projections.min())


def _orthonormal_basis(direction: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    helper = np.array([1.0, 0.0, 0.0]) if abs(direction[0]) < 0.9 else np.array([0.0, 1.0, 0.0])
    u = np.cross(direction, helper)
    u = u / np.linalg.norm(u)
    v = np.cross(direction, u)
    return u, v


def check_hole_pattern(shape: cq.Shape, assertion: ResolvedAssertion) -> AssertionResult:
    p = assertion.params
    expected_count = int(p["expected_count"])
    diameter_nominal = float(p["diameter_nominal"])
    diameter_tol = float(p["diameter_tol"])
    through_required = bool(p.get("through", True))

    all_groups = _group_holes(_find_cylindrical_hole_faces(shape))
    matched = [g for g in all_groups if abs(g["radius"] * 2 - diameter_nominal) <= diameter_tol]
    count = len(matched)

    expected = {"expected_count": expected_count, "diameter_nominal": diameter_nominal, "diameter_tol": diameter_tol}
    actual = {"matched_count": count, "diameters": sorted(round(g["radius"] * 2, 3) for g in matched)}

    if count != expected_count:
        return AssertionResult(
            id=assertion.id, type=assertion.type, status="fail",
            expected=expected, actual=actual,
            message=f"expected {expected_count} hole(s) of diameter {diameter_nominal}+/-{diameter_tol}mm, found {count}",
        )

    if through_required:
        depth_ref = _axial_extent(shape, matched[0]["dir"]) if matched else 0.0
        not_through = [g for g in matched if g["vspan"] < depth_ref - 0.1]
        if not_through:
            actual["blind_hole_count"] = len(not_through)
            return AssertionResult(
                id=assertion.id, type=assertion.type, status="fail",
                expected=expected, actual=actual,
                message=f"{len(not_through)} of {count} matched hole(s) do not appear to pass fully through the part",
            )

    pcd_params = p.get("pcd")
    if pcd_params and matched:
        direction = matched[0]["dir"]
        u, v = _orthonormal_basis(direction)
        points_2d = np.array([[np.dot(g["canon"], u), np.dot(g["canon"], v)] for g in matched])
        centroid = points_2d.mean(axis=0)
        radii = np.linalg.norm(points_2d - centroid, axis=1)
        actual_pcd = float(2 * radii.mean())
        expected_pcd = float(pcd_params["diameter"])
        pcd_tol = float(pcd_params["diameter_tol"])
        actual["pcd"] = actual_pcd

        if abs(actual_pcd - expected_pcd) > pcd_tol:
            return AssertionResult(
                id=assertion.id, type=assertion.type, status="fail",
                expected=expected | {"pcd": expected_pcd, "pcd_tol": pcd_tol}, actual=actual,
                message=f"PCD {actual_pcd:.3f}mm outside expected {expected_pcd}+/-{pcd_tol}mm",
            )

        if pcd_params.get("even_spacing", True):
            angles = np.degrees(np.arctan2(points_2d[:, 1] - centroid[1], points_2d[:, 0] - centroid[0]))
            angles = np.sort(angles % 360)
            deltas = np.diff(np.concatenate([angles, [angles[0] + 360]]))
            expected_delta = 360.0 / count
            angle_tol = float(pcd_params.get("angle_tol_deg", 1.0))
            bad = [float(d) for d in deltas if abs(d - expected_delta) > angle_tol]
            actual["angular_deltas_deg"] = [round(float(d), 3) for d in deltas]
            if bad:
                return AssertionResult(
                    id=assertion.id, type=assertion.type, status="fail",
                    expected=expected | {"expected_angular_delta_deg": expected_delta}, actual=actual,
                    message=f"hole pattern not evenly spaced: deltas {actual['angular_deltas_deg']}deg, expected ~{expected_delta:.1f}deg",
                )

    return AssertionResult(
        id=assertion.id, type=assertion.type, status="pass", expected=expected, actual=actual, message="ok",
    )
