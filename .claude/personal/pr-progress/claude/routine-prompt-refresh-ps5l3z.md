## Plan

Refresh `.claude/skills/stacked-pr-maintenance/routine-prompt.md`, which had drifted
from SKILL.md since it was last touched (65884bd4, 2026-08-03). Text-only change to
that one file. Draft PR #155.

Three drifts found and fixed:
1. "Do not summarise it back to me" contradicted SKILL.md's Finish section, which
   makes the emailed summary the delivery channel for the promotion create-links.
   Reworded to forbid describing the skill *instead of running it*.
2. ad6dfb86 ("Stop sessions from subscribing to their own pull requests") landed
   after this file, so the prompt never asserted that the skill's HARD RULES beat the
   host session's built-in PR-subscription/check-in defaults. Added one precedence
   line - not a copy of the rules, which 65884bd4 deliberately cut.
3. SKILL.md asserts "a scheduled run is configured to email its summary" but nothing
   told the registrar to configure that. Added the fresh-session + completion-email
   requirement.

Deliberately not re-added: a branch/ref pin for step 0a's `git checkout <ref> --
.claude/stack/` fallback. 65884bd4 cut that section as expired once `.claude/stack/`
reached the default branch, which it has.

## Done

- Read SKILL.md, stack README, stack.toml; diffed SKILL.md/`.claude/stack/` since
  65884bd4 to find the drift.
- Rewrote the substitution paragraph and the pasteable prompt block.
- Set the commit identity from `.claude/personal/git-identity` (the session default
  was the assistant identity AGENTS.md forbids).

- Committed `ed866f36` and pushed the branch.
- Opened draft PR #155. Not a bug fix, so no `bug` label.

## Next

- Nothing outstanding. The PR is a draft awaiting review; this session's job on it
  ends there.
- Nothing scheduled or subscribed by this session.
- Unrelated finding worth a separate change: the session started with git configured
  as `Claude <noreply@anthropic.com>`, which AGENTS.md forbids. Set by hand here from
  `.claude/personal/git-identity`; session-start.sh does not apply it.
