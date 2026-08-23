"""
The one thing about the resolve skill's upstream read worth asserting from code.

The skill is instructions, so most of what it says can only be checked by reading it.
The exception is what it must *not* condition on: a branch has an upstream pull request
from the moment its Create is clicked, while the promotion label appears only if someone
adds it afterwards, so the label is no evidence that the pull request exists. That is an
absence, computed from the configuration that owns the label rather than from a string
written here, which is what makes it worth a test where a prose assertion would not be.

Filesystem only: no network, no credentials, no scratch repository.
"""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

PROJECT_ROOT = Path(__file__).parents[3]

RESOLVE_SKILL_DOCUMENT = PROJECT_ROOT / ".claude/skills/plan-item-resolve/SKILL.md"
"""
The instructions a resolve run follows.
"""

UPSTREAM_REVIEWS_SKILL_DOCUMENT = (
    PROJECT_ROOT / ".claude/skills/upstream-reviews/SKILL.md"
)
"""
The instructions for reading a branch's upstream review threads.
"""

STACK_CONFIGURATION = PROJECT_ROOT / ".claude/stack/stack.toml"
"""
Where the promotion label is defined.
"""

PROMOTION_LABEL_KEY = "in_review_label"
"""
The configuration key naming the fork-pull-request label added at promotion time.
"""

SKILL_NAME_HEADING = re.compile(r"^name:\s*(?P<name>\S+)\s*$", re.MULTILINE)
"""
The ``name`` line of a skill document's frontmatter, which is what ``/`` invokes it by.
"""

# %% the definitions the assertions are computed from


def promotion_label() -> str:
    """
    The fork-pull-request label a developer adds once they have promoted a branch.

    Read through the key that owns it, so renaming either the key or its value reaches
    this test instead of leaving it asserting the absence of something nothing uses.

    :return: The label.
    """
    configuration = tomllib.loads(STACK_CONFIGURATION.read_text(encoding="utf-8"))
    return configuration[PROMOTION_LABEL_KEY]


def upstream_reviews_invocation() -> str:
    """
    How a session invokes the upstream-reviews skill.

    :return: The slash command, read from the skill's own frontmatter.
    """
    frontmatter = UPSTREAM_REVIEWS_SKILL_DOCUMENT.read_text(encoding="utf-8")
    return f"/{SKILL_NAME_HEADING.search(frontmatter).group('name')}"


# %% the resolve skill's upstream read


def test_the_upstream_read_is_not_conditioned_on_the_promotion_label():
    """
    The label is hand-added after the fact, so gating on it skips exactly the branches
    most likely to be carrying upstream review comments.
    """
    instructions = RESOLVE_SKILL_DOCUMENT.read_text(encoding="utf-8")

    assert promotion_label() not in instructions
    assert PROMOTION_LABEL_KEY not in instructions


def test_the_upstream_reviews_are_still_read():
    """
    Removing the condition must not remove the read it was conditioning.
    """
    instructions = RESOLVE_SKILL_DOCUMENT.read_text(encoding="utf-8")

    assert upstream_reviews_invocation() in instructions
