"""Agent protocol: the harness's only contract with "the agent under test".

Any agent -- an LLM writing CadQuery code, a future Aurorin-kernel-backed
agent, a human -- just needs to implement `run(spec_text, workdir)` and
produce a STEP file. The harness never inspects agent internals.
"""
from __future__ import annotations

from pathlib import Path
from typing import Literal, Protocol

from pydantic import BaseModel

AgentStatus = Literal[
    "ok", "llm_error", "code_parse_error", "execution_error", "timeout", "no_step_output"
]


class AgentResult(BaseModel):
    status: AgentStatus
    step_path: str | None = None
    stdout_tail: str = ""
    stderr_tail: str = ""
    message: str = ""
    duration_sec: float = 0.0


class Agent(Protocol):
    name: str
    model_id: str | None

    def run(self, spec_text: str, workdir: Path) -> AgentResult:
        """Given a task's natural-language spec, produce a STEP file under
        `workdir` and return an AgentResult pointing at it."""
        ...
