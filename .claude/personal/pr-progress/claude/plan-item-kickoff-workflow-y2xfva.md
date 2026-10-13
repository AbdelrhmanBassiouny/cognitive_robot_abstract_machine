## Next
Nothing outstanding. CI on #194 has not been read yet. The PR stays a draft.


## Plan
1. Failing test first, in `.claude/hooks/tests/` (already in CI — no new constant, no
   `ci.yml` line). Absence: the `in_review_label` value read from `.claude/stack/stack.toml`
   does not appear in `plan-item-resolve/SKILL.md`. Presence: the skill still invokes the
   upstream-reviews skill, its name read from that skill's frontmatter. Both derived, not
   retyped — no wording pinned.
2. Edit `plan-item-resolve/SKILL.md` at **two** sites: the step-2 bullet (lines 76-86), and
   step 5's "when the item looked promoted" flag (lines 168-169), which carries the same
   premise in different words.
3. Run the four-directory CI set; `format_docstrings.py` on the new test.
4. Fill in the PR description's Changes/Verification sections, keep it a draft.
