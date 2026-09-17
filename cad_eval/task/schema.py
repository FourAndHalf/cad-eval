"""Pydantic models for the task YAML assertion DSL.

A task YAML has: a Jinja2 `description_template` (the natural-language spec),
a `variables` block (typed, defaulted parameters the template and assertions
interpolate from), a list of `assertions`, and an optional `parametric` block
naming which variables can be perturbed for the robustness tests.

Assertion numeric/string fields may contain Jinja2 expressions (e.g.
"{{ hole_count }}") so that perturbing a variable and re-rendering
automatically produces a correctly-adjusted assertion set.
"""
from __future__ import annotations

from typing import Annotated, Literal, Union

from pydantic import BaseModel, Field


class Variable(BaseModel):
    type: Literal["int", "float", "str", "bool"]
    default: int | float | str | bool
    unit: str | None = None


# ---------------------------------------------------------------------------
# Assertion param payloads (discriminated by AssertionBlock.type)
# ---------------------------------------------------------------------------

class ManifoldSolidParams(BaseModel):
    min_solid_count: int = 1
    max_solid_count: int = 1
    allow_open_shells: bool = False


class PCDBlock(BaseModel):
    diameter: str
    diameter_tol: float
    center: list[float] | None = None
    even_spacing: bool = True
    angle_tol_deg: float = 1.0


class HolePatternParams(BaseModel):
    expected_count: str
    diameter_nominal: str
    diameter_tol: str
    through: bool = True
    axis: list[float] | None = None
    axis_tol_deg: float = 2.0
    pcd: PCDBlock | None = None
    position_tol: float = 0.2
    selection_hint: dict | None = None


class BoundingBoxParams(BaseModel):
    expected: dict[str, str]  # keys: x, y, z -> Jinja2 expression strings
    tolerance: float


class VolumeParams(BaseModel):
    expected: str
    tolerance_pct: float


class MinWallThicknessParams(BaseModel):
    min_thickness: str
    sample_count: int = 2000
    region: str | None = None


class KeywaySlotParams(BaseModel):
    width: str
    width_tol: float
    depth: str
    depth_tol: float
    length: str
    length_tol: float
    shaft_diameter: str
    position_along_axis_from_end: str
    position_tol: float = 0.5


class FeatureCountParams(BaseModel):
    feature_type: Literal["hole", "fillet", "slot"]
    expected_count: str


class AssertionBase(BaseModel):
    id: str
    description: str = ""


class ManifoldSolidAssertion(AssertionBase):
    type: Literal["manifold_solid"]
    params: ManifoldSolidParams


class HolePatternAssertion(AssertionBase):
    type: Literal["hole_pattern"]
    params: HolePatternParams


class BoundingBoxAssertion(AssertionBase):
    type: Literal["bounding_box"]
    params: BoundingBoxParams


class VolumeAssertion(AssertionBase):
    type: Literal["volume"]
    params: VolumeParams


class MinWallThicknessAssertion(AssertionBase):
    type: Literal["min_wall_thickness"]
    params: MinWallThicknessParams


class KeywaySlotAssertion(AssertionBase):
    type: Literal["keyway_slot"]
    params: KeywaySlotParams


class FeatureCountAssertion(AssertionBase):
    type: Literal["feature_count"]
    params: FeatureCountParams


AssertionBlock = Annotated[
    Union[
        ManifoldSolidAssertion,
        HolePatternAssertion,
        BoundingBoxAssertion,
        VolumeAssertion,
        MinWallThicknessAssertion,
        KeywaySlotAssertion,
        FeatureCountAssertion,
    ],
    Field(discriminator="type"),
]


# ---------------------------------------------------------------------------
# Perturbation
# ---------------------------------------------------------------------------

class Delta(BaseModel):
    op: Literal["set", "scale", "add"]
    value: float | int | None = None
    factor: float | None = None


class PerturbableVariable(BaseModel):
    variable: str
    deltas: list[Delta]


class ParametricBlock(BaseModel):
    perturbable: list[PerturbableVariable] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Top-level task
# ---------------------------------------------------------------------------

class TaskSpec(BaseModel):
    task_id: str
    title: str
    description_template: str
    variables: dict[str, Variable]
    assertions: list[AssertionBlock]
    parametric: ParametricBlock = Field(default_factory=ParametricBlock)
