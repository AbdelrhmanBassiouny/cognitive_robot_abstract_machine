# workflow-unification — roadmap & rationale

Narrative companion to `plan.yaml`. Created 2026-07-29 from the tooling review + implementation
plan worked out in session https://claude.ai/code/session_014DUCCpcvLLLMYszycEBPjP (also condensed
in `pr-progress/claude/stacked-pr-restacking-kz3ptd.md`).

## Why this plan exists — findings of the 2026-07-29 review

The workflow machinery had grown into four storage locations plus a live Routine, with real
duplication and dead weight:

- **Routine prompt duplicated and drifted**: the live Routine at claude.ai/code/routines and the
  copy embedded in `dev/README.md` (lines 147–367 on `claude/stack-workflow-tooling`) had already
  diverged (FINISH section, `cram2-link-sent` wording).
- **Dead/contradictory tooling on the tooling branch**: `.claude/workflows/restack.js` uses the
  Workflow tool and sources local ROS — both forbidden/impossible under the current cloud Routine.
  `dev/README.md`'s hygiene section still instructs `subscribe_pr_activity`, the exact thing the
  Routine's HARD RULES forbid.
- **The round-robin/`stack-turn` subsystem is dead**: `stack.toml` sets `wip_cap = 1000000`
  (deliberate — size/scrutiny predicts review duration better than admission gating), so the
  fairness ordering decides nothing, yet the Routine still stamps/carries turn markers every run
  (prompt tokens + GitHub API writes steering a queue that no longer exists).
- **`claude/session-hooks` superseded**: `main` carries a strict superset of it (+1237/−6) since
  the hooks landed upstream (cram2 #479 lineage); nothing at runtime reads the branch.
- **`cram-notes.md` bloat**: the EQL verbalization living roadmap (~10k tokens incl. 22 review-round
  logs) loads into *every* session on *every* branch — the single largest recurring token cost, and
  exactly the pattern the plan system replaced (`plans/README.md` calls itself "a generalized
  replacement for one-off master-roadmap docs"). `rdr-roadmap.md` also survives as a stale
  duplicate of `plans/rdr-refactor/`.
- **Two dashboard pipelines**: stack board (Pages, auto-refreshing, LOC/CI/conflict chips) vs plan
  dashboards (Artifacts, live-session-only republish, no LOC/CI chips) — two separate
  fetch-PR-state-and-render systems.

What was *not* found: the four-way storage split itself is load-bearing, not accidental. Fork
`main` must mirror upstream (everything on it flows into every stacked branch and up to cram2),
personal data can't be on a merged branch, and the stack-board repo exists because one repo gets
one Pages site and the fork's is taken by docs.

## Target architecture

- **`main` (via cram2, stacked on PR #101)** = all reviewed machinery: hooks, plan skills (already
  there), stack tooling `.claude/stack/{stack.py,ROUTINE.md,README.md}`, `/setup-stacked-prs`.
- **`claude/personal-notes`** = all personal state: conventions (slim), pr-progress, plans,
  `stack.toml` overrides.
- **`stack-board` repo** = the single auto-publishing surface: board + every plan dashboard, one
  Action, one Pages site, LOC/CI chips everywhere.
- **Live Routine** = ~10 lines: inline HARD RULES + "read `.claude/stack/ROUTINE.md` and execute".
- **Retired**: `claude/session-hooks` (now), `claude/stack-workflow-tooling` (after one green
  cycle on the new paths).

## Design decisions (with the reasoning that settled them)

1. **Code on `main`, per-user state as config — not per-user code branches.** A per-user branch
   holding `stack.py` instances has the template-drift problem the personal-notes system avoids by
   holding only data. For cram2, personal stack config lives on the personal-notes branch
   (`.claude/personal/stack.toml`), which `/setup-personal-notes` (PR #101) already creates.
2. **Fork-overlay install mode reconciles portability** (user question, 2026-07-29): for a foreign
   repo whose maintainers won't take `.claude/` tooling upstream, `/setup-stacked-prs` installs the
   same canonical files onto a never-merged tooling branch of the user's fork — today's
   `claude/stack-workflow-tooling` pattern, but created and *updated* by the skill (re-running it
   is the drift fix). So the per-user tooling branch survives as the portability escape hatch, not
   as the cram2 default.
3. **Portability rules**: no repo names outside `stack.toml` defaults + doc examples (PR 1);
   `board.yml` repo/branch/upstream become repository variables (PR 4). Long-term option kept open,
   not exercised now: lift the whole system into a standalone plugin/template repo.
4. **HARD RULES stay inline in the Routine prompt** even after the cutover — they must be in force
   before the Routine's first tool call (a webhook event could arrive before any file is read).
5. **Plan data model and stack data model stay separate.** The board is *derived mechanics now*
   (PR bases + git ancestry); plans are *intent over time* (waves/tracks/deps). Only their
   fetch/render layer unifies (shared `pr_state` module, one Pages site).
6. **Delete the round-robin subsystem rather than fix it** — the WIP cap was disabled deliberately;
   promotion becomes "every ready, non-in-review branch; `bug` is just a label".
7. **PR #101 is tracked but not owned by this plan** — it's the stacking base (`claude/patch-pr-rheubx`)
   and its `prerequisite-check.md` / `ScratchRepository` machinery is reused by PRs 1–2, so its live
   state gates the upstream wave.

## Ordering

```
now:        eql-roadmap-migration, session-hooks-retirement   (independent)
stacked:    PR #101 → PR 1 → { PR 2, PR 3 }
after PR 1–3 on cram2/main + fork main fast-forward:
            PR 4 (stack-board) → routine-cutover → tooling-branch-retirement
```

Interim state is safe by design: until the cutover, the current Routine and board Action keep
running unchanged off the old tooling branch.

## Standing risks

- **cram2 acceptance** of fork-workflow tooling on `main` — precedent is strong (#479, #101
  direction), and PR 1 genericizes by construction, but review may push back on scope.
- **`stack.py` review cost**: 741 pre-AGENTS.md lines; bringing it to repo standards (dataclasses,
  no abbreviations, docstrings, guard clauses, tests) is the slowest-reviewed item. Scope-box PR 1
  to port + delete + standards, not a redesign.
- **Dashboard URL change**: moving plan dashboards from Artifacts to Pages changes their URLs
  (`_generated/dashboard-urls.yaml` becomes legacy); bookmarks need one update.

## Dispatch prompt: setup-personal-notes-script (added 2026-07-29)

Item `setup-personal-notes-script` (stack-tooling track). The user supplied this implementation
prompt verbatim; hand it to the implementing session unchanged. Precondition it enforces itself:
PR #101 must be MERGED first — branch off `main`, never off the PR head.

> **Superseded on implementation — read the 2026-07-29 (night) addendum below before using this
> prompt as a reference.** Two of its statements no longer hold: the "requires #101 MERGED" rule
> was overridden by the user (#107 is based on `claude/patch-pr-rheubx`), and its central
> accounting — that the `get_me` remote-ownership check and the label check genuinely require a
> session — was tested and disproved. The prompt is kept verbatim as the historical record of what
> was dispatched, not as a description of what was built.

```
Extract a deterministic setup script from the /setup-personal-notes skill, in the
AbdelrhmanBassiouny/cognitive_robot_abstract_machine fork.

## Context

PR #101 added `/setup-personal-notes` (.claude/skills/setup-personal-notes/SKILL.md), a
skill that takes a clone from "I have a fork and nothing else" to working personal
notes, PR progress and plan dashboards. Review raised: does this need a skill at all,
or could it be a plain script? The accounting: every mechanical step is already a
script call, and only two things genuinely require a session —

1. deciding whether the resolved notes remote is the user's own fork (needs the
   authenticated GitHub identity via mcp__github__get_me; a git remote URL doesn't say
   who owns it, and getting it wrong pushes someone's personal notes to a repository
   they don't control), and
2. checking the `merged` / `bug` / `in-review` labels exist (GitHub API).

Everything else is either a script invocation or a question with a good default. The
agreed follow-up is to make the mechanical part runnable with no session at all.

This work depends on PR #101 being merged. Branch off `main` once it has; if it hasn't,
stop and say so rather than branching off the PR head.

## What to build

`.claude/hooks/setup-personal-notes.sh --remote <name-or-url> [--starter-notes]`,
performing what are currently the skill's steps 4-7 and 9, in order, non-interactively:

- point `claude.personalNotesRemote` at `--remote`
- create the notes branch via `create-personal-notes-branch.sh`
- seed the notes file from `starter-notes.md` via `write-personal-notes-file.sh`, only
  when `--starter-notes` is passed
- `pip install -r "${PLAN_DASHBOARD_REQUIREMENTS_FILE}"`, reporting rather than
  aborting if it fails (everything except plan dashboards works without it)
- run `session-start.sh` so the current clone picks the notes up
- finish by running `check-setup.sh` and printing its report

Requirements:

- Idempotent, and safe to re-run on an already-set-up clone: each underlying script
  already refuses or no-ops appropriately; preserve that rather than working around it.
- Source `resolve-personal-notes-config.sh` for every path and setting. Do not hardcode
  paths that already have constants there, and add new constants there if you need them.
- Do not duplicate any of `check-setup.sh`'s logic. It stays the single read-only source
  of truth for "is this clone set up?" — call it, don't reimplement it.
- `--remote` is required. Refusing to guess is the entire reason this can be a script:
  the guess is the part that needs a session.
- Fail with a clear message on unknown flags and on a missing `--remote`.

Then shrink SKILL.md to just the session-only parts: resolve whether the remote is the
user's (get_me), ask if it isn't, invoke the script, then do the label check (step 8,
which must keep running even on the already-set-up fast path since `check-setup.sh`
cannot see labels). Note there is no create-label tool in the GitHub MCP server — only
`get_label` — so creation shells out to `gh label create`, and says so plainly when `gh`
is absent rather than pretending it acted.

Update `.claude/hooks/README.md`'s by-hand section to mention the new script, and keep
its length discipline: it was deliberately cut from 378 to ~140 lines, so add lines
only where a reader needs them to act.

## Tests

Add a test module under `.claude/hooks/tests/`, reusing the existing `ScratchRepository`
(tests/scratch_repository.py) and the `scratch_repository` fixture in conftest.py rather
than building a new scratch layout. Cover at least: a missing `--remote` fails; a full
run leaves check-setup.sh exiting 0; `--starter-notes` seeds the file and its absence
leaves it empty; a second run changes nothing. CI already runs
`${HOOKS_TESTS_DIRECTORY}` in the `test_claude_dev_tooling` job, so no workflow change
is needed — but the tests must not need network access or credentials.

## Conventions

Follow AGENTS.md. Specifically: dataclasses, no abbreviations in any identifier, RST
docstrings on every field and method, absolute top-level imports, guard clauses over
nesting. Run `scripts/format_docstrings.py` on every file you touch. Commit as the human
user (their configured git user.name/user.email) — never an assistant identity as author
or committer, and no Co-Authored-By trailer for Claude; a plain "Made with the help of
Claude." line in the body is fine. Open the PR as a draft, include a link to the session
that created it, and subscribe to its activity.
```

## Update 2026-07-29 (late): PR 1 done as draft #106; dev-tooling Python package decided

**PR 1 status**: `stack-tooling-on-main` implemented as draft PR #106 (`claude/stack-tooling-on-main`
on `claude/patch-pr-rheubx`), by session_01Y9egTHHu5RTXmkFL4SwXM9. As planned it ported stack.py
minus the round-robin subsystem, added per-user config layering, made ROUTINE.md canonical, and did
NOT port restack.js or board rendering (deferred to PR 3/4). It landed as plain scripts under
`.claude/stack/` — no package.

**Design decision 8 — a proper dev-tooling Python package** (user-confirmed): all *Python* under
`.claude/` migrates into one proper package with its tests under the standard `test/` directory.
Reasons: PR 3's shared `pr_state` module needs a real import home (same-directory imports between
`.claude/stack/` and `.claude/skills/plan-dashboard/` are path hackery); standard pytest/CI
treatment instead of the special-cased `test_claude_dev_tooling` directory pointer; declared
dependencies instead of a loose requirements.txt; and it strengthens the future plugin/template-repo
lift (decision 3). Boundaries and constraints:

- **What stays in `.claude/`**: SKILL.md files, settings.json, and the bash hook entry points —
  Claude Code discovers all of them by path. They become thin wrappers invoking `python -m` into
  the package.
- **Zero-install must survive**: cloud sessions run on fresh clones with no pip step, so the
  package is a plain top-level directory importable from the repo root (`python -m ...`), with a
  pyproject for *optional* installation (stack-board Action, future plugin lift). No src-layout.
- **Dev-tooling optics for cram2**: own clearly-named directory, not published to PyPI, not part
  of the default install — visibly separate from the robot-stack packages.

**Revised sequencing** (PR 1 shipped without the package, so creation moves to PR 3):
- PR 3 (`shared-pr-state-chips`) *creates* the package and puts `pr_state` in it as its first
  module — the shared import need is what forces it into existence there.
- New item `dev-tooling-python-package` migrates the existing Python (stack.py, the plan-dashboard
  scripts, plan_manifest_tools.py) + all tests into it, last in the upstream wave: it requires
  #101 MERGED (it moves `.claude/hooks/tests/` files #101's diff adds) and PR 3 stable (it moves
  files PR 3 edits).

## Addendum: tag-push and branch-delete are unavailable from a Claude Code session (2026-07-29)

(Restored after a concurrent-save race briefly overwrote it; originally written by the
session-hooks-retirement kickoff session.)

`/plan-item-kickoff workflow-unification session-hooks-retirement` verified the item's premise
(`claude/session-hooks`'s tip is a literal `git merge-base --is-ancestor` ancestor of `main`, safe
to retire) and got a tag-then-delete plan approved and attempted in the same session. Both
operations failed with a real, reproducible `403` through the session's git proxy — creating or
updating a branch works, but `git push <tag>` and `git push origin --delete <branch>` are both
rejected outright. No GitHub MCP tool substitutes either (`create_branch` only creates from a
source branch; there is no delete-branch or create-tag tool). This reads as a deliberate platform
safety boundary against destructive/irreversible ref operations from an agent session, not a
misconfiguration or something to route around.

Consequence for this plan: both `session-hooks-retirement` and `tooling-branch-retirement` (the
same tag-then-delete shape, later in the `cutover` wave) need their tag-push and branch-delete
steps run outside the harness — from the user's own machine, or via `gh api`/a broader-scoped
token — even though everything upstream of that (verification, drafting the tag message, the
plan-manifest update itself) can still run in a session. The retirement was completed by the user
directly: `claude/session-hooks` is deleted (its tip was already an ancestor of `main`, so no tag
was needed); `origin/claude/push-scope-test-zsq7jc` (a diagnostic throwaway, identical to `main`)
still needs the same out-of-harness deletion.

## Addendum 2026-07-29 (night): setup-personal-notes-script implemented as #107; its premise disproved

Written by the implementing session (session_01MyxyUN3bsvPsJnb5QuNzxd), which also edited
`plan.yaml` directly rather than only comment-proposing on issue #102. Under the older
propose-don't-edit convention a non-steward session would have left the manifest stale; the user
has since made keeping plan state current the stronger rule, so state that is already fact gets
written straight into the manifest, with the issue comment kept as the record of *why*.

**Design decision 9 — the GitHub steps in this system do not need a session.** The dispatch prompt
above rested on an accounting that turned out to be wrong, and it is worth correcting explicitly
because the same reasoning was about to be copied into PR 2:

| Believed session-only | Actually |
| --- | --- |
| the authenticated login (`get_me`) | `GET /user` from a plain shell |
| label existence (`get_label`) | `GET /repos/{owner}/{repo}/labels/{name}` → 200/404 |
| creation needs `gh`, since MCP has no create-label tool | true of MCP only; `POST /repos/{owner}/{repo}/labels` has always existed |

`.claude/hooks/github-api.sh` owns these, preferring `gh` when installed and otherwise
`GH_TOKEN`/`GITHUB_TOKEN` with `curl`, failing with both routes named rather than silently doing
nothing. What is genuinely un-scriptable is also out of reach for a session, so neither justifies
one: persisting `CLAUDE_PERSONAL_NOTES_*` for the next fresh clone, and judging whether a divergent
`.claude/settings.json`/`.gitignore` is deliberate. The one real residue is a shell with neither
`gh` nor a token, where the skill's MCP path still works — kept as the documented fallback.

Consequence for PR 2 (`setup-stacked-prs-skill`): mirror this script/skill split, where the skill
keeps only the questions plus the environment-variable step. Do not reserve the GitHub calls for a
session.

**A portability trap worth knowing about, found here.** A Claude Code cloud session's clone has no
`github.com` in its remote URL at all — it is rewritten through a local git proxy
(`http://local_proxy@127.0.0.1:<port>/git/<owner>/<repo>`), and `git config remote.origin.url`
shows the proxy form too. Any code deriving `owner/repo` by matching the real host fails in exactly
the environment this tooling is most used in. `github_repository_of_remote` reads the trailing two
path segments instead, and rejects a local filesystem path outright (a path also ends in something
shaped like `<owner>/<repo>`, and attributing a directory name to a GitHub account would make an
ownership check refuse a valid setup).

**#101's stacking rule, in practice.** Basing on the PR head rather than waiting for the merge was
not a shortcut: `check-setup.sh`, the three `setup-personal-notes/` documents,
`scratch_repository.py` and the `CHECK_SETUP_SCRIPT`/`STARTER_NOTES_FILE` constants all arrive with
#101, so there was nothing to write against `main`. The same is true of `dev-tooling-python-package`
later in the plan, which moves `.claude/hooks/tests/` files — including the four test modules #107
adds.

**Two latent bugs surfaced by having tests at all**, each fixed as its own commit on #107 since the
feature could not work without them:

1. `current_branch_upstream_remote` piped git into `cut`, so under `set -o pipefail` it returned
   git's 128 rather than an empty answer when the branch has no upstream. That aborted
   `create-personal-notes-branch.sh` outright on any branch never pushed with `-u`.
   `fetch_personal_notes_branch` escaped it only by always being called from a condition.
2. The new test helper hid an executable by dropping its whole `PATH` entry — normally `/usr/bin`,
   which also provides `bash`. Invisible on a machine without `gh`, fatal on CI which has one.

**Open, for the developer, not fixed here.** `test_each_lib (coraplex)` fails intermittently for a
reason unrelated to this plan: `test/coraplex_test/conftest.py`'s `pytest_configure` regenerates
`coraplex/src/coraplex/orm/ormatic_interface.py` with no xdist guard, so with `2/2 workers` two
processes rewrite the same ~33.5k-line file concurrently and `ruff format` then fails to parse it.
Analysis posted on #107. Untouched deliberately: different root cause, different package, and
AGENTS.md routes ORM-interface problems via `scripts/regenerate_all_orm.py` or the developer.

## Update 2026-07-30: the upstream wave linearized; PR 2 kicked off

**Decision 10 — the upstream wave is a linear chain, not siblings on #101.** #106 and #107 were
both based on `claude/patch-pr-rheubx`, so neither branch carried both `.claude/stack/*` and
`github-api.sh`. PR 2 (`setup-stacked-prs-skill`) needs both: the stack tooling it sets up, and the
label check/create helpers its setup script calls. Three options were weighed and the diamond was
rejected on mechanical grounds, not aesthetics: `stack.py restack-plan` emits exactly one
`{branch, parent, strategy}` per branch, derived from the pull request's base, so a branch with two
real parents is invisible to the second parent — when that parent moves, nothing restacks the child
onto it. A branch the stack tooling cannot maintain is a poor advertisement for the stack tooling.
So #107 was retargeted onto `claude/stack-tooling-on-main` and #106 merged into it (clean, one
auto-merged file), making the chain `#101 → #106 → #107 → PR 2`. #106 is the parent because it is
un-drafted and promotes first.

