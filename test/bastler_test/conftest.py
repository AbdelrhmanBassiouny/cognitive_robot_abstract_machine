"""
Makes ``bastler`` importable when this directory is run from an arbitrary working
directory - the package is a plain top-level directory on the repository root,
importable with no install, so the root just has to be on ``sys.path``.

This suite runs in the lightweight ``test_bastler`` CI job with ``--confcutdir`` pointed
here, so the repository-root ``test/conftest.py`` - which imports the robotics stack that
job does not install - is never loaded for it.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
