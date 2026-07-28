PR #97 (claude/verbalization-surfaces-autogen-sh2saj): auto-generate
verbalization_results.py via krrood's code_generation.CodeGenerator (jinja),
mirroring the ormatic_interface.py conftest.py-regeneration pattern. Off
main, PR #39 (code-generation-extract) + PR #87 (operand-naming) merged
first.

Status: implementation complete, all 21 review threads resolved, PR is
draft (personal convention), pushed as 1e263066, CI was pending on this
head as of the last check.

History: another concurrent session instance implemented and pushed
f786a908 (PLACEHOLDER_EXAMPLE_VALUES module-level dict keyed by
(callable, field name) tuple, replacing OverriddenOperand/
_placeholder_operand_overrides_ in predicate.py entirely) while this
session was independently building an equivalent fix; verified the two
approaches were equivalent and discarded this session's uncommitted
duplicate work rather than push a conflicting commit.

This round: developer asked (result_verification.py:38) to turn
PLACEHOLDER_EXAMPLE_VALUES's tuple key into a dataclass with
callable_class/field_name fields. Added PlaceholderExampleField (frozen
dataclass), re-keyed the registry and placeholder_operands()'s lookup on
it, ran scripts/format_docstrings.py, verified full test_verbalization/ +
test_patterns/ + test_class_diagrams/ green (1184 passed, 3 pre-existing
skips, same known ruff-version regeneration noise reverted before
committing). Pushed as 1e263066, replied-and-resolved the thread, updated
the PR description to mention the dataclass key.

Next: wait for CI on 1e263066; if green, nothing further needed until the
developer reviews again; if red, investigate and fix.
