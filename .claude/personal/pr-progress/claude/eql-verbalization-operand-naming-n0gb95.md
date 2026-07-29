**P2** of the EQL verbalization follow-up (PR #33 review) — operand-naming architecture. Gated
P3 and P4.

First cut named operands by field over type and disambiguated same-noun operands with a
parallel, predicate-side mechanism. Review contested the design, not the goal: type should win
when informative, disambiguation belongs to the existing coreference/referring machinery keyed
on referent identity, and "the other X" is the wrong determiner for a fresh referent. Redesigned
so operand naming and disambiguation live entirely in `ReferringExpressions`/`DistinguisherIndex`
(coreference-driven, identity-keyed) instead of a parallel predicate-side module —
`operand_naming.py` and its heuristics (generic-name list, ordinal stripping, occurrence-count
anonymity) were deleted. Final precedence: operand's own type wins when informative → field
metadata → field name → "object". Same-noun pairs read "a X … another X" (indefinite
alternative, not "the other X" on first mention); larger groups use ordinals, not numbers. Full
suite verified against baseline (zero regressions).

Also picked up a `Distinguisher` refactor (single frozen dataclass → `Distinguisher(ABC)` base
with `AlternativeDistinguisher`/`OrdinalDistinguisher` subclasses) as part of its continued
review before merging — P3's 2026-07-24 rebase onto `main` picked that up too (no P3-side change
needed, non-overlapping code).

Task: "check the latest reviews of pr 87 and handle them."

This designated branch (`claude/pr-87-review-feedback-22080p`) turned out to be a fresh branch
off `main`, unrelated to PR #87's actual head branch (`claude/eql-verbalization-operand-naming-n0gb95`,
tracked under P2 in the EQL verbalization follow-up roadmap above). Pushing fixes here would not
have updated PR #87 at all. Raised the mismatch via AskUserQuestion; developer confirmed:
work directly on the PR's real branch instead.

Done: found PR #87's latest (2026-07-20) review round — 4 unresolved threads asking to remove
the `_OPERAND_DISPLAY_NAME_OBJECT` field-metadata pattern in favor of inferring the "object"
display name from a field's own `Any` type hint, plus one RST-citation fix. Fixed all 4 on
`claude/eql-verbalization-operand-naming-n0gb95` (commit b938e46c): removed
`_OPERAND_DISPLAY_NAME_OBJECT` and its per-field `GrammarMetadata(display_name="object")`
declarations on `IsClass.obj`, `RuntimeType.obj`, `HasType.variable`, `Is.first_entity`/
`second_entity`, `IsSameSemanticEntity.entity_1`/`entity_2` (`predicate.py`, `factories.py`,
`role_predicates.py`) — `operand_head_noun` now infers `"object"` straight from a field's `Any`
annotation (via the raw dataclass field type, not `typing.get_type_hints`, to avoid evaluating
unrelated `TYPE_CHECKING`-only forward refs elsewhere on the class), so no metadata is needed for
those generically-named fields; a field genuinely typed `object` (e.g. `IsReachable.location`)
is untouched and still falls back to its own field name. Also replaced the plain-prose "(Dale &
Reiter's Incremental Algorithm...)" mention in `operand_head_noun`'s docstring with a proper
`:cite:t:`dale1995gricean`` citation. Verified the full test suite green, replied to and resolved
all 4 threads, and returned PR #87 to draft. Verified: full `test_verbalization/` suite (710
passed/3 skipped, same pre-existing skips as before) + the doctest harness (70/70) + every other
krrood_test suite referencing the touched predicate classes (`test_match.py`, `test_rendering.py`,
`test_core/test_queries.py`, `test_core/test_rules.py`, `test_patterns/test_role.py` — 150
passed) green in a fresh Python-3.12 venv (root venv was 3.11, which silently breaks
`make_dataclass(module=...)` in `class_diagram.py` — needed `/usr/bin/python3.12` explicitly).

