"""
Shared setup for the hook tests: module importability, the scratch repository they all
run against, and the stubbed ``PATH`` the ones that would otherwise reach GitHub use.

The hooks' Python scripts are single-file scripts, not an installed package - so their
directory is added to ``sys.path`` here rather than requiring an ``__init__.py``/
packaging setup just for tests. Mirrors
``.claude/skills/plan-dashboard/tests/conftest.py``.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from scratch_repository import ScratchRepository  # noqa: E402
from stub_executables import StubExecutableDirectory  # noqa: E402


@pytest.fixture
def scratch_repository(tmp_path: Path) -> ScratchRepository:
    """
    An initialized scratch project root and its bare notes remote, with nothing
    committed and no hook scripts installed yet.

    Each test module layers on what its own hook needs - the scripts under test, the
    files they read, and the notes branch contents - so only what genuinely differs
    between them lives in the modules.

    :param tmp_path: pytest's per-test temporary directory.
    :return: The scratch repository.
    """
    return ScratchRepository.create(tmp_path)


@pytest.fixture
def stub_executables(tmp_path: Path) -> StubExecutableDirectory:
    """
    An empty stub-executable directory, for the tests whose subject would otherwise call
    ``gh``, ``curl`` or ``pip`` for real.

    Each test installs the stubs it needs and runs its subprocess with
    :meth:`StubExecutableDirectory.subprocess_environment`, which also strips the
    caller's own GitHub credentials.

    :param tmp_path: pytest's per-test temporary directory.
    :return: The stub directory, with nothing installed yet.
    """
    return StubExecutableDirectory.create(tmp_path)
