"""Reference agent: prompts Claude for CadQuery code, executes it in a
sandboxed subprocess, exports STEP. Demonstrates the harness end-to-end and
is deliberately swappable -- any agent that can produce a STEP file from a
spec string fits the same `Agent` protocol.
"""
from __future__ import annotations

import re
from pathlib import Path

import anthropic

from cad_eval.agents.base import AgentResult
from cad_eval.agents.prompts import DEFAULT_MODEL, MAX_TOKENS, SYSTEM_PROMPT, USER_PROMPT_TEMPLATE
from cad_eval.agents.sandbox import run_python_script

_CODE_BLOCK_RE = re.compile(r"```(?:python)?\s*\n(.*?)```", re.DOTALL)

_EXPORT_FOOTER = """

# --- harness-controlled export footer (not written by the model) ---
import cadquery as _cad_eval_cq
_cad_eval_cq.exporters.export(result, {step_path!r}, exportType="STEP")
"""


class ReferenceLLMAgent:
    name = "reference_llm_agent"

    def __init__(self, model_id: str = DEFAULT_MODEL):
        self.model_id = model_id
        self._client = anthropic.Anthropic()

    def _generate_code(self, spec_text: str) -> tuple[str | None, str]:
        message = self._client.messages.create(
            model=self.model_id,
            max_tokens=MAX_TOKENS,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": USER_PROMPT_TEMPLATE.format(spec_text=spec_text)}],
        )
        text = "".join(block.text for block in message.content if block.type == "text")
        match = _CODE_BLOCK_RE.search(text)
        if not match:
            return None, text
        return match.group(1), text

    def run(self, spec_text: str, workdir: Path) -> AgentResult:
        workdir = Path(workdir)
        workdir.mkdir(parents=True, exist_ok=True)
        step_path = workdir / "part.step"

        try:
            code, raw_response = self._generate_code(spec_text)
        except Exception as exc:  # noqa: BLE001 - any API failure is an llm_error, not a crash
            return AgentResult(status="llm_error", message=str(exc))

        if code is None:
            return AgentResult(
                status="code_parse_error",
                message="no fenced Python code block found in model response",
                stdout_tail=raw_response[-2000:],
            )

        script_path = workdir / "agent_code.py"
        script_path.write_text(code + _EXPORT_FOOTER.format(step_path=str(step_path)))

        sandbox_result = run_python_script(script_path, workdir)

        if sandbox_result.timed_out:
            return AgentResult(
                status="timeout", stdout_tail=sandbox_result.stdout, stderr_tail=sandbox_result.stderr,
                message="agent code did not finish within the sandbox timeout",
                duration_sec=sandbox_result.duration_sec,
            )
        if sandbox_result.returncode != 0:
            return AgentResult(
                status="execution_error", stdout_tail=sandbox_result.stdout, stderr_tail=sandbox_result.stderr,
                message=f"agent code exited with code {sandbox_result.returncode}",
                duration_sec=sandbox_result.duration_sec,
            )
        if not step_path.exists():
            return AgentResult(
                status="no_step_output", stdout_tail=sandbox_result.stdout, stderr_tail=sandbox_result.stderr,
                message="agent code ran successfully but produced no STEP file",
                duration_sec=sandbox_result.duration_sec,
            )

        return AgentResult(
            status="ok", step_path=str(step_path),
            stdout_tail=sandbox_result.stdout, stderr_tail=sandbox_result.stderr,
            duration_sec=sandbox_result.duration_sec,
        )
