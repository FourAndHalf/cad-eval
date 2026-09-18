"""Task designer: turns a free-text design-requirements prompt into a task
YAML (spec template + variables + assertions) conforming to cad_eval's task
schema, via Gemini. Used by `cad-eval design` to bootstrap a new task file
without hand-authoring YAML.
"""
from __future__ import annotations

import re

import yaml
from google import genai
from google.genai import types
from pydantic import ValidationError

from cad_eval.agents.prompts import (
    DEFAULT_MODEL,
    MAX_TOKENS,
    TASK_DESIGN_RETRY_TEMPLATE,
    TASK_DESIGN_SYSTEM_PROMPT,
    TASK_DESIGN_USER_TEMPLATE,
)
from cad_eval.task.schema import TaskSpec

_YAML_BLOCK_RE = re.compile(r"```(?:yaml)?\s*\n(.*?)```", re.DOTALL)


class TaskDesignError(RuntimeError):
    """Raised when the designer can't produce a schema-valid task YAML."""


class TaskDesignerAgent:
    def __init__(self, model_id: str = DEFAULT_MODEL):
        self.model_id = model_id
        self._client = genai.Client()

    def _generate_yaml_text(self, prompt: str) -> str:
        response = self._client.models.generate_content(
            model=self.model_id,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=TASK_DESIGN_SYSTEM_PROMPT,
                max_output_tokens=MAX_TOKENS,
            ),
        )
        return response.text or ""

    def design(self, requirements: str, task_id: str, max_attempts: int = 3) -> tuple[TaskSpec, str]:
        """Returns (validated TaskSpec, raw YAML text) or raises TaskDesignError."""
        prompt = TASK_DESIGN_USER_TEMPLATE.format(requirements=requirements, task_id=task_id)
        last_yaml_text: str | None = None
        last_error: str | None = None

        for _ in range(max_attempts):
            if last_error is not None:
                prompt = TASK_DESIGN_RETRY_TEMPLATE.format(prior_yaml=last_yaml_text, error=last_error)

            raw = self._generate_yaml_text(prompt)
            match = _YAML_BLOCK_RE.search(raw)
            if not match:
                last_yaml_text = raw
                last_error = "no fenced ```yaml code block found in response"
                continue

            yaml_text = match.group(1)
            last_yaml_text = yaml_text
            try:
                data = yaml.safe_load(yaml_text)
                task = TaskSpec(**data)
            except (yaml.YAMLError, ValidationError, TypeError) as exc:
                last_error = str(exc)
                continue

            return task, yaml_text

        raise TaskDesignError(
            f"task designer failed to produce a valid task YAML after {max_attempts} attempts: {last_error}"
        )