**Two scope calls settled at PR 2's kickoff**, both from the item notes conflicting with the
roadmap:

- *stack-board bootstrap*: the item notes say PR 2 "offers stack-board repo bootstrap", but the
  parameterized `board.yml` belongs to PR 4. PR 2 prints the bootstrap steps and the repository
  variables the Action will need, and installs no workflow file — shipping the pre-parameterization
  Action would pull cutover work into the upstream wave and hand PR 4 a file to immediately rewrite.
- *`prerequisite-check.md`*: read as "PR 2 gets its own", not "reuse #101's". What settles it is the
  consumer side rather than the planning prose — `ROUTINE.md`'s SETUP step 0 needs exactly this
  document, with one variation: the Routine must *report* a missing setup rather than offer to fix
  it, since its own HARD RULES forbid asking or entering plan mode.

**Two kickoff plans were produced independently for this item** — one via `/plan-item-kickoff`, one
from a plain prompt — and merged. The comparison is worth recording because the gaps were in the
skill, not in either session: a `done`-only reading of sibling items gathers nothing in a wave where
every item is still in flight, and dependency *readiness* never asks whether the dependency branch
actually carries the files the item builds on. Both are now steps in `plan-item-kickoff`'s SKILL.md
(branch `claude/plan-item-kickoff-workflow-ylk9wu`), along with checking the consumer side before
raising an open question, and ending every proposed plan with the plan-state bookkeeping. The
second plan also caught that `.claude/stack/board.json` is documented as never-committed scratch
while nothing gitignores it — fixed in PR 2, with a `board_ignored` check to keep it true.

## Update 2026-07-30: PR 3 (shared-pr-state-chips) kicked off; package named

Kickoff session: https://claude.ai/code/session_014KoJeaTUxyECZZpfWiVmvr, via
`/plan-item-kickoff`. Branch `claude/shared-pr-state-chips`, based on
`claude/stack-tooling-on-main` (#106's head) as a **sibling of #107 on #106** — decision 10's
linearization was forced by PR 2 needing files from two parents, which doesn't apply here: PR 3
needs only #106's files (`.claude/stack/stack.py`, the `STACK_*` constants; `github-api.sh` is
bash, and `pr_state` fetches in Python with the same dual-backend rule as decision 9).

Two decisions settled with the user at kickoff:

- **The dev-tooling package (decision 8) is named `development_tooling`** — abbreviation-free per
  AGENTS.md ("dev" is an abbreviation), over `dev_tooling`/`claude_tooling`. Flat top-level
  directory, `pyproject.toml` inside the package directory (the repo root already carries the
  workspace meta-pyproject), zero-install import from the repo root preserved.
- **The headless static-site build pushes manifest auto-corrections.** The `build_site.py`
  entrypoint the Pages Action will invoke reuses `refresh_dashboard.sh` per plan, including its
  push of merged→done corrections to the personal-notes branch — the user chose keeping the
  manifest current with no session over a read-only Action.

Interim states this PR deliberately leaves for `dev-tooling-python-package` to clean up:
`stack.py` gets a repo-root `sys.path` insert to import the package, and `build_site.py` lives in
`.claude/skills/plan-dashboard/` next to the render scripts it imports until the migration moves
them into the package together. PR 3's own new tests go straight to
`test/development_tooling_test/` so the migration has nothing to move for them.

## Update 2026-07-30: routine-cutover kicked off — prepared, gated on PR 1 reaching main

Kickoff session: https://claude.ai/code/session_017JMftn3ujp7xsyhwcMaF75, via
`/plan-item-kickoff`. The item's own gate ("only after PR 1 is on cram2/main and fork main
fast-forwards") is **not met yet** — #101 is open (`in-review`, awaiting the cram2 merge) and #106
stacks on its head — so this kickoff prepared everything and execution waits. No timer is armed
(no-scheduled-checks rule); execution happens when the user says go or a session verifies the gate
on request/event.

Findings that shaped the preparation:

- **The live Routine is trigger `trig_01N79jHmLo3bSbg8pLM6MNTB`** ("PR Stack Monitor and Update"),
  found via `list_triggers`. Its 17,392-character prompt still carries the dead round-robin
  subsystem, `dev/` paths, and the tooling-branch pull step. Diffing it against #106's
  `.claude/stack/ROUTINE.md` embedded prompt confirmed the only substantive differences are exactly
  what PR 1 changed (round-robin deleted, promote-all Phase 3 via `next --porcelain`, `dev/` →
  `.claude/stack/`, step 0b deleted) — so ROUTINE.md is a faithful successor and nothing in the
  live prompt needs rescuing beyond what it already contains.
- **The cutover is executable from a session**: `update_trigger` replaces a Routine's prompt in
  place, keeping name/schedule/connectors/email config. The item note "No PR —
  claude.ai/code/routines change" predates knowing this; manual paste stays as the fallback.
- Design calls settled at kickoff (user-approved plan): inline HARD RULES = never-subscribe,
  end-turn-on-webhook-events, and never-plan-mode (all three must bind before ROUTINE.md is read);
  the LABELS-ARE-REPLACE rule stays file-only since label writes can only happen post-read. The
  pointer prompt stops-and-reports if ROUTINE.md is missing from main, never falling back to the
  old tooling branch.

### The approved replacement prompt (paste or update_trigger verbatim at execution time)

```text
You maintain the stacked-PR fork-staging workflow for AbdelrhmanBassiouny/cognitive_robot_abstract_machine.
The full doctrine lives in the repo: read `.claude/stack/ROUTINE.md` on your `main` checkout and execute
the prompt embedded in it, exactly as written there. If that file is missing from `main`, STOP and report
that instead - never fall back to another branch or to a remembered older copy of the doctrine.

HARD RULES, in force from this line onward - before any file is read or any tool is called - and
overriding ROUTINE.md if the two ever disagree:
- NEVER call `subscribe_pr_activity`, and never stay subscribed - you learn CI by POLLING.
- If a review, review-comment, issue-comment, or any `<github-webhook-activity>` event is ever delivered
  to you, your ONLY valid action is to END THE TURN immediately. The one exception is a CI/check *status*
  you were polling for your own restack.
- NEVER enter plan mode or post a "here's my plan" comment. You either perform a mechanical step from
  ROUTINE.md or you stop; you never open a discussion.
```

