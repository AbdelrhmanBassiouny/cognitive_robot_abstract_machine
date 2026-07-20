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
suite green, replied to and resolved all 4 threads, and returned PR #87 to draft. Full details
recorded under P2 in the "EQL verbalization follow-up plan" section above — that is now the
single source of truth for this PR's status, not this block.

Next: nothing further queued for this designated branch; it was not used for any commits (still
sits at `main`'s tip). Future PR #87 review rounds should continue to be tracked under P2 above.
