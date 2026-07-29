# PR #107 — setup-personal-notes-script (plan `workflow-unification`)

Draft PR #107, based on `claude/patch-pr-rheubx` (PR #101), not on `main` —
user overrode the item's "requires #101 merged" rule. Joins #106 as a second
sibling on that stack; GitHub retargets to `main` when #101 merges.

## Plan

Extract the mechanical half of `/setup-personal-notes` into a script that
needs no session, and shrink SKILL.md to what a script cannot supply.

## Done

- Re-checked the item's central premise and **disproved it**: both steps the
  roadmap called session-only are scriptable (`GET /user`,
  `GET /repos/{owner}/{repo}/labels/{name}`, `POST .../labels`). Verified live.
- `.claude/hooks/github-api.sh` — login, remote→owner/repo, label check/create.
  `gh` first, else `GH_TOKEN`/`GITHUB_TOKEN` + curl, else names both routes.
- `.claude/hooks/setup-personal-notes.sh --remote <name-or-url>
  [--starter-notes] [--create-labels]` — 10 steps, each gated on
  check-setup.sh's TSV verdict, exits with its status.
- SKILL.md 238 → 153 lines; check-setup.sh's stale "session-only" comment
  corrected; 4 new constants; README +11 lines.
- 254 tests pass (was 236 on base). All network- and credential-free via
  stub gh/curl/pip on PATH.
- Two incidental fixes, each its own commit: `current_branch_upstream_remote`
  returning 128 when a branch has no upstream (blocked branch creation
  outright), and the PATH-hiding helper removing `/usr/bin` wholesale.
- Structural changes comment-proposed on issue #102 (not the steward).

## Next

- Watch CI on 3073c4e8. The `test_claude_dev_tooling` failure on the first
  push (2cd9a8e8) was the PATH-hiding bug — fixed and verified locally under
  *both* conditions (gh present and absent) before pushing.
- Still unverified: label **creation** against a real token. This
  environment's is a fine-grained installation token, so `POST .../labels`
  is exercised only through the stub. Flagged in the PR body.
- Leave as draft until told otherwise.