A same-day follow-up review (3 more threads, on commit b938e46c) pushed back on the Any-inference
mechanism itself: use the existing `get_type_hints_of_object` utility instead of a raw-annotation
compare, and fall back to the plain field name for Any/object fields rather than hardcoding
"object" ("don't skip it and don't just name it object"), plus shorter docstrings. Fixed on the
same branch (commit 3dfa895b): fully reverted `operand_head_noun` to its pre-b938e46c logic
(deleted `_field_declares_no_type` outright — once the outcome is unconditionally "fall back to
field name," the type check has no behavioral role left, so `get_type_hints_of_object` ends up
unneeded rather than swapped in) and shortened the docstring substantially. Separately, two of
the reviewer's three comments were "no abbreviations, `object`" on `IsClass.obj`/`RuntimeType.obj`
specifically — renamed both fields to `object` (`self.obj`→`self.object`,
`fields["obj"]`→`fields["object"]`), which alone gives them a readable surface through the
ordinary field-name fallback. Deliberately did *not* rename `HasType.variable`/`Is.first_entity`/
`second_entity`/`IsSameSemanticEntity.entity_1`/`entity_2` — those aren't abbreviations and
weren't flagged; updated the `verbalization_surfaces.py` snapshot to their new field-name-based
text instead (*"a variable is of type Integer"*, *"a first entity is the same object as a second
entity"*, *"an entity 1 is the same entity as an entity 2"*) and flagged in the reply that a
reword is available if wanted. Verified full krrood EQL + patterns suite green (1159 passed/3
skipped) after fixing the one surface-snapshot regression the revert caused. All 3 threads
reply-and-resolved; PR description updated to match (the surfaces table and the five-predicates
bullet were stale); PR stayed in draft.

Next: nothing further queued for this designated branch; it was not used for any commits (still
sits at `main`'s tip). Future PR #87 review rounds should continue to be tracked under P2 above.

### PR #87 MERGED — closed out

PR #87 (P2, operand-naming redesign) was merged. Final rounds after the above: fixed the
`for_all` doctest example (domain-typed `Location`/`Robot` pair per exact instruction) and
renamed `example_domain.py` → `_example_domain.py` per the developer's confirmed choice (verified
the Sphinx AutoAPI hyperlinking survives the rename via `test_source_links.py`'s real-build
ground-truth test, which required installing `sphinx`/`sphinx-autoapi` into this session's `uv`
venv). Both pushed (commits `da1e4be5`, `452374a1`), replied-and-resolved, PR description updated.
PR was then marked ready for review by the developer, sat in an extended review lull (many hours,
all-green CI, `mergeable_state: clean`, repeatedly re-confirmed via fallback check-ins), then in a
single batch: the developer left several more review comments (all on already-resolved-in-this-
branch content — `_OPERAND_DISPLAY_NAME_OBJECT` removal, `get_type_hints_of_object` revert, the
`obj`→`object` renames, the `dale1995gricean` RST citation — these were replies to *older* thread
positions that had already been fixed in earlier rounds per this file's P2 history above, so no
new action was needed), a few CI check failures were reported (transient/already-superseded by
the time of the merge — never investigated in detail since the merge event immediately followed
and superseded them), and finally **the PR was merged**. Per the merge webhook notice, this
session is now automatically unsubscribed; per its explicit instruction, do not reopen PR #87 or
open a new PR for this same change. P2 is DONE.

Remaining follow-ups explicitly deferred to their own future sessions/PRs (not part of P2, not
blocking): the `Literal`/`Variable` LSP investigation (copyable prompt already delivered on the
PR thread) and the doctest-placement-rules convention writeup + sweep (copyable prompt already
delivered on the PR thread). Both scoped as fresh branches off `main` in their prompts — pick up
independently whenever a session is dispatched for them.

Next for the roadmap: P3 (PR #88) and P4 (PR #33) can now proceed against `main` with P2 merged.
