from pathlib import Path
from unittest.mock import MagicMock

from cad_eval.agents.reference_llm_agent import ReferenceLLMAgent
from cad_eval.agents.sandbox import run_python_script


def _mock_response(text: str):
    response = MagicMock()
    response.text = text
    return response


def test_code_parse_error_when_no_fenced_block(tmp_path):
    agent = ReferenceLLMAgent.__new__(ReferenceLLMAgent)  # skip __init__ (no client needed)
    agent.model_id = "gemini-3.8-flash"
    agent._client = MagicMock()
    agent._client.models.generate_content.return_value = _mock_response("sorry, I can't do that")

    result = agent.run("build a box", tmp_path)
    assert result.status == "code_parse_error"


def test_llm_error_on_api_exception(tmp_path):
    agent = ReferenceLLMAgent.__new__(ReferenceLLMAgent)
    agent.model_id = "gemini-3.8-flash"
    agent._client = MagicMock()
    agent._client.models.generate_content.side_effect = RuntimeError("connection refused")

    result = agent.run("build a box", tmp_path)
    assert result.status == "llm_error"
    assert "connection refused" in result.message


def test_execution_error_on_broken_generated_code(tmp_path):
    agent = ReferenceLLMAgent.__new__(ReferenceLLMAgent)
    agent.model_id = "gemini-3.8-flash"
    agent._client = MagicMock()
    agent._client.models.generate_content.return_value = _mock_response(
        "```python\nraise RuntimeError('boom')\n```"
    )

    result = agent.run("build a box", tmp_path)
    assert result.status == "execution_error"
    assert "boom" in result.stderr_tail


def test_ok_status_and_step_export_on_valid_code(tmp_path):
    agent = ReferenceLLMAgent.__new__(ReferenceLLMAgent)
    agent.model_id = "gemini-3.8-flash"
    agent._client = MagicMock()
    agent._client.models.generate_content.return_value = _mock_response(
        "```python\nimport cadquery as cq\nresult = cq.Workplane('XY').box(10, 10, 5)\n```"
    )

    result = agent.run("build a small box", tmp_path)
    assert result.status == "ok", result.stderr_tail
    assert result.step_path is not None
    assert Path(result.step_path).exists()


def test_sandbox_reports_nonzero_exit_without_crashing_harness(tmp_path):
    script = tmp_path / "broken.py"
    script.write_text("import sys\nsys.exit(1)\n")
    result = run_python_script(script, tmp_path)
    assert result.returncode == 1
    assert not result.timed_out
