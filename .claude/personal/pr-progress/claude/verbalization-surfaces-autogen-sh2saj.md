PR #97 (claude/verbalization-surfaces-autogen-sh2saj): auto-generate
verbalization_results.py via krrood's code_generation.CodeGenerator (jinja),
mirroring the ormatic_interface.py conftest.py-regeneration pattern. Off
main, PR #39 (code-generation-extract) + PR #87 (operand-naming) merged
first.

Status: implementation complete, all 20 review threads resolved, PR is
draft (personal convention), CI running on head f786a908.

This session's own contribution to this round: independently arrived at
the same fix for the last open thread (predicate.py:446, "value given to a
field is a Literal or small domain, rendered by its own value") that
another concurrent session instance had already implemented and pushed as
f786a908 first. Verified the two approaches were equivalent (module-level
PLACEHOLDER_EXAMPLE_VALUES dict vs. an instance-field operand_overrides
dict on VerbalizationResultsOfPackage), confirmed the pushed version was
already fully tested (735 + 984 passed) and its thread already
reply-and-resolved, then discarded this session's uncommitted duplicate
work (git stash + reset --hard to origin) rather than pushing a
conflicting commit.

Next: wait for CI on f786a908 to finish; if green, nothing further needed
until the developer reviews again; if red, investigate and fix.