### Execution checklist (any session can run this once the gate is met)

1. Verify the gate — the cram2 remote is outside a session's repo scope, but the routine
   fast-forwards fork main from cram2/main, so `origin/main` is the observable:
   `git fetch origin main claude/stack-tooling-on-main && git merge-base --is-ancestor
   origin/claude/stack-tooling-on-main origin/main`, plus
   `.claude/stack/{ROUTINE.md,stack.py,stack.toml,README.md}` all present on `origin/main`.
2. Re-read `origin/main`'s ROUTINE.md once — later PRs may have evolved it (the pointer design
   absorbs that), but its embedded HARD RULES should still match the inline ones above.
3. `update_trigger` with `trigger_id: trig_01N79jHmLo3bSbg8pLM6MNTB` and `prompt:` the text above
   (touch nothing else on the trigger).
4. After the next natural routine run, confirm from its email/summary that it read ROUTINE.md and
   ran the phases normally, then set the item `done` (unblocking tooling-branch-retirement),
   `save-plan.sh`, republish the dashboard.

Two wording nits flagged to fix on #106 before it merges (relayed to the user, not acted on from
this item): ROUTINE.md's header says "This file becomes the one to **paste into**
claude.ai/code/routines" and README.md echoes "paste it (or its successor)" — both should describe
the pointer design instead; and ROUTINE.md's "Not live yet" paragraph goes stale at cutover.

Also restored in this same save: PR 3's kickoff state (manifest + the roadmap section above),
which a concurrent stale-scaffold save (bdd0beaa, 14:49) had silently reverted five minutes after
it was recorded (973ff31a, 14:44) — the second occurrence of this race; the first is noted in the
2026-07-29 tag-push addendum.

## Update 2026-07-30: personal settings sync joins the personal-data track (PR #109)

New item `personal-settings-sync` (`claude/local-settings-dashboard-sync-8sx0tf`, PR #109,
session_0167iZiWUnXizpKSqa7xf5rC), added at the user's request after the work was already built
and open.

**What it adds.** The personal-notes branch can now also carry `.claude/personal/settings.local.json`,
which `session-start.sh` copies to the project root's `.claude/settings.local.json` — the file
Claude Code itself reads as local settings. Seeded with a rule allowing the `Artifact` tool
without prompting, so plan dashboards publish without a permission prompt each session.
`save-personal-settings.sh` is the write half, delegating its commit/push to the existing
`write-personal-notes-file.sh`. The same session also added a personal-notes rule that any session
changing a plan's data republishes that plan's dashboard in the same turn — notes-branch only, no
PR, and the direct reason this item exists as a tracked one rather than a loose change.

