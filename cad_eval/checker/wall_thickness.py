"""Approximate minimum-wall-thickness check.

Method: mesh the solid, and for every mesh-triangle centroid on the
boundary, cast a ray inward along the local face normal; the shortest
ray-hit distance across all sampled points is reported as the approximate
minimum wall thickness.

Known, deliberate limitations (documented rather than hidden -- true
minimum-wall-thickness is a much harder offset-surface-self-intersection
problem):

- Sampling density vs. accuracy tradeoff: a thin wall smaller than the
  mesh deflection can be missed if no triangle centroid lands near it.
- Measuring along the *local surface normal* underestimates true minimum
  thickness at two walls that face each other at a sharp non-parallel
  angle (the true shortest path between them is not axis-aligned with
  either normal).
- Doesn't reliably handle walls that face each other but aren't directly
  "across" via a straight normal ray (e.g. offset, non-parallel walls).

A cheap corroborating check worth adding later: attempt an inward shell
offset by the threshold itself (`shape.shell(-min_thickness)`) and treat
a self-intersection/failure as a pass/fail-at-threshold signal, which
catches some cases the sampling method misses.
"""
from __future__ import annotations

import cadquery as cq
import numpy as np
from OCP.BRep import BRep_Tool
from OCP.BRepMesh import BRepMesh_IncrementalMesh
from OCP.gp import gp_Dir, gp_Lin, gp_Pnt
from OCP.IntCurvesFace import IntCurvesFace_ShapeIntersector
from OCP.TopAbs import TopAbs_REVERSED
from OCP.TopLoc import TopLoc_Location

from cad_eval.report.models import AssertionResult
from cad_eval.task.resolve import ResolvedAssertion

_MESH_DEFLECTION = 0.3  # mm; triangulation chord tolerance
_RAY_NUDGE = 1e-3  # mm; offset the ray start off the surface to avoid self-hit
_RAY_MAX_DIST = 1e5  # mm


def _min_wall_thickness_sampled(shape: cq.Shape, sample_count: int) -> float:
    BRepMesh_IncrementalMesh(shape.wrapped, _MESH_DEFLECTION)

    intersector = IntCurvesFace_ShapeIntersector()
    intersector.Load(shape.wrapped, 1e-6)

    triangles: list[tuple[np.ndarray, np.ndarray, object]] = []  # (centroid, inward_normal, source_face)
    for f in shape.Faces():
        loc = TopLoc_Location()
        tri = BRep_Tool.Triangulation_s(f.wrapped, loc)
        if tri is None:
            continue
        trsf = loc.Transformation()
        reversed_face = f.wrapped.Orientation() == TopAbs_REVERSED
        for i in range(1, tri.NbTriangles() + 1):
            i1, i2, i3 = tri.Triangle(i).Get()
            p1 = tri.Node(i1).Transformed(trsf)
            p2 = tri.Node(i2).Transformed(trsf)
            p3 = tri.Node(i3).Transformed(trsf)
            a = np.array([p1.X(), p1.Y(), p1.Z()])
            b = np.array([p2.X(), p2.Y(), p2.Z()])
            c = np.array([p3.X(), p3.Y(), p3.Z()])
            normal = np.cross(b - a, c - a)
            norm = np.linalg.norm(normal)
            if norm < 1e-9:
                continue
            normal = normal / norm
            if reversed_face:
                normal = -normal
            centroid = (a + b + c) / 3.0
            triangles.append((centroid, -normal, f.wrapped))  # store inward-pointing normal

    if not triangles:
        return float("inf")

    # sample_count caps how many triangles we ray-cast, for cost control on dense meshes
    if len(triangles) > sample_count:
        idx = np.linspace(0, len(triangles) - 1, sample_count).astype(int)
        triangles = [triangles[i] for i in idx]

    min_dist = float("inf")
    for centroid, inward, source_face in triangles:
        start = centroid + inward * _RAY_NUDGE
        line = gp_Lin(gp_Pnt(*start), gp_Dir(*inward))
        intersector.Perform(line, 1e-6, _RAY_MAX_DIST)
        if not intersector.IsDone():
            continue
        intersector.SortResult()
        # Exclude hits back on the ray's own source face: on curved (e.g.
        # cylindrical) surfaces, the nearest raw intersection is often a
        # neighboring mesh triangle on the *same* face due to surface
        # curvature, not a real crossing to the opposite wall. Results are
        # sorted nearest-first, so the first non-self hit is the answer.
        for k in range(1, intersector.NbPnt() + 1):
            if intersector.Face(k).IsSame(source_face):
                continue
            dist = intersector.WParameter(k)
            if dist < min_dist:
                min_dist = dist
            break
    return min_dist


def check_min_wall_thickness(shape: cq.Shape, assertion: ResolvedAssertion) -> AssertionResult:
    p = assertion.params
    min_required = float(p["min_thickness"])
    sample_count = int(p.get("sample_count", 2000))

    actual_min = _min_wall_thickness_sampled(shape, sample_count)
    status = "pass" if actual_min >= min_required else "fail"
    return AssertionResult(
        id=assertion.id, type=assertion.type, status=status,
        expected={"min_thickness": min_required},
        actual={"approx_min_thickness": round(actual_min, 4)},
        message="ok (approximate, ray-sampled)" if status == "pass"
        else f"approximate min wall thickness {actual_min:.3f}mm < required {min_required}mm",
    )
