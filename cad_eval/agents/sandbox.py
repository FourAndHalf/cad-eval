"""Safe(r) execution of LLM-generated CadQuery code.

Never `exec()` untrusted model output in-process. The generated code is
written to a temp file and run as a separate subprocess with a timeout and
basic resource limits. This is NOT a full sandbox (no container, no network
isolation) -- that's an explicit v1 scoping decision, called out in the
README as the productionization next step, not built here.
"""
from __future__ import annotations

import resource
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

_TIMEOUT_SEC = 30
_MEMORY_LIMIT_BYTES = 2 * 1024 * 1024 * 1024  # 2 GiB
_CPU_LIMIT_SEC = 30
_OUTPUT_TAIL_CHARS = 4000


@dataclass
class SandboxResult:
    returncode: int | None
    timed_out: bool
    stdout: str
    stderr: str
    duration_sec: float


def _limit_resources():
    resource.setrlimit(resource.RLIMIT_AS, (_MEMORY_LIMIT_BYTES, _MEMORY_LIMIT_BYTES))
    resource.setrlimit(resource.RLIMIT_CPU, (_CPU_LIMIT_SEC, _CPU_LIMIT_SEC))


def run_python_script(script_path: Path, workdir: Path) -> SandboxResult:
    start = time.monotonic()
    try:
        proc = subprocess.run(
            [sys.executable, str(script_path)],
            cwd=str(workdir),
            timeout=_TIMEOUT_SEC,
            capture_output=True,
            text=True,
            preexec_fn=_limit_resources,
            start_new_session=True,
        )
        duration = time.monotonic() - start
        return SandboxResult(
            returncode=proc.returncode,
            timed_out=False,
            stdout=proc.stdout[-_OUTPUT_TAIL_CHARS:],
            stderr=proc.stderr[-_OUTPUT_TAIL_CHARS:],
            duration_sec=duration,
        )
    except subprocess.TimeoutExpired as exc:
        duration = time.monotonic() - start
        return SandboxResult(
            returncode=None,
            timed_out=True,
            stdout=(exc.stdout or "")[-_OUTPUT_TAIL_CHARS:] if exc.stdout else "",
            stderr=(exc.stderr or "")[-_OUTPUT_TAIL_CHARS:] if exc.stderr else "",
            duration_sec=duration,
        )
