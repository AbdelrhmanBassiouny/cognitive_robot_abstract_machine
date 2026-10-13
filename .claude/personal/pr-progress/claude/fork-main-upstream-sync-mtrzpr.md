## Next
Nothing outstanding. Dashboard republished (same URL), structural change recorded on
tracking issue #102. PR #188 is open as a draft with the `bug` label; per my notes,
opening it ends this session's obligation to it.

## Plan
Make every session start from a fresh base: a deterministic SessionStart step that
fast-forwards the fork's default branch from the upstream repository, locally and on
the fork, and reports how stale the checked-out branch is.

Tracked as `workflow-unification` item `fresh-base-at-session-start` (personal-data
track). PR #188, draft, `bug` label.

Design decisions (all implemented):
- `.claude/hooks/fast-forward-default-branch.sh`, run as a subprocess by
  session-start.sh, printing its outcome plus indented follow-up rows.
- Upstream resolved from `stack.py configuration`, so no repository is named in the
  hook and there is one place to correct if the upstream moves.
- Fast-forward only, never a force push; a diverged base is reported and left alone.
- Only the default branch is touched; the checked-out branch's staleness is reported,
  never merged or rebased automatically.
- Never fatal: every refusal reports and exits 0.