**Why `personal-data` and not `stack-tooling`** (user's call, offered three options): the target
architecture already names `claude/personal-notes` the home for *all* personal state, and this is
that — config rather than data, but the same home and the same mechanism. It is also genuinely
independent of the #101 stack: branched off fork `main`, not on the chain, so putting it in the
upstream track would have broken that track's one-linear-chain property (decision 10) for no gain.
The consequence is that the `personal-data` track is no longer only about *slimming* the notes
branch; it is personal-notes data and config generally. The track keeps its name, and the item
records the widening.

**Not a dependency, but a merge to expect.** Three open PRs touch the same two files:
`#107` adds path constants to `resolve-personal-notes-config.sh`, `#110` makes
`write-personal-notes-file.sh` delegate to a new `write-branch-files.sh`, and `#109` adds its own
constants to the first and calls the second. None of them needs the others to work, so no
`depends_on` was added — whichever lands second resolves a textual overlap in files both already
edit. Worth knowing before restacking anything, not worth serializing the work over.

**Deliberate deviation from a plain copy.** Claude Code writes permission grants into
`.claude/settings.local.json` itself whenever the user picks "don't ask again", so an
unconditional copy every session start would silently drop them. The hook writes only when the
file is absent or unchanged since it last synced, tracked by a hash stamp in the gitignored
`.claude/.personal-settings-sync-hash`; otherwise it keeps the local file and says so in its
session-start summary, and `save-personal-settings.sh` re-stamps so syncing resumes. This is the
one place the settings round trip is not symmetric with the notes round trip, and it is the reason
why.

## Update 2026-07-31: GitHub native stacked-PRs preview - evaluation, live prototype, findings

GitHub shipped stacked pull requests as a public preview (server-side cascading rebase, `gh stack`
CLI, stack webhooks/REST/GraphQL, stack map UI). Evaluated against this plan's stack tooling in
session https://claude.ai/code/session_015db4P7UfiFTTfrbxYjU5yW, then verified by a live prototype
on throwaway `proto-*` branches in the stack-board repo (its `main` untouched; a throwaway branch
served as trunk). The user had already created **Stack #112** on the fork - the seven D-core PRs
(#41→#63→#64→#65→#66→#67→#98) adopted post-hoc into a native stack trunked on
`ripple-down-rules-refactor` - which by itself proved the preview is enabled, post-hoc adoption
works, and a non-default trunk works.

**User decisions recorded before the prototype:**

- **One dashboard only.** The plans dashboard (with its buttons and suggested next actions) is the
  single surface; the stack-board visualization dies - GitHub's stack map covers derived
  mechanics. Every fork PR must belong to a plan, which the dashboard build can enforce by
  flagging unclaimed open PRs.
- The gain sought from GitHub is the stacking *mechanics* via API, and slimming the Routine -
  possibly down to a plain GitHub Action.

**Prototype findings (all verified live, not from docs):**

1. **Reads work from a session.** The PR resource carries a `stack` object
   (`id`/`number`/`size`/`position`/`base{ref,sha}`) and `GET/POST /repos/{o}/{r}/stacks`,
   `GET /stacks/{n}`, `POST /stacks/{n}/add`, `POST /stacks/{n}/unstack` all work with the
   session's fine-grained installation token under `X-GitHub-Api-Version: 2026-03-10`. GraphQL is
   unusable from a session (the git-proxy token serves only a pinned set of PR-review queries), so
   `pr_state` must use REST.
2. **Create/extend/dissolve verified.** Bottom-to-top `pull_requests` list; a draft PR is accepted
   as a stack member; creating a stack on stack-board proves the preview is account-wide, not
   per-repo. A stack whose open PRs are all removed (only merged members remain) auto-closes.
3. **The cascade is the one gap.** Pushing new commits to a lower branch does *not* auto-rebase
   the branches above (verified over ~5 min), and no REST endpoint triggers the server-side
   cascade (`rebase`/`sync`/`restack`/`update`/`cascade`/`rebase-async` variants all 404;
   `PUT /pulls/{n}/update-branch` is explicitly 403 "Merging stacked PRs via this API is not
   supported. Use the web interface instead."). Server-side cascade = UI button only; automation
   does a *local* cascading rebase + `--force-with-lease` push, which preserves stack membership
   (verified) - i.e. exactly what stack.py restack already does, minus deriving the order, which
   now comes free from the stack object.
4. **Merging is a new async API and it is good.** Classic `PUT /pulls/{n}/merge` hard-403s for
   stacked PRs - including through the GitHub MCP server's merge tool, so the Routine/tooling
   *must* adopt `PUT /pulls/{n}/merge-async` → poll `GET /pulls/{n}/merge-async/{uuid}`
   (result retained 24h). Verified: merging mid-stack PR #2 merged #1+#2 into the trunk in one
   operation and auto-retargeted the draft above to the trunk within seconds. A stale stack is
   refused with a precise reason ("PR #2's branch is not a linear descendant of PR #1's branch"),
   and a draft refuses with "Pull request is in draft".
5. **Conflicts surface conventionally.** A trunk commit conflicting with an upper layer shows as
   plain `mergeable: false` / `mergeable_state: dirty` on that PR - no special stack state. The
   stack's `base.sha` lagging the real trunk head is a machine-readable "needs cascade" signal.
6. **Events carry the stack.** `pull_request` webhook/Actions payloads include
   `.pull_request.stack`; the post-merge retarget arrives as an `"edited"` action. An Action can
   key on stack membership without deriving anything.

**Consequences per open item** (decisions for the user, not yet made):

- `stack-tooling-on-main` (#106): restack-order derivation and promote mechanics shrink - the
  stack object is authoritative for structure, merge-async replaces any merge path, and the MCP
  merge tool must not be used on stacked PRs. The local rebase+push loop survives as the cascade
  executor. Pivot-now vs land-then-migrate is the open call.
- `setup-stacked-prs-skill` (#110): setup shrinks to labels + stack.toml + (optionally) creating
  the stack via API; fork-overlay mode demotes to a fallback for repos without the preview.
- `stack-board-single-site`: re-scoped by the user's one-dashboard decision - plans-only Pages
  site, no board index; add the every-PR-in-a-plan invariant check to the build.
- `routine-cutover`: the endgame candidate is stronger than "slim the Routine" - deterministic
  duties (fork-main fast-forward, labels, cram2-link comment, site build, happy-path cascade via
  local rebase) fit a plain scheduled Action; the LLM residue is cascade *conflicts* and red CI
  after a restack, which could become on-demand sessions instead of any scheduled LLM run. This
  would finally align the Routine with the no-scheduled-checks rule.
- Unchanged: the fork→cram2 hop was never a stack (cross-fork stacks unsupported) - promotion
  doctrine, label hygiene and fast-forward stay ours; the plan system and dashboards are
  untouched by the preview.

**Leftovers from the prototype:** stack-board carries closed throwaway PRs #1-#5 (two merged into
`proto-trunk`, which is itself throwaway) and the branches `proto-trunk`, `proto-layer-1..4` -
branch deletion needs the user (session branch-deletes 403, the standing platform constraint).
Stack #4 there is closed. Nothing on the fork was touched beyond reads.

## Update 2026-07-31 (later): pivot approved and recorded; round-2 probes; the reparent hazard

The user approved the recommendation set from the evaluation session
(https://claude.ai/code/session_015db4P7UfiFTTfrbxYjU5yW): #106 lands with one trim commit rather
than a re-scope or a pure land-then-migrate; #110 and #111 amend while still drafts; PR 4 becomes
plans-only; routine-cutover's endgame becomes a deterministic Action + on-demand sessions with no
scheduled LLM. Item notes updated accordingly; the plan description now reflects the one-dashboard
decision and the Action endgame.

**Round-2 probes (same throwaway proto-* branches on stack-board), run for the Routine audit:**

1. **The audit itself came back clean on merges**: neither the live Routine's doctrine (embedded in
   `dev/README.md` on the tooling branch) nor #106's ROUTINE.md ever calls the classic merge API or
   `update-branch` on fork PRs — fork-side "merged" is the git-ancestry test + `merged` label +
   close, and restacks are plain git. No latent 403 there.
2. **But Phase 1's REPARENT is broken for stack members**: `PATCH /pulls/{n}` with a new `base`
   fails 422 — "Cannot change the base branch because the pull request is part of a stack." Both
   doctrines do exactly this when a parent lands. With Stack #112 already wrapping the D-core
   chain, the first cram2 landing of a D-core branch hits this. The trim commit on #106 must
   special-case it; until then the recovery is manual (UI Rebase-stack button) or the API-only
   sequence below.
3. **Push-based merges do not auto-retarget children.** Merging the bottom branch into the trunk by
   push (the fork's fast-forward-from-cram2 pattern) marks the bottom PR merged immediately, but
   the PR above keeps its old base — unlike merge-async, where retargeting is automatic within
   seconds. So the reparent duty survives in our flow even with native stacks.
4. **The API-only recovery works**: unstack the affected PR (`POST /stacks/{n}/unstack`), then
   `PATCH` its base, then re-stack. Verified live. Note unstacking down to only-merged members
   auto-closes the stack, so re-stacking may mean creating a fresh stack.
5. **Reopened + previously-closed PRs stack fine** (stack #6 was built from two reopened PRs).

**From the "Managing stacked pull requests" doc (user-supplied):** the server-side cascade is the
"Rebase stack" button in the merge box (UI-only, confirming the API gap; its commits are
*unsigned*); `gh stack rebase`/`push` is the local cascade; and `gh stack sync --prune` is
documented as **safe to run in automation** — it fetches, fast-forwards the trunk, rebases the
remaining branches onto it, force-pushes, and syncs PR status, aborting cleanly on divergence in
non-interactive terminals. Actions runners ship `gh`, so the cutover Action's cascade step can be
`gh stack sync` rather than a hand-rolled rebase loop. `gh stack modify` handles restructuring;
unstacking from the website removes open/draft/closed PRs but merged/queued ones stay.

**Chain adoption (recommendation 3) is left to the user**: creating the stack for
#101 → #106 → #107 → #110 from a session was blocked by the permission layer, and given finding 2
it should follow — not precede — comfort with the reparent story. It's the same "Add to stack" flow
used for #112, or `gh stack` locally. #111 cannot join that stack (it's a sibling of #107 on #106;
stacks are strictly linear) and stays loose; #109 is independent by design.

## Update 2026-07-31 (adoption): the upstream chain is Stack #114; unstack means dissolve

The user adopted the chain via the UI, but the "Add to stack" flow picked #111 (a valid linear
continuation from GitHub's perspective, since it also targets #106's head) instead of #107 —
producing Stack #113 = #101 → #106 → #111, which blocks #107/#110 from ever joining. Fixing it
from the session surfaced a correction to round-2 finding 4: **`POST /stacks/{n}/unstack` takes no
body and has no selective mode — it dissolves the stack** (removes every open/draft/closed member;
merged members stay, per the docs' website-unstack description). The `pull_requests` body it was
called with was silently ignored. This retroactively reinterprets the stack-board probes (stacks
#4/#6 "auto-closing" after selective unstack were in fact full dissolutions), and it narrows the
reparent recovery: the API-only sequence is dissolve → PATCH base(s) → re-create the stack, not a
surgical removal. `gh stack modify` is the only surgical restructuring tool.

Outcome: Stack #113 dissolved, **Stack #114 created with the intended sequence
main → #101 → #106 → #107 (draft) → #110 (draft)**; #111 verified untouched (open draft on
#106's head, stack: null — it cannot join, as a sibling of #107; its restack remains stack.py's/
gh's job). The upstream wave is now natively stacked, so #101's cram2 landing will exercise the
push-merge/reparent path for real — the "Rebase stack" button or gh stack sync is the recovery
until #106's trim commit lands. Also noted: fork-side stack writes from a session worked this
round (create/unstack on the fork repo); the earlier same-call denials were permission-layer
variance, so treat session-side stack surgery as possible but not guaranteed.

## Update 2026-07-31 (routine patch): update_trigger is unavailable for this Routine — manual paste only

The approved interim amendment (Phase 1 native-stack special case) was drafted and its application
attempted via `update_trigger`, which the platform refused: the live Routine was created via the
web UI ("http_api"), and agents may only update Routines they created themselves (an agent-created
trigger would be updatable; this one is not). This corrects the 2026-07-30 kickoff finding that
"the cutover is executable from a session" — for this trigger it is not; **manual paste at
claude.ai/code/routines is the mechanism for both the interim amendment and any future prompt
cutover**. The amendment text (appended to the otherwise-unchanged 17.5k-char live prompt) was
handed to the user as a file; its content is: detect stack membership via the `stack` object under
API version 2026-03-10; never classic-merge/MCP-merge a stack member; Phase 1 reparent for stacked
children = record stack composition → dissolve (`unstack`, no body) → PATCH bases → normal local
restack → re-create stack; stop-and-report on any unexpected API behavior.

## Update 2026-07-31 (cut): decision 11 — #106 cuts the restack subsystem instead of trimming it

User decision, prompted by an explicit reassessment ask ("fastest and simplest while reliable,
clean, and minimal cram2 review effort"). The trim commit approved earlier the same day kept the
restack engine with a stack-API-primary/PR-base-fallback split; the reassessment concluded the
fallback's only remaining justification (repos without the stacks preview) is YAGNI — the preview
is account-wide for the user, cram2-the-org is never stacked on directly, and the old tooling
branch survives as a tagged archive if a preview-less repo ever materializes. Since the plan's own
named slowest-review risk was stack.py's 741 lines, cutting the engine is simultaneously the
fastest path through the actual bottleneck (cram2 reviewer time) and the most reliable one (GitHub
maintains the mechanics; we maintain policy).

What #106 keeps: ROUTINE.md rewritten around native mechanics — stack object as structure source,
merge-async + poll as the only merge path, base.sha-lag staleness, the Phase-1 reparent special
case (record → dissolve → PATCH bases → restack → re-create) — plus stack.toml and per-user config
layering, the label/cram2-link helpers, a small reparent-recovery script, and tests. What it drops:
restack-plan, next, status/structure derivation. Knock-ons recorded on setup-stacked-prs-skill
(nothing to install beyond doctrine + labels + config + optional stack creation) and
shared-pr-state-chips (the stack.py export interplay may vanish). Instructions were posted as
comments on #101, #106, #107, #110, and #111 so each owning session receives them as events.

## Update 2026-07-31 (conventions): delta recheck, comment routing, merged-branch cleanup

Three conventions recorded in cram-notes.md at the user's request, after the question "is the
tracking-issue subscription enough?" was answered no — the manifest is the primary state channel
and pushes to the notes branch emit no events, so subscription covers only the structural subset
that gets commented:

1. **Recheck deltas, don't reread**: sessions recheck plan/tracking-issue updates when prompted
   after idling, when starting a new task, and always immediately before a `save-plan.sh` write
   (the anti-stale-save rule; two silent reverts on record). Mechanics: stamp the last-seen
   notes-branch SHA, then read `git diff <sha>..FETCH_HEAD -- plans/<id>/` and only
   newer-than-stamp issue comments.
2. **Comment routing**: the tracking issue always carries the structural record; a PR gets a
   comment only when its owner must act or its review context materially changes. (Assessment of
   the 2026-07-31 five-PR broadcast: #106/#110/#111 warranted, #101 borderline, #107 noise.)
3. **Merged/closed branch cleanup**: the owning session unsubscribes, deletes armed
   triggers/check-ins referencing the branch, and stops all related polling the moment its PR
   merges or closes.

New item `plan-updates-since-helper` (personal-data track) implements convention 1 as a hook
script with a session-start SHA stamp; small independent PR off fork main, like #109.

## Update 2026-07-31 (adoptions): the two open dashboard bug-fix PRs join the plan

Asked why `plan-updates-since-helper` was missing from the "Ready to start" sidebar, the answer
turned out to be a known bug with a fix already in review: **#103** (ready-to-start drops
dependency-free items - the exact `_compute_next_steps` guard diagnosed live in the session) and
its sibling dashboard fix **#105** (unmet dependency chips shown as blocked). Both predate the
one-dashboard decision, are based on fork main, and carry `bug` + `in-review`. Adopted as
`ready-to-start-dependency-free-fix` and `dependency-chips-blocked-fix` in the dashboards track -
the first exercise of the "every fork PR belongs to a plan" rule, which the PR-4 site build will
later enforce mechanically. Practical note: the sidebar gap remains visible on published
dashboards until #103 lands on fork main, since the build runs main's copy of
build_dashboard.py.

## Update 2026-07-31 (kickoff): plan-updates-since-helper kicked off

`/plan-item-kickoff workflow-unification plan-updates-since-helper`, this same session
(https://claude.ai/code/session_01UrxbEr6ZHMThA2p4Vcnrqv). Confirmed live: `origin/main`
(`0fd14357`) has no `.claude/hooks/github-api.sh` - it exists only on PR #107's branch,
which this item does not depend on - and `.claude/hooks/tests/` on `main` still has only
the original minimal `conftest.py` (bare `sys.path` insert), not either sibling's shared
scratch-project/stub-executable scaffolding (#109's `ScratchProject`, #107's
`ScratchRepository` + `stub_executables.py`). Consequences for the design:

- The tracking-issue-comments GitHub call this item needs is implemented inline, in the
  same gh-preferred/curl+token style `github-api.sh` already uses on #107's branch, rather
  than sourcing that file (it isn't reachable from fork main yet). A follow-up once #107
  lands can dedupe the shared credential/repo-resolution helpers; out of scope here.
- Tests build their own minimal scratch-repo + stubbed-`gh`/`curl` fixtures locally in the
  new test module, matching the shape `test_save_plan_sh.py` already has on `main` today,
  rather than depending on either sibling's shared fixture module landing first.

**Basing decision, asked and confirmed by the user**: based directly off fork `main` (not
stacked on #109), matching this item's own note "small independent PR off fork main, like
#109" - read as "the same *kind* of independent PR #109 is", not "on top of #109's
branch." A textual overlap with #109 is expected in the same two files this item also
touches (`resolve-personal-notes-config.sh`, `session-start.sh`) - same shape, and same
no-`depends_on` treatment, as the #107/#109/#110 shared-file overlap already on record
above: whichever lands second resolves it, nothing serializes over it.

**Design point flagged, not settled fact**: `session-start.sh` stamps the notes-branch SHA
unconditionally on every successful fetch, not only when the current branch resolves to a
plan via `plan_id_for_branch` - cram-notes.md's wording ("stamps the SHA it loaded plan
state at") only strictly requires the latter, but the broader reading matches "so sessions
have the baseline for free" better (this very kickoff session read plan state manually on
a branch with no plan of its own) and costs nothing extra, since `fetch_personal_notes_branch`
already always fetches the whole branch regardless.

Implemented as draft PR #115 same session: `PLAN_STATE_SYNC_STAMP` +
`record_plan_state_sync_stamp`/`last_recorded_plan_state_sha` in
`resolve-personal-notes-config.sh`; an unconditional stamp call added to
`session-start.sh` (with a `plan state SHA:` summary line); the new
`plan-updates-since.sh <plan-id> [--since <sha>]`; `.gitignore`/`README.md`
updates; and `test_plan_updates_since_sh.py` (13 tests) with its own minimal
scratch-repo fixture and stubbed `gh`/`curl` executables, matching the shape
`test_save_plan_sh.py` already has on `main` rather than either sibling's
not-yet-landed shared fixture. All 29 tests under `.claude/hooks/tests` pass.
Verified live: ran `plan-updates-since.sh workflow-unification --since
1faf0f52` against the real personal-notes branch and tracking issue #102, and
its printed diff matched a manual `git diff` exactly.

Two real bugs the tests caught before they shipped: (1) the comment-printing
Python snippet used an f-string with a backslash-escaped quote inside the
expression part - invalid syntax before Python 3.12, and the `pytest` install
actually available in this session's environment is 3.11, so this was worth
fixing outright rather than working around; (2) the `default_repository` grep
had no `|| true` guard (unlike the `tracking_issue` one right above it), so a
plan with `tracking_issue` set but no `default_repository` field made `grep`
exit 1 with no match, which `set -e`/`pipefail` turned into the whole script
dying silently - no stderr message, no explanation - instead of reaching the
explicit guard-clause error a few lines later. Caught by
`test_tracking_issue_without_default_repository_fails_clearly`, which without
the fix saw an empty stderr instead of the intended message.

## Update 2026-07-29 (merge): ready-to-start-dependency-free-fix landed

PR #103 merged 2026-07-29. Session
https://claude.ai/code/session_016mfBqcBibxA7Wa5eNfWtoL drove it from adoption through
merge: TDD-added `test_dependency_free_not_started_item_is_ready_to_start` (proved the
bug live, `assert [] == ['a']`, before the one-line fix removing the `not dependencies`
short-circuit in `_compute_next_steps`) and a companion pinning that a dependency-free
`BLOCKED` item still lands in neither list. Two pre-existing tests turned out to have an
incidental dependency-free `NOT_STARTED` fixture item that legitimately became
ready-to-start under the corrected semantics once the guard was fixed; rather than touch
either test's assertions, that fixture item's status was changed to `BLOCKED` so each
test keeps isolating only the behavior its name describes (the item it was actually about
- "b" was only ever there as an unready dependency for a different item under test). Full
`.claude/skills/plan-dashboard/tests/` (189) and `.claude/hooks/tests/` (16) suites green.
Opened as draft, `bug`-labeled, subscribed to PR activity per the personal-notes
conventions; the developer marked it ready for review shortly after. One CI red
surfaced along the way - `test_each_lib (semantic_digital_twin)` failing on
`test_world_sim_state_sync`, a Mujoco box-drop physics-settling assertion wholly
unrelated to this diff - noted once on the PR as pre-existing/unrelated per convention,
and it cleared on the next automatic re-run (an out-of-session `origin/main` merge commit
landed on the branch mid-review, authored `Claude <noreply@anthropic.com>`, not something
this session pushed). No review comments arrived before merge. This is the plan's first
completed exercise of the every-fork-PR-belongs-to-a-plan adoption rule from item to
merge.

## Update 2026-07-31 (landed): PR #101 merged — the upstream wave's base is on fork main

`setup-personal-notes-pr101` is **done**: merged into fork `main` at 10:36:43Z (head
`90f69f56`). Verified by presence on `main` rather than from the merge notification alone —
`.claude/skills/setup-personal-notes/SKILL.md` and `.claude/hooks/check-setup.sh` both
`git cat-file -e` clean on `origin/main`.

**Consequences for the plan.** This was the base of the whole upstream chain
(#101 → #106 → #107 → #110, natively Stack #114), so GitHub retargets the chain upward and
`setup-personal-notes-script` (#107) — the item whose dispatch prompt originally required
"#101 MERGED first", a rule the user overrode to let it be based on the PR head — now has
that precondition satisfied retroactively. `dev-tooling-python-package`, whose dependency was
recorded as *stronger* than the open-and-ready rule because it moves `.claude/hooks/tests/`
files this PR's diff adds, is likewise unblocked on that count. And the deferred follow-up
below is now runnable.

**The agreed follow-up, now unblocked.** Review asked whether `/setup-personal-notes` needs to
be a skill at all. The accounting: every mechanical step is already a script call, and only two
things need a session — deciding whether the resolved notes remote is the user's own fork
(needs the authenticated identity; a git remote URL doesn't say who owns it) and checking the
labels exist. The user settled it as a **follow-up, not part of #101**: extract
`.claude/hooks/setup-personal-notes.sh --remote <name-or-url> [--starter-notes]` covering skill
steps 4-7 and 9, shrinking the skill to those two session-only parts. A full kickoff prompt was
handed over in-session. Note this is the same conclusion decision 9 reached independently on
#107 (2026-07-29 night addendum) — that the GitHub steps in this system do not need a session —
so whoever picks it up should read that addendum first: the remote-ownership check is scriptable
via `GET /user`, which narrows the skill's residue further than the review discussion assumed.

**What #101 ended up containing beyond the original patch**, since the plan tracked it as
"the patch, unchanged": the hooks README rewritten as a step-based guide (378 → ~140 lines,
with the worked example surfaced in a callout at the top), a skill step checking the
`merged`/`bug`/`in-review` labels exist in the fork and offering to create them (no create-label
tool exists in the GitHub MCP server — only `get_label` — so creation shells out to `gh`), and a
review round that moved the verbatim-duplicated hook-test scratch repository onto a shared
`ScratchRepository` dataclass plus a `conftest.py` fixture, and replaced the stringly-typed
check-setup report with `SetupCheck`/`CheckStatus` StrEnums and `CheckResult`/`SetupReport`
dataclasses.

**Two standing hazards this item re-confirmed.** Three merge commits authored *and* committed as
`Claude <noreply@anthropic.com>` landed on this branch from outside any session — the same
pattern as `6b51075e`/`f5d1c883` on the P3 branch, and against AGENTS.md's Version Control rule.
Each was verified content-neutral for the PR (`git diff <old>..<new> -- .claude/` empty, branch
diff unchanged at 21 files/+1598/−434) and left unrewritten, since fixing authorship means
force-pushing shared history unilaterally. Separately, the robotics CI jobs flaked repeatedly on
this `.claude/`-only PR — `test_world_sim_state_sync` and
`test_attached_self_collision_avoid_stick`, each proven unrelated (the latter by the giskardpy
job flipping pass→fail across a diff of three documentation files) — and the user instructed
these be ignored rather than investigated on this PR.

## Addendum 2026-07-31 — the orphaned-child bug, found from the PR #41 side

`landed-parent-detection` was not planned work. It surfaced while a session handled a review
round on PR #41 (`rdr-backward-inference`), which had been sitting on a base branch,
`ripple-down-rules-refactor`, whose content had long since landed on `main`. Merging `main`
into #41 to satisfy the review blew its Files-changed view up from 7 files to 268
files / +27,825 — none of it real, all of it an artifact of a merge-base measured against a
stale base branch.

**Why the routine never caught it.** Phase 1 reparents children of "each OPEN fork PR that is
merged by ancestry". PR #40, the one whose head is `ripple-down-rules-refactor`, is *closed,
not merged* — its content reached `main` by another route. So Phase 1 never looked at it, and
#41 was left parented to a landed branch. The same blind spot sits in `stack.py`: `board.json`
holds only open PRs, so `by_name.get(branch.parent)` returns `None` for that parent, and both
`restack_plan` and `parent_landed` interpret the `None` as "there is no parent" — the first
leaving the child on its stale base, the second treating the child as an unblocked root and
clearing it to promote ahead of a parent that may not have landed at all.

The fix is to stop inferring landedness from board membership. The doctrine already defines
`merged` as `git merge-base --is-ancestor origin/B cram2/main`, which answers for *any* branch
name; the code simply never used it outside the board. `Stack` now carries that predicate and
exposes `has_landed_upstream()`, and both call sites ask it instead.

**What this says about the board as a data source.** `board.json` is a projection of open PRs,
not of the branch graph, and every question of the form "what is true about this branch" that
gets answered from it inherits the same hole. `stack_root()` in the `dev/` copy has the same
`by_name.get(...) is None` shape; it was left alone because it feeds only the round-robin/WIP-cap
subsystem, which `stack-tooling-on-main` deletes outright. Worth remembering if any future
question gets answered from board membership rather than from git.

**A premise that turned out to be wrong.** PR #89's description predicted the restacking bot
would "cascade it down through code-extraction → code-generation-extract →
ripple-down-rules-refactor → rdr-backward-inference without a manual conflict resolution on
#41". It could not have: the cascade stops at the first parent whose PR is closed rather than
merged, which is exactly where this chain breaks.

**The 422 has teeth now.** Retargeting #41 to `main` — the correct repair, and the one Phase 1
prescribes — is refused with `422 - Cannot change the base branch because the pull request is
part of a stack`, the hazard `native-stacks-prototype`'s round-2 probes recorded. #41 is not the
stack tip: #63 → #64 → #65 → #66 hang off it, so GitHub's documented recovery (Unstack, retarget,
`gh stack submit`) would dissolve and rebuild a six-PR stack to fix one PR's diff. Phase 1 now
treats the 422 as report-and-continue and explicitly forbids unstacking as a mechanical step;
the FINISH summary lists the stuck PRs so they can be retargeted by hand. #41 itself is left as
found, awaiting that decision — its review round is resolved and its code is correct either way.

### Reversal within the same item: the stack-member 422 is worked around, not reported

The first revision of `landed-parent-detection` told the routine to treat the reparent 422 as
report-and-continue and explicitly forbade unstacking, reasoning that dissolving a stack is too
destructive for a mechanical step. The user rejected it with one sentence — *we want to merge the
problematic branch to main; fast-forwarding its base doesn't retarget it to main* — and that is
decisive. The reparent's purpose, in the doctrine's own words, is that the child stacks on main
"not on a branch about to disappear"; the inflated diff is a symptom. Deferring the reparent does
not make it optional, it leaves the child unable to land and due to be closed when Phase 1 deletes
its base, while the now-working orphan detection re-reports the same PR every run. And "retarget it
by hand" resolves to a human performing the identical dissolve-and-recreate through the UI, so the
rule never avoided the destructive operation — it only moved who performs it.

Two things this settles for the future:

- **The live Routine's `AMENDMENT 2026-07-31` was right, and `ROUTINE.md` now matches it** rather
  than contradicting it. Worth noting the near-miss: the amendment was pasted into the live prompt
  the same morning, and the first revision of this item was written without reading it, so the two
  canonical copies of the doctrine briefly disagreed on a destructive operation. Read the live
  prompt before changing `ROUTINE.md` until `routine-cutover` collapses them into one copy.
- **Fast-forwarding a landed base branch to `main` is rejected as a general technique**, not just
  here. It moves the merge-base so the diff renders correctly while the child still targets a
  disappearing branch, and when that base is a stack's trunk — as `ripple-down-rules-refactor` is
  for Stack #112 — it desynchronises the stack's recorded `base.sha` from its real head, which the
  prototype recorded as GitHub's own staleness signal. It was offered for PR #41 before the stack
  trunk relationship was noticed.

The reparent duty also survives `routine-cutover`: the fork→cram2 hop is not a stack, fork branches
land by push/fast-forward, and round-2 probing established that push-based merges are detected as
merged but do **not** auto-retarget children — only `merge-async` does. `gh stack modify` is the
surgical alternative to dissolving, but the docs describe it as interactive, so it is unavailable
to an unattended Action or Routine.

##### Update 2026-07-31 (night): the dashboard's own drift flags were the bug (#119)

The dashboard raised two drift flags against this plan — `#103` and `#105` "marked done, but pull
request #N was closed without merging" — for two pull requests GitHub records as **merged** at
`2026-07-31T10:36:43Z`, the moment fork `main` fast-forwarded from cram2 and GitHub auto-detected
both branches. The timeline shows them open until that instant, so a merely stale fetch could only
ever have said *"still open"*; "closed without merging" had to come from the data.

It did. `classify_live_state` has exactly two merge signals: GitHub's `merged_at`, or the
hand-applied `merged` label. The published page rendered `#101` — merged in the same second — as
`Merged` purely because it carries that label, while `#103`/`#105` (labels `bug`, `in-review`) fell
through to closed-unmerged. So the `pr_data.json` behind that build had `state: "closed"` and no
`merged_at` for all three.

`pr_data.json` is assembled by a session from `list_pull_requests`, whose `fields` parameter lets
the caller drop fields, and `pr-data-fetching.md` only ever insisted on `labels`. That is per-run
variance, not a state change: the same morning's `sync_manifest_status.py` run read both as merged
and auto-corrected them to `done` (`Auto-sync workflow-unification: 2 item(s) to done`). A doc line
alone would not have prevented it, so `#119` makes the contract enforceable — a closed entry
without the `merged_at` key is now a `MissingMergeTimestampError`, while key-present-and-`null`
stays the genuine closed-unmerged case.

Two things this settles:

- **The `merged` label is a fallback for a merge GitHub never recorded, not a redundancy for
  `merged_at`.** It masked this bug on exactly one pull request and hid it on the other two; a
  fetch that drops the timestamp is not partially correct, it is wrong for every unlabelled pull
  request.
- **Every hand-assembled input to the dashboard is a place this can recur.** The remaining
  gatherer-side steps are prose in `pr-data-fetching.md`; where a wrong value is
  indistinguishable from a legitimate one, the parser has to reject it rather than the doc ask
  nicely.

## Update 2026-08-01: ready-to-promote sidebar + one-click upstream create-links (new item)

Added `ready-to-promote-upstream-links` to the `dashboards` track (wave: upstream), depending on
`shared-pr-state-chips` (#111). The ask: a fifth sidebar group listing the pull requests that are
actually ready to go upstream, each with a link that opens cram2's compare-and-create page with the
description already written, so promoting is one click.

### Why it belongs to this plan rather than being its own thing

Phase 3 of `ROUTINE.md` already builds exactly this link, in exactly this format, and its only
delivery channel is the emailed FINISH summary of a scheduled LLM run. `routine-cutover`'s revised
target is that no scheduled LLM run exists at all — deterministic duties move to a plain Action,
judgment work moves to on-demand sessions "surfaced by the plans dashboard rather than a timer".
Building the link is pure computation over live pull request state; the only reason it needed a
model was that nothing else was rendering it anywhere. Putting it on the dashboard removes the last
non-judgment reason Phase 3 exists, so this item is a direct enabler of the cutover, not a parallel
feature. The same builder is what the Action's own "cram2-link comment" duty will call.

### The eligibility predicate

An item is ready to promote when all of:

- its live state is open-and-ready — this repo's convention is that a pull request stays a draft
  until its author has reviewed it themselves, so out-of-draft *is* the record of "reviewed by me",
  the same signal `_compute_ready_to_review` already reads in the opposite direction;
- GitHub reports it cleanly mergeable (PR 3's `mergeable`, already fetched for its conflict chip) —
  `None` (still computing) is not treated as ready, since promoting a conflicted branch upstream is
  the failure this check exists to prevent;
- its base is the fork's default branch — a pull request still stacked on a sibling cannot be
  promoted on its own, and one whose parent has merged has already been retargeted to main by
  GitHub, so this reads the *current* base rather than the plan's `depends_on`;
- it does not carry `in-review` (already promoted), and it is not merged or closed.

Check state deliberately does **not** gate the list: this repo's robotics jobs flake on tests a
`.claude/`-only pull request cannot reach, and that has already been ruled unrelated-and-ignorable
more than once in this plan. It renders as a chip so the decision stays the user's.

### The link

`https://github.com/<upstream_repository>/compare/<upstream_base>...<fork owner>:<branch>?expand=1&title=<t>&body=<b>`,
url-encoded, with the title taken from the fork pull request and the body being its first paragraph
truncated plus a `Full detail: <fork pull request url>` line. The truncation is not cosmetic —
Phase 3's doctrine records that a compare URL has a length cap and silently drops an over-long body,
which is the kind of failure nobody notices until a promoted pull request arrives upstream empty.

Portability: `upstream_repository` becomes a new optional top-level `plan.yaml` field (with an
optional `upstream_base`), because the dashboard tooling lives on main and this plan's standing rule
forbids a hardcoded repository name outside config defaults. A plan that sets neither renders no
group at all — the feature is invisible rather than broken for a plan with no upstream. `stack.toml`
was considered and rejected as the home for it: it carries git *remote* names (`upstream_remote =
"cram2"`), not the `owner/repo` a compare URL needs, and it is not a file the dashboard reads.

### Why it depends on #111 rather than standing alone off fork main

The two facts the predicate needs live in the same place #111 is already touching: `mergeable` is
literally #111's conflict chip, and the link builder belongs next to `pr_state` in the
`development_tooling` package #111 creates, so `routine-cutover`'s Action can import it instead of
re-deriving the URL format in prose a third time. Standing this item off fork main — the way #103,
#105, #119 and #115 legitimately do — would mean duplicating the `mergeable` plumbing into
`build_dashboard.py` a second time and colliding with #111 for real, not just textually. The cost is
accepted: this item cannot start until #111 leaves draft.

Three fields the pull request entry does not yet carry are this item's own work: `base`, `title` and
`body`, plus `pr-data-fetching.md`'s minimum field set updated to name them — the same document
whose under-specification caused the #119 bug, so the addition goes in as a documented requirement
rather than an optional extra.

### Removal from the list

Applying `in-review` after clicking Create is what drops an item, which is precisely the existing
convention ("I add `in-review` then"). `cram2-link-sent` stays out of the dashboard entirely: it is
Routine-side bookkeeping that stops an emailed link being re-sent, and a list recomputed from live
state on every refresh has nothing to remember. That leaves the two surfaces double-listing a pull
request while the live Routine is still running — accepted, since the Routine is scheduled for
deletion by `routine-cutover` and the overlap is a duplicate link, not a wrong one.

### Ordering

Before `dev-tooling-python-package`, which moves `build_dashboard.py` wholesale, and after #111.
Textual overlap in `build_dashboard.py` with #103, #105, #111 and #119 is the established
whichever-lands-second-merges pattern for this track.

## Update 2026-08-01 (new item): bug-fix chips in the dashboard sidebar

A new `dashboards` item, `sidebar-bug-fix-chips`, on branch
`claude/dashboard-bugfix-pr-section-161vf8`.

### The design reversal that defines it

The request was to surface bug-fixing pull requests in the sidebar, and the first
implementation read that as a new top group — "Bug fixes", listed first, outlined in red.
The user rejected that framing outright: *the sidebar is about actions, and being a bug fix
is not an action classification*. Every such item already belongs to ready-to-start,
blocker-may-be-cleared or ready-to-review, so a fifth group can only be built by taking
items out of the group that describes what to actually do with them. The red outline was
rejected for a second, independent reason: the existing group outlines are not mutually
exclusive with bug-ness, so a bug outline would compete with them for the same visual
channel rather than adding to it.

What survives is an attribute, not a category: `Item.is_bug_fix`, rendered as a small `bug`
chip on the entry *wherever it already is*. Two regression tests pin exactly that — a
bug-labelled item stays in its ordinary action group, and a non-bug entry gets no chip.

This is worth recording because `ready-to-promote-upstream-links` (the item added earlier
the same day) *does* add a fifth sidebar group, and correctly so: "ready to promote" names
something the user does. The distinction the two items draw together is the rule for
anything added to this sidebar later — a group must name an action; anything else is a chip.

### Incidental cleanup

The four sidebar group blocks were near-identical copies of the same markup, which is what
made "add a fifth" look cheap in the first place. They are now one `next_step_group` Jinja
macro whose `{% call %}` body supplies the reason line, so the per-item drift reason and the
three fixed reasons share one code path.

### Process failure recorded on this item

The item was created *after* the implementation was written, pushed, and reviewed — not
before, as this plan's own conventions require. It was also implemented without running
`check-setup.sh` first, so the plan-dashboard dependencies were discovered missing one
`ModuleNotFoundError` at a time across two interpreters instead of in one call. Both are
the same root cause: session-start scaffolding was treated as sufficient context to start
work from. See the conventions discussion this update was written alongside.

### Ordering

Independent, off fork main, no `depends_on`. `build_dashboard.py` overlap with #103, #105,
#111 and #119 is the established whichever-lands-second-merges pattern for this track.

## Update 2026-08-01 (later): the filter, the example, and where this PR sits

Follow-on to the bug-chip item above, all in the same session.

### The filter the chip made possible

The original request had framed this as "more of a filter that we can apply to show only
the bug-fixing ones", and the chip alone did not deliver that. "Bug fixes only" is now a
checkbox on the sidebar card: it hides every non-bug entry and every group left holding
none. Two details are load-bearing rather than cosmetic:

- **The checkbox only renders when some sidebar entry is a bug fix.** A filter whose only
  possible result is an empty card is worse than no filter, and this removes the empty
  state entirely rather than designing a message for it.
- **Each group's heading carries both counts, swapped by CSS.** A filtered group that
  still claims "(4)" while showing one entry is simply wrong, and recomputing counts in
  script would be the first place this page does arithmetic at runtime. Rendering both up
  front and switching with a class is what the done-items toggle already does with its two
  precomputed indent levels, so the filter adds a case to an existing pattern instead of a
  new mechanism.

### The example now demonstrates it

`example/pr_data.json`'s pull request #103 gains a `bug` label — `retry-fallback-queue`, a
dead-letter queue for dropped retries, is plausibly filed as a bug fix, and it puts the
chip on the *drift* entry, which is the clearest possible demonstration that the chip
appears wherever the item already sits rather than moving it. All three walkthrough
screenshots were regenerated from the committed sample (the third,
`dashboard-bug-filter.png`, is new and shows the filter applied). A test pins that the
example keeps producing exactly one chip and the toggle, so the screenshots cannot silently
go stale again.

Regenerating them turned up an unrelated staleness worth noting: the old
`dashboard-overview.png` still showed the description text `EXAMPLE_WALKTHROUGH.md`, a
filename that has since been renamed. Committed screenshots drift silently in a way
committed text does not.

### Where this pull request belongs

Asked to work out its best place, the answer is: exactly where it already is, plus one
downstream dependency.

- **Base stays fork `main`.** The branch is one commit off the current tip, touches only
  plan-dashboard files, and needs nothing from the #101/#106 chain — the same independent
  treatment #103, #105 and #119 get. Stacking it on #111 would buy nothing and inherit that
  chain's review latency.
- **It carries no `bug` label.** It surfaces bug fixes; it does not fix a bug. The
  convention that bug-fix pull requests must be labelled does not reach it.
- **`ready-to-promote-upstream-links` now depends on it.** That item adds a fifth sidebar
  group, which is a single `next_step_group` call once this macro has landed and a fifth
  hand-copied block if it has not — and the reconciliation would then be someone's manual
  merge of two divergent copies of the same markup. This is the first dependency in the
  `dashboards` track recorded for a *refactor seam* rather than for data or files, and it
  is the whole practical payoff of having collapsed the four blocks.
- **Still before `dev-tooling-python-package`**, which moves `build_dashboard.py` wholesale.

Overlap with #111 (item-card chips, new `pr_data.json` fields) and #119 (`from_mapping`'s
merge-timestamp guard) stays the established whichever-lands-second-merges pattern; neither
is a dependency in either direction, and #111 could not depend on this one anyway, being
based on #106.

### An oddity found and deliberately not fixed

`_compute_ready_to_review` requires every dependency to have an *open* pull request, via
`has_open_pull_request`, which is false once that dependency has merged. So an item whose
dependency has fully landed is excluded from "Ready to review", while one whose dependency
is merely open is included — the more finished the dependency, the less reviewable the
dependent looks. It is visible in the committed example, where `retry-circuit-breaker` sits
out of the list behind a merged `retry-backoff-strategy`. Left alone here: it is a
different root cause from this item's, and this plan's own convention keeps a bug-fix pull
request to one. It belongs to the same family as #103 and is worth its own item if it is
real rather than intended.

## Update 2026-08-01 (process): the two skipped steps become their own item

New `personal-data` item `session-start-plan-and-setup-guards`, recorded at the user's
request and deliberately left unimplemented for its own session.

Both failures it addresses happened in the bug-chip session, and both were already
forbidden in prose:

1. **The plan item was created after the implementation was written, pushed and reviewed.**
   The request named the plan in its first sentence. What made it survivable was
   `session-start.sh` printing a bare `plan: none` for a branch the generated index does
   not list — a message that reads as "no plan applies here" but equally means "the plan
   you were told about has no item for this branch yet". The convention that plan state is
   updated in the same turn cannot fire if the session has already concluded no plan is in
   play.
2. **`check-setup.sh` was never run**, so the plan-dashboard dependencies surfaced one
   `ModuleNotFoundError` at a time across two interpreters, and `plan-dashboard/SKILL.md`'s
   own step 0 was not read until the skill was invoked at the very end — long after its
   code had been edited.

The three fixes, in increasing strength: make the plan line name its own ambiguity; run
`check-setup.sh` from `session-start.sh` and surface a non-zero exit; and, if enforcement
is wanted over prompting, a `PreToolUse` hook on `Edit|Write` refusing the first source edit
from a branch with no plan item, with an explicit opt-out. The first two are the
recommendation. Only the third makes the miss impossible rather than unlikely.

Plan mode was considered as the mechanism and rejected: it would likely have caught the
first failure, but it rests on the same judgment that missed it and runs nothing, so it
would not have caught the second at all. The distinction worth keeping is that conventions
in `cram-notes.md` are read by a session that has already decided what it is doing, while
hooks run before it decides.

## Update 2026-08-01 (spun out): the ready-to-review merged-dependency bug gets its own item

`sidebar-bug-fix-chips` was opened as draft pull request **#120** (fork `main`, no `bug`
label, subscribed). The oddity its session recorded but refused to bundle in is now
`ready-to-review-merged-dependency` in the `dashboards` track.

**The bug.** `_compute_ready_to_review` admits an item only when every dependency satisfies
`has_open_pull_request` — `OPEN_DRAFT` or `OPEN_READY`, and therefore *false* once that
dependency merges. So the rule inverts at the far end: a dependency with a rough open draft
lets its dependent through, and the same dependency, fully landed, keeps it out. The more
finished the base, the less reviewable the thing on top of it looks.

**Why it reads as an oversight rather than intent.** The method's own docstring gives the
rationale as *"reviewing a stacked pull request before its base even has one open yet is
premature"* — a condition a merged base satisfies more completely than any open one.
`has_open_pull_request` was evidently reached for as the proxy for "the base exists and is
far enough along to build on", and it simply happens to be false at the settled end of the
range. That is a guess about intent, though, so the item's first step is to confirm it with
the developer rather than to patch it — AGENTS.md is explicit that an unexplained decision
gets a question, not an invented reason.

**The shape of the fix, if confirmed.** A dependency with *no* pull request at all must keep
excluding its dependent — there the base really does not exist yet, and that half of the
rule is right. So only the settled states need adding. `Item` already carries
`is_ready_to_unblock_dependents()` (done, merged, or open-and-ready), which is nearly this
predicate under a different name, so the fix may be a consolidation rather than an extra
clause.

**Why it was not folded into #120.** Different root cause, and this plan's own convention
keeps a bug-fix pull request to one. It is the third member of the same family as #103
(ready-to-start dropping dependency-free items) and #105 (unmet dependency chips) — all
three are cases of the sidebar's admission rules being written for the common case and
falling over at an edge of the dependency lifecycle. Worth noticing that the family keeps
producing members: the four sidebar lists are computed by four separate predicates that
each re-derive "is this dependency far enough along" in their own words.

## Update 2026-08-01 (kickoff + implementation): the session-start guards ship as #121

`/plan-item-kickoff workflow-unification session-start-plan-and-setup-guards`, session
https://claude.ai/code/session_01JSxeoePmxWoA4aETrwhFcx, which went on to implement it in the
same session as draft pull request **#121** on `claude/workflow-unification-setup-jgvs53`
(fork `main`, independent of the #101/#106 chain).

### The question that reshaped the design

The item recorded three fixes and named the first two as the recommendation. Asked which to
build, the user chose those two but attached a requirement the item had not considered:
*maybe the user doesn't want to have a plan or personal notes at all — how would that be
handled?* — and, for the guard, *"only for people who want to have plans or personal notes …
as automatic as possible and reliable and works well for both types of users"*.

That requirement turned out to need **no new setting**, which is the point worth carrying
forward. `session-start.sh` already opens with `fetch_personal_notes_branch || exit 0`, so a
clone with no personal-notes branch has always been served total silence; everything added
sits after that line and inherits it. Within the group that does use the branch, whether
`_generated/branch-index.tsv` exists separates *notes but no plans* — a legitimate
configuration that must read as quiet and accurate — from *plans in use*. Both discriminators
are state that already exists. A configuration flag would have been the obvious design and
the wrong one: it can be set wrongly, it needs documenting, and it asks the least invested
user to opt out of something they never asked for.

### What shipped

Four distinct plan-line outcomes in place of one bare `none`, the third of which had never
been visible at all: an index entry naming a plan whose manifest has since gone missing was
indistinguishable from having no plan. And a `setup:` line carrying `check-setup.sh`'s
`needs-setup` rows — run *after* `CLAUDE.local.md` is written, so its `claude_local_md` check
reports on this run's own output rather than flagging a correctly set-up clone, and captured
with `|| true` so a setup gap can never fail the hook. `plan_branch_index_exists` and
`tracked_plan_count` live in `resolve-personal-notes-config.sh`, which already owns that path.

### A latent crash, found only by writing the tests

`session-start.sh` had no test module. Writing the first one immediately surfaced that a plan
with **no `tracking_issue`** killed the hook outright: `grep` exits 1 when it matches nothing,
`pipefail` propagates that, and `set -e` ends the script with no output whatsoever — no notes,
no progress, no summary, no error. Every plan this fork tracks sets `tracking_issue`, which is
the only reason it had never been seen. This is the same shape as the `default_repository`
grep bug `plan-updates-since-helper` caught on #115, in the same family of scripts, within
days — the pattern is `set -o pipefail` plus a `grep` used as a test rather than a filter, and
it is worth grepping the remaining hooks for it rather than waiting for the third instance.

### The third fix became its own item

`plan-item-edit-guard` (`personal-data`, depends on this item). The user settled its semantics
while agreeing the split: block until resolved rather than a one-shot speed bump, active only
for someone who uses plans or personal notes, inert for everyone else. Inertness is a hard
constraint, not a preference — `.claude/settings.json` is committed, so every contributor who
inherits this repo inherits the hook, and one that blocked their edits would be indefensible
upstream. It should reuse #121's state-derived discriminator rather than introduce a setting,
for the same reason above.

Also worth recording from this session: the git identity configured in a fresh cloud clone is
`Claude <noreply@anthropic.com>` — precisely what AGENTS.md's Version Control rule forbids, and
the same authorship this roadmap already flags twice as a standing hazard on #101 and the P3
branch. It is the *default*, so it is not a one-off slip that happened to land; every session
that commits without setting the identity first reproduces it. Set `user.name`/`user.email`
before the first commit of any session.

## Update 2026-08-01 (hazard tracked): the assistant git identity is the container default

Raised by the user while `session-start-plan-and-setup-guards` was being implemented, and now
tracked as `git-identity-from-personal-notes` (`personal-data`).

This roadmap already flags commits authored `Claude <noreply@anthropic.com>` twice — three merge
commits on #101, and `6b51075e`/`f5d1c883` on the P3 branch — both times as something that had
happened, left unrewritten because fixing authorship means force-pushing shared history. What was
never established is *why* it keeps happening. It is the **global** git config in a session's
container:

```
global : Claude / noreply@anthropic.com
local  : (none, in a fresh clone)
GIT_AUTHOR_* / GIT_COMMITTER_* : unset
```

So it is the default rather than a slip, and every session that commits without first setting an
identity reproduces it. That reframes it from a recurring lapse of discipline into a missing piece
of tooling — which is the reason it became an item instead of another roadmap warning.

**The fix has a natural home.** `personal-settings-sync` (#109) already established the pattern:
personal config lives on the notes branch and is written into the clone at session start. A git
identity is the same shape. `check-setup.sh` gains a `git_identity` check, which then reaches the
user through the `setup:` line #121 added, with no new delivery mechanism. The one design rule
worth fixing now: write the repo-local identity *only when none exists yet* — a fresh clone has
none, someone who set one deliberately keeps it — rather than blocklisting known assistant
identities, which would be brittle and would need updating for every new one.

**Two limits, stated rather than papered over.** A hook covers only commits made inside a session
in this clone. The merge commits flagged above landed from *outside* any session — the GitHub
merge button and the live Routine — and no local hook can reach those; that half needs the GitHub
account's own commit-email setting or a changed merge path. And the global config stays wrong, so
only this repo is covered.

**A zero-code alternative exists and is stronger where it applies**: `GIT_AUTHOR_NAME`,
`GIT_AUTHOR_EMAIL`, `GIT_COMMITTER_NAME` and `GIT_COMMITTER_EMAIL` set at the environment level,
alongside the `CLAUDE_PERSONAL_NOTES_*` variables already kept there. Environment variables beat
both local and global config and are in force from a session's first command, before any hook
runs. They are per-environment and do not travel to another contributor's clone, which is exactly
why the tooling fix is still worth doing — the two cover different populations rather than
competing.

## Update 2026-08-01 (kickoff + implementation): the ready-to-review merged-dependency fix ships as #122

`/plan-item-kickoff workflow-unification ready-to-review-merged-dependency`, session
https://claude.ai/code/session_01Ltrz1G8qwSHgo6jyfeV1EU, which went on to implement it the same
session as draft pull request **#122** on `claude/plan-item-kickoff-workflow-s9e8bj` (fork `main`,
`bug` label, independent of the #101/#106 chain).

### The confirmation the item required

The item's first step was to confirm the oversight reading with the user rather than patch on a
guess, per AGENTS.md's rule against inventing a reason for existing behaviour. Confirmed: it is an
oversight. `has_open_pull_request` was the proxy for *"the base exists and is far enough along"* and
simply happens to be false at the settled end of the range.

### The consolidation this plan proposed three times is wrong

Worth recording prominently, because the suggestion had propagated into three places that all agree
with each other — the item's own `notes`, the *spun-out* section above, and the tracking-issue
comment of 2026-08-01T11:00:35Z — so the next reader would have found three concurring sources
pointing at the wrong fix.

`Item.is_ready_to_unblock_dependents()` is **not** the right shared predicate. It is
`is_effectively_done() or OPEN_READY`: it deliberately *excludes* `OPEN_DRAFT`, because a draft can
still see heavy rework and is unsafe to build a branch on. But `_compute_ready_to_review`
deliberately *includes* a draft dependency, and that is pinned by a pre-existing test whose own
comment says so — *"The dependency need not itself be past review - it just needs a pull request
open, so a whole reviewable stack can surface before its base merges."* Reusing it would have
traded this bug for a new one.

So the two predicates differ by exactly `OPEN_DRAFT`, and that difference is the real distinction:

- **safe to build a branch on** requires the base to be out of draft — `is_ready_to_unblock_dependents()`
- **worth reviewing the branch above** requires only that the base exists — `is_ready_for_dependent_review()`

Two sibling predicates sharing `is_effectively_done()` is the correct shape, not one merged
predicate. `has_open_pull_request` survives as the building block the new one composes, so nothing
became test-only and AGENTS.md's consult-before-removing rule was never reached.

This is the general lesson the family keeps teaching: the four sidebar lists each re-derive "is this
dependency far enough along" in their own words, and the answer is genuinely *different* per list.
Consolidating them onto one predicate is the tempting fix and the wrong one — what they need is
named predicates that make each list's own threshold explicit.

### The example, and the one assertion deliberately changed

`test_example_plan_renders_the_counts_and_sections_the_walkthrough_describes` is the only existing
assertion touched. That is the test working, not a test being bent: its own docstring says it exists
so *"a future change to either would fail this test instead of silently leaving the doc showing stale
numbers"*, and updating the assertion together with the prose and the screenshot is exactly the
response it was written to force. The example *fixture* is untouched, and now demonstrates the fix —
`retry-circuit-breaker` reaches the list behind its merged `retry-backoff-strategy`, so the sidebar
reads **Ready to review (2)**.

The screenshot was regenerated (user's call, taken knowing it conflicts as a binary with #120's own
regenerated copy — whoever lands second re-regenerates, mechanical because the image is deterministic
from the committed fixture). **There is no regeneration script**, which is itself the reason
screenshots keep drifting silently; until one exists the recipe is: render `example/` through
`build_dashboard.py`, then headless Chromium at `--window-size=1280,…` with
`--blink-settings=preferredColorScheme=0` — the dark theme the committed images use, and *not* the
headless default — cropped to the same 100px bottom margin. Regenerating also cleared the
`EXAMPLE_WALKTHROUGH.md` staleness this roadmap flagged on 2026-08-01: a committed screenshot goes
stale from any change, not only from the one that prompted the regeneration.

### Correction to the git-identity hazard, verified live this session

The `git-identity-from-personal-notes` item recorded above diagnoses the container state as
`GIT_AUTHOR_*`/`GIT_COMMITTER_*` **unset**, with the global config supplying
`Claude <noreply@anthropic.com>`. That is no longer the state. In this session:

```
global : Claude / noreply@anthropic.com      (still wrong)
local  : set by this session, and ignored
GIT_AUTHOR_NAME / GIT_COMMITTER_NAME   : Abdelrhman Bassiouny
GIT_AUTHOR_EMAIL / GIT_COMMITTER_EMAIL : abassiou@uni-bremen.de
```

So the zero-code alternative that item names as *"stronger where it applies"* is now actually in
force, and #122's commit is live proof it works: it landed authored `Abdelrhman Bassiouny
<abassiou@uni-bremen.de>` despite the global config still being wrong, and despite a repo-local
identity having been set to `bido.bassuny@gmail.com` — environment variables beat both, exactly as
predicted.

Two consequences for that item. Its diagnosis section needs updating before anyone implements
against it, or they will build for a container state that no longer holds. And its "write the
repo-local identity only when none exists yet" rule now has a second reason to be careful: a
repo-local identity written by the hook would be silently overridden by these environment variables
anyway, so on this environment the hook can only ever be a no-op — its real value is the *other*
populations (another contributor's clone, an environment without the variables set), which is what
the item already says, just now with the overlap made concrete.

## Update 2026-08-01 (gap closed): notes-only work needs no plan item

Raised by the user after #121 was already open, and it exposed a real wart in what had
just shipped: *"some situations happen where I am a personal notes user and a plan user,
and there's work that will just be directly a modification on my personal notes and will
not be merged upstream or be done off main. For these cases, there's no need for the item
to be part of a plan."*

Verified rather than reasoned about, by running the new hook against a `main` worktree:

```
PR progress:  not applicable (no current PR on this branch)
plan:         no item tracks branch 'main' (5 plan(s) tracked) - ... add its item before starting
```

`main` can never be a plan item's branch, and **the line directly above already knew
that** — `pr_progress_path` has always excluded the default branch, the personal-notes
branch and a detached HEAD. The new plan line simply ignored an exclusion its own
neighbour had been applying for exactly the same reason. Those three now report
`not applicable`; an index entry naming the branch still wins over the check, so a
genuinely tracked branch is unaffected.

**The two predicates are deliberately not shared**, despite listing identical cases today.
They answer different questions and are already known to diverge: a branch whose pull
request *targets the notes branch* still wants its progress tracked, but still never wants
a plan item. Sharing them now would have to be undone the moment that case is handled.

### The case left open, and why it isn't in #121

The user's follow-up — *"what if someone (a session for example) makes a PR that targets
the notes branch? this as well should not have a plan item"* — is correct and is **not**
covered by the three branch names. It is recorded on `plan-item-edit-guard` instead of
being fixed here, for a concrete reason worth remembering: the obvious local test, "the
notes branch tip is an ancestor of HEAD", collides with the hook tests' own fixture, which
creates its work branch *off* the notes branch (`publish_notes_branch`). Adopting that test
without first re-basing the fixture on the initial commit would have failed every existing
plan-line test and, worse, encoded an unrealistic branch topology as the reference. That is
a fixture refactor in a file #115 also edits, so it belongs with the item that needs the
mechanism rather than bolted onto this one.

### What this settles for the guard

`plan-item-edit-guard` now carries two mechanical exemptions rather than opt-outs: it fires
only for files tracked in the working tree (so notes-only work is exempt for free —
`CLAUDE.local.md` is gitignored, and notes and plan data are written from scratch paths by
the `save-*.sh` scripts), and a notes-targeting pull request is exempt once (b) has a
mechanism. The per-branch opt-out survives, but its only remaining job is genuine no-plan
*code* work — a much narrower and more defensible role than "anything the guard gets wrong".

## Update 2026-08-01 (kickoff + implementation): the git identity sync ships off #121

`git-identity-from-personal-notes` was kicked off and implemented in the same session. Two
things the item recorded turned out to be wrong at implementation time; both are corrected
in its `notes`, and both changed the design rather than just the prose.

### The environment variables, confirmed a second time

The container check the `#122` session recorded above (*"Correction to the git-identity
hazard"*) reproduced exactly: global config still `Claude <noreply@anthropic.com>`,
`GIT_AUTHOR_*`/`GIT_COMMITTER_*` set to `Abdelrhman Bassiouny <abassiou@uni-bremen.de>`, and
an empty commit in a scratch repository authored correctly — reverting to `Claude` the moment
those four variables are stripped. This clone differed in one respect from that session's:
**no repository-local identity at all**, so precedence ran straight from the environment to
the global fallback.

The consequence that section did not draw is the load-bearing one for the check. Because the
variables outrank config, `git config --get user.name` prints `Claude` *on a clone whose every
commit is correctly authored*. A check built on it would report the assistant identity as the
problem on exactly the clones that don't have one — the single wrong answer a check about
commit authorship must never give. So `effective_git_identity` resolves through
`git var GIT_AUTHOR_IDENT`, which applies git's real precedence, and `check-setup.sh` compares
*that* against what the notes branch records.

That also answers the "the hook can only ever be a no-op on this environment" point above.
It is true, and it is why the check matters more than the write here: on an environment with
the variables set, the `git_identity` row is what makes the override visible, naming
`GIT_AUTHOR_NAME`/`GIT_AUTHOR_EMAIL` as the reason a correct-looking config still isn't what
commits carry. The write half is for the populations without them.

### Not an independent PR off main after all

The item says *"small independent PR off fork main, like #109 and #115"*, `depends_on: []`.
Checked against the live branches, neither held:

- **#109 is not a viable base at all** — `mergeable_state: dirty`, labelled `needs-resolution`,
  based on the superseded `0fd14357`. The item offered folding the identity into its
  `settings.local.json` sync; that would have blocked this on a stalled PR, so it gets its own
  `.claude/personal/git-identity` instead.
- **#121 carries the only harness that can test this.** On `main`, *nothing* runs
  `session-start.sh` in a test. #121 adds `ScratchRepository.run_hook_script` and
  `write_setup_prerequisites`, and `test_session_start_sh.py` alongside them.

Basing off `main` would have meant hand-rolling a `run_hook_script` equivalent *in the same
file* #121 adds one to — not the textual overlap the whichever-lands-second convention covers,
but duplicated infrastructure that collides. The asymmetry settled it: if #121 lands first,
rebasing onto `main` costs nothing, whereas a parallel harness is thrown-away work either way.
So `depends_on: [session-start-plan-and-setup-guards]`, and the sibling items that legitimately
based off `main` are not a precedent here — theirs overlapped on summary lines, this one needs
a harness.

Worth keeping as a general rule: *"independent PR off main"* recorded at planning time is a
claim about the code, and it expires when a sibling PR moves the test infrastructure. Re-check
it against the live branches at kickoff rather than inheriting it.

### What shipped

`.claude/personal/git-identity` on the notes branch, in git's own config format and read back
with `git config --file` — no hand-rolled parser, and the writer is the same tool as the reader
so the two cannot disagree. `session-start.sh` writes it into repository-local config only when
the clone has neither `user.name` nor `user.email` of its own, before the setup check so
`check-setup.sh` reports on what this run just did. `save-git-identity.sh` requires `--name`
and `--email` and refuses to read them from the clone's config — in a fresh session environment
that resolves to the assistant identity, so a guessing script would record the very thing this
item exists to stop, silently. Same reasoning as #107's required `--remote`.

One refactor came along because the tests forced it: the environment scrub moved onto
`ScratchRepository.run_hook_script`, replacing the two hand-rolled scrubbed-subprocess blocks
#121 left in `test_check_setup_sh.py` and `test_session_start_sh.py`, and extending it to
`GIT_AUTHOR_*`/`GIT_COMMITTER_*`. Without that the suite would assert against whatever identity
the runner's shell happens to carry — which, per the section above, is not empty here.

54 tests pass in `.claude/hooks/tests`, was 37. Verified live in this clone beyond the suite:
the row read `needs-setup` naming the real author while `git config --get user.name` said
`Claude`, `save-git-identity.sh` recorded the identity, the row went `ok`, and a re-run pushed
nothing.

## Update 2026-08-01 (kickoff + implementation): dashboard chip notes collapse

Raised directly from a screenshot of this plan's own published dashboard: the
`ready-to-review-merged-dependency` card's `notes` (see its entry above) ran long enough to
fill the entire viewport by itself, so only one item was visible on screen at a time and
reviewing the board meant heavy scrolling instead of a glance-able overview. The dashboard's
whole purpose is the opposite of that.

`item_card` (`templates/dashboard.html`) rendered `item.notes` at full height with no
collapse — every long-note item did this, not just that one card. Fixed by wrapping the
notes `<div>` in a `<details>`/`<summary>` toggle, collapsed by default, reusing the
`.roadmap-details` CSS-only arrow-toggle already in the file for the page-level "Background
& history" section rather than adding new JS. Deliberately did not touch
`build_dashboard.py`/`render_common.py` — they already pass `item.notes` through unchanged,
and the native `<details>` element needs no script wiring. The sidebar "What to do next"
cards are unaffected: they render short fixed one-line strings, not `item.notes`.

Verified by rendering the skill's own `example/` fixtures through `build_dashboard.py` with
a temporarily lengthened note and publishing the result as an Artifact: notes collapse by
default behind "▸ Notes", expand to "▾ Notes" in place on click, and items with no notes
render no summary line at all. `pytest .claude/skills/plan-dashboard/tests/` — 194 passed,
unaffected since this is template/CSS only.

Independent of the `#101` chain, based on fork `main`; `dashboard.html` overlap with `#103`,
`#105`, `#111`, `#119`, `#120` and `#122` is the same whichever-lands-second-merges pattern
this track has had throughout. Opened as draft pull request `#124`, subscribed to its
activity.

### Opened as #126, and the one thing that makes a stacked base worth watching

Draft pull request **#126**, based on `claude/workflow-unification-setup-jgvs53` (#121), no `bug`
label. It is the first item in this plan whose pull request stacks on *another item's* pull request
while sitting outside the `#101 → #106 → #107 → #110` chain, and that is worth one line of standing
guidance rather than being rediscovered later.

Neither #121 nor #126 is a member of a native GitHub stack, so the Phase-1 reparent hazard
(`422 - Cannot change the base branch because the pull request is part of a stack`) does not apply
here: a plain `PATCH` of the base is available as the recovery. What *does* apply is round-2 of
`native-stacks-prototype`'s findings — a push-based merge marks a pull request merged but does
**not** retarget its children, and only `merge-async` retargets automatically. So if #121 lands by
push or fast-forward rather than through its own pull request, #126 keeps pointing at a branch that
is about to disappear, and needs retargeting to `main` by hand. Cheap to fix, invisible if nobody
looks.

The reverse direction is the cheap one, and is why the base was chosen: if #121 merges normally
first, rebasing #126 onto `main` costs nothing.

## Update 2026-08-01 (decision 12): the bash layer retires into development_tooling — conversion registered

Session: https://claude.ai/code/session_015ShWoksdRxv5ioXcDaNiQk (study session; registration only, no
code conversion). Eight new items in the `dashboards` track: `dev-tooling-notes-core-python` through
`dev-tooling-config-shim-slimming` plus `dev-tooling-github-api-unification`, all downstream of
`dev-tooling-python-package`.

### What was decided

All logic in the `.claude/` bash tooling (~1300 lines across 9 hook scripts plus
`refresh_dashboard.sh`) moves into `development_tooling`. This extends decision 8 in its own
words — it already said the bash hook entry points "become thin wrappers invoking `python -m`" —
and settles what that means: the permanent bash remainder is ~8 three-line shims at the existing
paths, a slimmed `resolve-personal-notes-config.sh` (constants + cd for the 10 doc sourcing sites
and ci.yml), and `configure-personal-notes.sh` unchanged (pasted-by-reference into cloud
environment setup fields this repo cannot update). `settings.json` stays byte-identical.

### Why now (the evidence)

The study inventoried the bash layer's failure record and duplication:

- Four near-identical copies of the scratch-worktree write dance (plus an orphan fifth) that
  `write-personal-notes-file.sh` was extracted to end but never absorbed; the marker strings,
  branch-missing error, and no-CLAUDE.local.md error each duplicated 3-4 times.
- The recorded pipefail/`set -e` family (#107's exit-128 fix, #115's `default_repository` grep,
  #121's `tracking_issue` latent hook-kill) — the 2026-08-01 comment on #102 already called two
  instances a pattern; the study found the class is structural, not incidental.
- Defects nobody had hit yet: a missing `BEGIN-PERSONAL-NOTES` marker pushes the *whole*
  `CLAUDE.local.md` (PR-progress included) into the notes file; `__save-personal-notes-tmp` /
  `__save-pr-progress-tmp` are fixed names that race between concurrent sessions; every push is
  single-shot, so a concurrent save loses the edit after the trap deletes the committed scratch
  worktree; `set -u` kills argument loops on a trailing flag; `save-plan.sh` never validates the
  roadmap; `check-setup.sh` passes on any substring occurrence of `session-start.sh` in
  settings.json.

Each conversion item fixes its file's defects with failing tests first; external contracts (flag
surfaces, TSV rows, exit codes, the 4-line SessionStart stdout block) are pinned by golden
fixtures recorded from the bash versions and by subprocess contract tests through the real shims.

### The one accepted functional trade

The SessionStart floor rises from bash+git to bash+git+python3>=3.11. The shim probes and exits 0
with a single diagnostic line when the probe fails, so the hook stays inert for contributors —
a machine without python3 silently skips loading personal notes. Accepted deliberately: every
targeted environment ships 3.11+, and the bash read path is where the silent-death bugs live.

### Sequencing

Items 2-6 cannot land before the in-flight bash-touching PRs (#107, #109, #110, #115, #121,
#126): a wholesale body rewrite is not mergeable by the whichever-lands-second-merges convention.
`dev-tooling-session-start-python` additionally depends on the #121/#126 items so their
`run_hook_script` tests carry over as the shim contract tests. Everything hangs off
`dev-tooling-python-package`, which stays last in the upstream wave as already recorded.

### The krrood question (asked, verified, deferred)

The user asked whether `development_tooling` should depend on `krrood` — exceptions as
`DataclassException` subclasses, and eventually EQL/verbalization. Verified in-session:
`krrood.exceptions`' only third-party import is `typing_extensions` (line 9, `Optional`) — a
one-line stdlib fix makes `import krrood.exceptions` fully stdlib-clean (proven empirically with
all third-party imports blocked; `krrood/__init__.py` is already stdlib-light). In-monorepo use
would need no install (a 2-line `sys.path` bootstrap to `krrood/src/`); other repos have
`pip install krrood` (PyPI, 26.7.0) via their environment setup script — never in the hook (60s
budget, pygraphviz build hazard, contributors' machines). EQL/verbalization can never be
hook-safe (jinja2/lemminflect/rustworkx) and are under active churn in three sibling plans.

**Decision: version 1 is fully independent of krrood.** `errors.py` mirrors the
`DataclassException` idiom in a stdlib-only base — a small, conscious pattern duplication. A
separate future plan (working name `dev-tooling-krrood-adoption`, deliberately *not* created now)
migrates the tooling onto krrood once the krrood API plans (`dag-facade-hardening`,
`eql-performatives`, `eql-verbalization`) and the converted tooling itself have stabilized,
seeded with the verified facts above plus the guard design (a CI test importing
`krrood.exceptions` with third-party modules blocked defines the hook-safe surface; the tooling
may only import guard-covered modules). Dependency tiers adopted now, krrood-independent:
tier 1 hook-safe = stdlib only (SessionStart path, enforced by an import-block test); tier 2
command-time = installed packages (PyYAML); tier 3 domain machinery (EQL queries over the plan
model, verbalized status text) = only ever in dedicated feature items of that future plan.

## Update 2026-08-02: `landed-parent-detection` validated against the real PR #41 stack

`/plan-item-resolve workflow-unification landed-parent-detection`, prompted by the user wanting to
try PR #117's fix on "the current stack that starts with PR #41 which has the exact issue" rather
than take the item's synthetic tests on faith.

**Confirmed live, not assumed**, before touching anything:

- `ripple-down-rules-refactor` (PR #40's head, `34f160df`) **is** an ancestor of `origin/main` -
  `git merge-base --is-ancestor origin/ripple-down-rules-refactor origin/main` succeeds. PR #40 is
  closed, not merged - exactly the "landed by another route" case.
- PR #41 (`rdr-backward-inference`) is still based on that branch (`base.sha` matches the branch's
  live tip) - it has not been reparented since the bug was found.
- PR #41 is native GitHub **Stack #112** (`GET /stacks/112`, `X-GitHub-Api-Version: 2026-03-10` via
  curl + `GH_TOKEN` - no MCP tool exposes the stacks API): `#41 (rdr-backward-inference) -> #63
  (D-core-aid) -> #64 (D-core-underspecified) -> #65 (D-core-corner-case) -> #66
  (D-core-serialization) -> #67 (D-core-support) -> #98 (D-core-expert)`, all open, all non-draft
  except #41. This is the exact native-stack-member case `ROUTINE.md`'s NATIVE-STACK MEMBERS section
  (added by this item) targets: plain `PATCH` 422s here, recovery is dissolve -> PATCH -> restack ->
  re-create.

**The validation itself** (read-only local script, no push, no GitHub write): built the real 7-PR set
above as `PullRequest` records and wired `is_merged` to a real `git merge-base --is-ancestor
origin/<branch> origin/main` predicate - no stubs, no synthetic fixtures - then ran `restack_plan`/
`parent_landed` from two checkouts:

- **`claude/stack-tooling-on-main` (#106, pre-fix)**: `restack_plan` reparents #41 onto
  `ripple-down-rules-refactor` (the stale, closed branch) rather than `main` - the bug reproduces
  exactly as described, on live data, not just in the item's own synthetic tests.
- **`claude/stack-landed-parent-detection` (#117, the fix)**: `restack_plan` correctly emits
  `{"branch": "rdr-backward-inference", "parent": "main", "strategy": "merge"}` for #41, and
  `has_landed_upstream("ripple-down-rules-refactor")` is `True`. The six branches above #41
  (#63..#98) keep their normal parent-chain entries unchanged - only #41's root parent moves.

**What this settles.** The item's own notes already said "restack-plan emits the right parent but
Phase 1 still will not retarget on GitHub" - that was true of the synthetic tests only, since nobody
had run the fixed code against #41's actual data before. It now holds against the real stack too, so
the fix is validated end-to-end for the exact case it was written for, not merely for the
synthetic fixtures the failing-first tests use.

**What was deliberately not done.** The live repair - `POST /stacks/112/unstack` (dissolves all 7,
no selective/undo), `PATCH` #41's base to `main`, restack + force-push #41 through #98 in order,
`POST /stacks` to re-create - was proposed but not executed. It is destructive (no undo once
dissolved) and force-pushes six live branches, so it needs the user's explicit go-ahead in the
session, separate from and beyond validating the fix's logic. Also untouched, as already recorded
above: merging #117 itself (normal cram2-review track) and pasting the Phase 1 amendment into the
live Routine trigger (the user's own manual-paste call, unrelated to this validation).
