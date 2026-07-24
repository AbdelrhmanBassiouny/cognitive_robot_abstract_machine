Task: "check the latest reviews of pr 87 and handle them."

This designated branch (`claude/pr-87-review-feedback-22080p`) turned out to be a fresh branch
off `main`, unrelated to PR #87's actual head branch (`claude/eql-verbalization-operand-naming-n0gb95`,
tracked under P2 in the EQL verbalization follow-up roadmap above). Pushing fixes here would not
have updated PR #87 at all. Raised the mismatch via AskUserQuestion; developer confirmed:
work directly on the PR's real branch instead.

Done: found PR #87's latest (2026-07-20) review round — 4 unresolved threads asking to remove
the `_OPERAND_DISPLAY_NAME_OBJECT` field-metadata pattern in favor of inferring the "object"
display name from a field's own `Any` type hint, plus one RST-citation fix. Fixed all 4 on
`claude/eql-verbalization-operand-naming-n0gb95` (commit b938e46c), verified the full test
suite green, replied to and resolved all 4 threads, and returned PR #87 to draft.

A same-day follow-up review (3 more threads, on commit b938e46c) pushed back on the Any-inference
mechanism itself: use the existing `get_type_hints_of_object` utility instead of a raw-annotation
compare, and fall back to the plain field name for Any/object fields rather than hardcoding
"object" — plus rename the two actual abbreviations (`IsClass.obj`/`RuntimeType.obj` → `object`).
Fixed on the same branch (commit 3dfa895b): fully reverted `operand_head_noun` to its pre-b938e46c
logic (the type check became a no-op once the fallback is unconditional, so it was deleted rather
than reimplemented with `get_type_hints_of_object`), renamed the two `obj` fields, left the other
non-abbreviated generic fields (`variable`, `first_entity`/`second_entity`, `entity_1`/`entity_2`)
untouched, and updated the `verbalization_surfaces.py` snapshot to match. Verified full krrood EQL
+ patterns suite green (1159 passed/3 skipped). All 3 threads reply-and-resolved; PR description
updated to match; PR stayed in draft.

Full details recorded under P2 in the "EQL verbalization follow-up plan" section above — that is
now the single source of truth for this PR's status, not this block.

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
