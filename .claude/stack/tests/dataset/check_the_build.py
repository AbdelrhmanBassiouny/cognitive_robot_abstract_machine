"""
A suite whose verdict depends on what the build under test actually contains.

Copied onto the base of the scratch fork, where every build carries it, and run against
the finished integration branch. Its point is that a semantic break is *reproduced*
rather than declared: the assertion holds for either tip alone and fails only for a tree
carrying both, which is the failure per-branch checks structurally cannot see.
"""

import pathlib
import sys

# Only a build carrying the test needs the module it imports, which is what makes this
# fail for a combination of tips rather than for either one of them.
if pathlib.Path("test_needs_the_module.py").exists():
    import a_module

    assert a_module.VALUE

sys.exit(0)
