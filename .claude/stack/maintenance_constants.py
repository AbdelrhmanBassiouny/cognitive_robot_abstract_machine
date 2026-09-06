"""
The maintenance executor's hand-maintained values.

Everything here is a decision somebody made and may change again - where the API lives,
which environment variables carry a credential, the heading a promotion link is written
under. They are gathered in one module so changing one is an edit rather than a search
through whichever module happens to read it.

Values a program derives for itself belong beside the code that derives them, not here.
"""

from __future__ import annotations

import re

GITHUB_API_ROOT = "https://api.github.com"
"""
Base URL every REST call the executor makes is built on.
"""

CREDENTIAL_VARIABLES = ("GH_TOKEN", "GITHUB_TOKEN")
"""
Environment variables read, in order, for the token the API calls authenticate with.
"""

BASE_RETARGET_REFUSAL_STATUSES = frozenset({403, 422})
"""
The two status codes a base-branch retarget can come back with that a caller cannot act
on but must fall back from: ``403`` (this credential is refused the write) and ``422``
(the pull request is a member of a GitHub Stack, which must be moved through native
Stack mechanics instead of a plain base change).

Any other status is a genuine failure.
"""

SESSION_LINK_PATTERN = re.compile(r"https://claude\.ai/code/session_[A-Za-z0-9_-]+")
"""
Matches the session link a pull request description carries, which is the only channel
for telling a branch's owner that their branch needs them.
"""

NEEDS_RESOLUTION_COMMENT_PREFIX = "🔴 ROUTINE - NEEDS RESOLUTION:"
"""
Opens a comment reporting anything a branch's owner alone can resolve - a restack
conflict or a pending reparent - so every one of them can be found at a glance.
"""

MERGEABLE_STATE_WITH_CONFLICTS = "dirty"
"""
The one ``mergeable_state`` meaning a branch genuinely conflicts with its base.

Everything else - ``clean``, ``unstable``, ``blocked``, ``behind``, ``has_hooks``,
``unknown`` - means there are no conflicts, whatever else may be true of it.
"""

PROMOTION_HEADING = "## Promote"
"""Heading the compare-and-create link is written under, in the fork pull request's own
description - the summary that carried it is delivered once and then gone, and the
description is still there a week later."""

PROMOTION_LINK_LABEL = "cram2-link-sent"
"""
Marks a branch whose link has been built, so a later pass does not rebuild it.
"""
