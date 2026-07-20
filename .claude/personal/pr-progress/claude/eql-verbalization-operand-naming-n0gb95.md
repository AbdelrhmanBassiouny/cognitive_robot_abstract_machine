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
