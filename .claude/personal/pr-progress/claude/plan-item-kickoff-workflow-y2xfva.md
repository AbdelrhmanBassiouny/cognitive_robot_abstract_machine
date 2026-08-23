# always-read-upstream-reviews — PR #194 (draft, `bug`)

Plan item `workflow-unification` / `always-read-upstream-reviews`, track `personal-data`,
wave `immediate`. Branch off `origin/main` (`3f643cf`). No dependencies.
Session: https://claude.ai/code/session_01Cs9MvTBPS4hsd1HJimooVy

## The fix

`/plan-item-resolve` invokes `/upstream-reviews` only when the fork PR carries `in-review`.
The label is added by hand after clicking Create, so it is not evidence the upstream pull
request exists — `stacked-pr-maintenance/SKILL.md` says outright that no pass ever adds it.
Ten open fork PRs carry `cram2-link-sent` against two carrying `in-review`; those ten are
skipped in silence. Fix: invoke it whenever the item has a branch.

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

## Done — all of it

- Branch pushed, draft PR #194 opened and labelled `bug`; description filled in.
- Manifest: `branch`, `session`, `pull_request_number`, `status: in_progress` written;
  roadmap section appended (`plan_item_bootstrap.py open` + `record`). Dashboard
  republished to its existing URL.
- `test_upstream_review_reading.py` written first and confirmed failing on the unedited
  document, passing after; `plan-item-resolve/SKILL.md` edited at both sites; 515 tests
  pass over the four CI directories; `format_docstrings.py` run. Commit `258c5334`.

## Next

Nothing outstanding in this session. CI on #194 has not been read yet — it is a
first run on a new branch. The PR stays a draft.

## Decisions worth not relitigating

- **Test location corrected against the roadmap's carried note.** It said to add a
  `plan-item-resolve/tests/` directory plus a constant and a `ci.yml` path. #185 deletes
  `.claude/hooks/tests/` and `.claude/stack/tests/`, collapses the four-directory job into
  one `test_bastler` job, and rewrites both of those files — so that route builds what #185
  removes, in the two files it conflicts with most.
- **No wording assertions.** #121's review round cut exactly that kind of test; the step 5
  rewording is covered by review, and the roadmap says so rather than pretending a test
  guards it.
- **Not folded in:** `.claude/upstream_reviews/tests/` runs in no CI job (#185 fixes it
  incidentally); `stack.toml`/`stack.py`'s "cram2 is not readable from the cloud" is false
  and already flagged in the 2026-08-07 roadmap entry as `stacked-pr-maintenance`'s to fix.
