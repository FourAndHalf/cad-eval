"""Result models shared by the checker and the report writer."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

FailureCategory = Literal[
    "dimensional", "topological", "intent_regeneration", "agent_failure"
]

AgentStatus = Literal[
    "ok", "llm_error", "code_parse_error", "execution_error", "timeout", "no_step_output"
]


class AssertionResult(BaseModel):
    id: str
    type: str
    status: Literal["pass", "fail", "error"]
    expected: dict = Field(default_factory=dict)
    actual: dict = Field(default_factory=dict)
    message: str = ""


class TaskResult(BaseModel):
    task_id: str
    variant: Literal["base", "perturbation"] = "base"
    perturbed_variable: str | None = None
    delta_description: str | None = None
    agent_status: AgentStatus = "ok"
    overall_status: Literal["pass", "fail", "agent_failure"] = "fail"
    failure_categories: list[FailureCategory] = Field(default_factory=list)
    assertions: list[AssertionResult] = Field(default_factory=list)
    step_path: str | None = None
    agent_stdout_tail: str | None = None
    agent_stderr_tail: str | None = None
    duration_sec: float = 0.0


class RunResult(BaseModel):
    run_id: str
    timestamp: str
    agent_name: str
    model_id: str | None = None
    tasks: list[TaskResult] = Field(default_factory=list)
