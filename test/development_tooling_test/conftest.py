"""
Makes ``development_tooling`` importable when this directory is run directly from an
arbitrary working directory - the package is a plain top-level directory on the
repository root, importable with no install, so the root just has to be on
``sys.path``. Mirrors ``.claude/stack/tests/conftest.py``.

This suite runs in the lightweight ``test_claude_dev_tooling`` CI job with
``--confcutdir`` pointed here, so the repository-root ``test/conftest.py`` (which
imports the robotics stack) is never loaded for it.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
