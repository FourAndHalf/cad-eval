from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"
TASKS = Path(__file__).parent.parent / "tasks"


@pytest.fixture
def fixtures_dir():
    return FIXTURES


@pytest.fixture
def tasks_dir():
    return TASKS
