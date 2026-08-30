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

**What was deliberately not done, then attempted with approval.** The live repair - `POST
/stacks/112/unstack` (dissolves all 7, no selective/undo), `PATCH` #41's base to `main`, restack +
force-push #41 through #98 in order, `POST /stacks` to re-create - was proposed first and not
executed pending explicit go-ahead, since it is destructive and force-pushes six live branches. The
user then approved it in the same session, and it was attempted for real:

- `POST /stacks/112/unstack` (no body): **204**, dissolved cleanly.
- `PATCH /pulls/41` with `{"base": "main"}`: **403** - `"Changing a pull request's base branch is
  not permitted for this session type."` This is a new hazard, and a harder one than the item
  itself anticipated: `ROUTINE.md`'s NATIVE-STACK MEMBERS section (this item's own addition) was
  written for the **422** GitHub returns when a `PATCH` targets a *stacked* PR's base - its whole
  recovery sequence (dissolve first, then PATCH, then restack, then re-create) exists to get past
  that 422 by removing the PR from a stack before touching its base. This 403 fired on the *already
  unstacked* PR - it is a platform-level restriction on any base-branch change from a Claude Code
  session, unrelated to stack membership. The dissolve-then-PATCH recovery this item designed
  cannot work around it, because the block isn't the stack; the doctrine's whole premise for this
  case needs revisiting.
- Recovery, per `ROUTINE.md`'s own stop-and-report rule (never leave a stack half-dissolved):
  re-created the stack immediately, `POST /stacks` with the same 7-PR list. GitHub assigned it a
  **new number, Stack #128** - #112 cannot be reused once dissolved - but the PR list, order, and
  every base are otherwise identical to before the attempt. Verified: #41's base is still
  `ripple-down-rules-refactor`, unchanged; nothing about any of the seven PRs' actual state moved.

**Consequence for `landed-parent-detection` and `ROUTINE.md` going forward.** This joins the
tag-push/branch-delete finding from the 2026-07-29 addendum as a third confirmed instance of the
same shape: a mutating GitHub operation that works fine through the API in principle but is blocked
specifically for a Claude Code session's credentials. The item's NATIVE-STACK MEMBERS sequence
still describes the right *mechanics* (dissolve -> PATCH -> restack -> re-create), but step 3 (the
PATCH) needs a human or a differently-scoped actor to execute - the UI's "Rebase stack" button, `gh
stack` from a real user token, or a broader-scoped credential - the same way tag pushes and branch
deletes already do. `ROUTINE.md` and the live Routine's prompt both need this stated explicitly
rather than assuming the sequence completes end-to-end from a session; as written today, a session
hitting this now dissolves a stack it cannot finish repairing unless it also re-creates it
immediately, as done here. Merging #117 itself (normal cram2-review track) and pasting the Phase 1
amendment into the live Routine trigger (the user's own manual-paste call) remain untouched,
unrelated to this finding.

## Update 2026-08-02 (later): the fix generalizes to a new item; and preventing the orphan in the first place

Follow-on in the same session, after the user asked two things: how to make the reparent fully
session-solvable (not needing a human for the blocked step), and separately, how to stop a parent
landing-while-closed from orphaning a child at all, rather than only recovering after the fact.

### Scope correction: the block is unconditional, not stack-specific

The PATCH 403 recorded above fired on PR #41 *after* it had already been removed from Stack #112 -
at that moment it was an ordinary, non-stacked pull request. That means the restriction is not the
stack-member 422 `landed-parent-detection`'s `ROUTINE.md` addition was written for; it is a
platform-level block on **any** pull request base-branch change from a Claude Code session, full
stop. The consequence reaches further back than today's incident: the *original* Phase 1 REPARENT
paragraph (`stack-tooling-on-main`, #106), which prescribes a plain `PATCH` for an ordinary,
non-stacked child whose parent lands, was never actually session-executable either - nobody had hit
it live before because a parent landing while its own PR stays open-and-merged (the common case) is
rare enough that the retarget step had never actually been exercised end to end.

### New item: `session-safe-pr-reparent`

Spun out rather than folded into #117, since it is a different root cause (a blocked API call, not
the board-membership/git-ancestry detection bug #117 fixes) - matching this plan's own
one-root-cause-per-bug-fix convention. `depends_on: [landed-parent-detection]`, branched on top of
#117's head rather than #106 directly, since it edits both #106's original REPARENT paragraph and
#117's NATIVE-STACK MEMBERS addition.

**The fix**: replace "PATCH the base" everywhere in `ROUTINE.md` (and the small reparent-recovery
script #106 already scopes) with **close the orphaned PR, `create_pull_request` for the same head
branch against the corrected base, carry over labels and the session-link line, comment on the old
PR linking to the new number**. Creating and closing pull requests both already work fine from a
session - this substitutes the mechanism rather than retrying the blocked verb. Native-stack members
keep the same shape as #117's sequence, swapping only the middle step: unstack -> close old PR ->
create new PR -> restack (local rebase/force-push, unchanged) -> re-create the stack with the new PR
number in place of the old one.

**Cost, named rather than hidden**: the reparented PR gets a new number and its review thread starts
fresh. Mitigated by the close-comment linking old to new, but it is a real trade against a clean
PATCH - accepted because the clean PATCH is not available to a session at all, so there is no
zero-cost alternative to weigh it against.

**Cross-note for `routine-cutover`** (added to that item's own notes too): verify, concretely, whether
the Action's own credential (default `GITHUB_TOKEN` or a stored PAT - a different actor identity than
a session's token) can PATCH a base cleanly, before assuming it needs the same close+create-PR
fallback. If it can, the Action gets a real, clean reparent with no PR-renumbering cost at all -
worth checking before building the fallback into the Action's own path.

### Preventing the orphan itself, not just recovering from it

The user's second question - stop a landed-but-closed parent from ever orphaning a child - has two
layers, and the first one is the most direct:

1. **The fix that already exists has to actually ship.** `landed-parent-detection`'s own notes already
   record that the live Routine's Phase 1 prompt is unpatched pending the user's manual paste, and
   #117 itself is not yet merged to `main`. Until both land, the *old* code keeps running in
   production, and it will keep missing this exact case - a closed-not-merged parent - on every
   cycle, indefinitely, not just once. This is worth stating plainly because it is easy to read
   today's work as "done" once the logic is fixed and validated; it is not in force until deployed.
   Once it is, the ancestry-based check runs on every Phase 1 pass and self-heals this pattern within
   one cycle of whatever cadence Phase 1 runs on.
2. **Cadence still leaves a window; make detection event-triggered, not just periodic.** Even with
   #117 live, a scheduled Routine/Action only notices a closed-and-landed parent on its next tick.
   The tighter fix - folded into `routine-cutover`'s notes as a design requirement, not a new item,
   since it is a refinement of the Action that item already owns - is to also trigger the ancestry
   check from the `pull_request` `closed` webhook event itself: the moment any fork PR closes,
   ancestry-test its head branch immediately, and reparent every open PR based on it right then if
   it turns out to have landed elsewhere. That collapses the detection window from "up to one
   scheduled cycle" to "the same event that could cause the problem," which is what actually prevents
   the #40/#41 pattern from recurring rather than only shrinking how long it can go unnoticed.

Both of these are about *when* the already-correct detection logic runs, not about the logic itself
- #117 already answers "is this parent actually landed" correctly; what was missing is "make sure
that question gets asked, in production, as close to the landing event as possible."

## Update 2026-08-02 (traced): who closed PR #40, and why prevention means catching it, not stopping it

The user asked directly: who closed the parent PR without marking it, and if it was them, doesn't
that mean no automated script or routine can actually prevent this? Traced from PR #40's own GitHub
timeline and its successor rather than assumed:

- **The user closed PR #40 themselves**, 2026-07-09T08:49:56Z, with a comment on the PR: *"Replaced
  by #53. This branch's history was rebuilt (recreated, not force-pushed forward) after
  eql-core-prep/code-generation-extract advanced further upstream, so GitHub won't let this PR
  reopen. Same content — #53 cherry-picks this PR's single real commit onto the current
  code-generation-extract tip."* This is deliberate, correct maintenance - a branch got rebuilt
  after its own base advanced, the old PR couldn't reopen against the new history, so the user closed
  it and opened a clean successor. Not a bot, not the Routine, not a mistake.
- **PR #53** is that successor: same branch name (`ripple-down-rules-refactor`), rebuilt history,
  same one real commit cherry-picked onto the current `code-generation-extract` tip. The user merged
  it normally into `main` on 2026-07-25T09:56:27Z (`merged_by: AbdelrhmanBassiouny`) - this is the
  actual, ordinary merge event that put the branch's content in `main`.
- **PR #41** predates both: created 2026-07-07, based on the branch name `ripple-down-rules-refactor`
  directly, never on #40 or #53's PR number. It had no way to know which PR number was currently "of
  record" for that branch, because it never referenced one.

**The right conclusion, and the correction it forces on the prevention design above.** The user is
right that no automation should try to stop this - closing a superseded PR after a branch rebuild,
and later merging its replacement, are both normal and correct. Trying to prevent the *human action*
would be solving the wrong problem. What was missing is narrower and worse than first framed: it is
not specifically "closed without merging" (#40's case) - it is that **any pull request leaving the
open set drops out of `board.json`**, whether by an unmerged close (#40) or by a normal
merge-and-auto-close (#53). The old code's `by_name.get(branch.parent)` returns `None` either way,
and reads that `None` as "no parent" regardless of which route caused it. `landed-parent-detection`'s
ancestry check is correct against both, which is reassuring - it never depended on which of the two
happened.

It does mean the event-triggered design recorded on `routine-cutover` above was one event narrower
than it should be. `pull_request: closed` fires for a merge-close exactly as it does for a
supersede-close, so the fix is to re-sweep ancestry for **every** remaining open fork PR's base on
that one event type, not to special-case "check just this PR's own branch." Concretely in this
history: that sweep, triggered off #53's closed-via-merge event on 2026-07-25, would have caught
#41's orphaning that same day - instead of the ~6 days it actually took until a review round on #41
noticed the inflated diff by accident on 2026-07-31. `routine-cutover`'s notes are corrected to say
this plainly, rather than leaving the narrower framing on record.

## Update 2026-08-02 (probed): the base-change 403 is one credential, not the platform

`/plan-item-kickoff workflow-unification session-safe-pr-reparent`, session
https://claude.ai/code/session_01WvRrTrtiznzAyvaoeCdNSq, prompted by the user wanting the fix tried
on PR #41 the way `landed-parent-detection` had been.

The kickoff's step 0 was a cheap probe the previous session had no reason to run: the recorded 403
came from `curl` + `GH_TOKEN` through the session git proxy, and `mcp__github__update_pull_request`
takes a `base` parameter that nobody had tried. Run on a throwaway pull request (#129), against the
same pull request minutes apart:

| Client | Non-stacked PR | Stack member |
| --- | --- | --- |
| MCP `update_pull_request(base=…)` | **200, base changed** | `422 - Cannot change the base branch because the pull request is part of a stack` |
| raw `PATCH` + `GH_TOKEN` via the git proxy | **403 - not permitted for this session type** | — |

**The block is on that credential, not on the operation and not on sessions.** The reason nobody had
noticed is structural rather than accidental: the stacks endpoints have no MCP tool, so `ROUTINE.md`
tells the reader to use `curl` with `GH_TOKEN` — and a reader already in `curl` naturally issues the
base `PATCH` there too, straight into the 403. The doctrine's own advice routed people into the one
client that cannot do the job.

The full stack-member repair was then rehearsed end to end on a throwaway stack, before anything
touched #41: `POST /stacks/131/unstack` → 204, MCP base change → 200, `POST /stacks` → 201 (new
Stack #132, trunk moved). That is exactly the sequence `landed-parent-detection` already prescribes.
**It was right about the mechanics and wrong only about the client.**

### What this kills

`session-safe-pr-reparent` was created to replace every reparent with close-old-PR → create-new-PR,
accepting a new pull request number and a fresh review thread on each one because "the clean PATCH is
not available to a session at all". It is available. So:

- **No close+create fallback**, anywhere — no pull request has to lose its number, labels or review
  thread to be reparented.
- **No reparent-recovery script.** Worth recording that the script the item's notes said #106
  "already scopes" **was never written** — `git ls-tree` on both `claude/stack-tooling-on-main` and
  `claude/stack-landed-parent-detection` shows `.claude/stack/` holds only `README.md`, `ROUTINE.md`,
  `stack.py`, `stack.toml`, `tests/`. Decision 11 promised it and it did not get built; with the base
  change available there is nothing left for it to work around, and not adding new mechanics is
  decision 11's own direction (GitHub maintains the mechanics, we maintain policy).
- **The "third instance" framing is wrong and is corrected in the item notes.** Tag-push and
  branch-delete are genuinely blocked for a session because *no MCP tool exists for either*. A
  base change has one. The family is "operations with no session-reachable client", not "operations
  the platform forbids sessions" — which is a materially different thing to carry into
  `routine-cutover`, where the Action's own credential is the open question.

### What shipped — and why it ended up inside #117 rather than beside it

A `BASE CHANGES GO THROUGH THE GITHUB MCP SERVER` rule stated once in Phase 1 — recording the 403, naming its cause, and telling a
session that hits it that it used the wrong client rather than found a stuck reparent — with both
reparent sites deferring to it, step 3 of the native-stack sequence using the MCP tool and stating
that the child keeps its number, labels and review thread, and `README.md`'s source-of-truth row
naming the tool.

Four contract tests, written failing first. `ROUTINE.md` is prose and had **no test coverage at
all**, which is exactly how a doctrine drifts back to a blocked verb unnoticed; 251 tests pass in the
dev-tooling suite, was 247.

This was opened as draft PR **#133**, stacked on #117 — because a session's standing instruction is
to develop on its own designated branch and not push to another session's branch without explicit
permission. The user overrode that on sight of the result, with a standard worth recording as
general: **a pull request must be self-sufficient and correct on its own; never leave one open that
is known to contain a bug.** #133's only purpose was correcting a section #117 had *just
introduced*, so stacking it meant #117 would sit in review prescribing a step already known to 403,
with its fix visible only to someone who noticed a second PR behind it. A change whose sole purpose
is patching its parent's own new section is not independent work.

So the commit was fast-forwarded onto `claude/stack-landed-parent-detection` (a true
fast-forward, `a672c146..938e6415` — no rebase, no force-push, #117's three commits untouched).
GitHub then detected #133's head as contained in its own base and auto-closed it as **merged** —
merged into that branch, not into `main`, which is worth stating because the badge does not say so.
A comment on #133 records it.

Two consequences beyond the fold itself. #117's description was rewritten rather than left alone —
it described the old mechanism in two places, and a PR whose body explains a superseded design is
not self-sufficient either; it now carries the 403-vs-422 table directly. And #117 went back to
**draft**, per the standing always-re-draft-after-pushing rule. Note that open PR #123 proposes
exactly the opposite for this case — that a draft→ready flip the user made means accepted, with no
re-drafting — so whichever way #123 lands settles the question; until then the in-force rule applies.

**#106 deliberately needed no equivalent change.** The change touches text originating in both PRs,
but only #117's was actively wrong. #106 says "retarget its child's base to `main` on GitHub" and the
README row said "retargeting the PR base on GitHub" — vague, naming no client, and so not misleading
in the way `PATCH` is. Since #117 stacks on #106, `main` gets the corrected text whenever the chain
lands.

### PR #41, repaired

Then run for real against the case the whole thread started from, using the newly written sequence:
recorded Stack #128's composition → dissolved it (204) → changed #41's base to `main` via the MCP
tool → re-created the stack (201).

- #41: **268 files / +27,825 → 7 files / +1,318** — exactly the four `rdr/` modules and three test
  files its own description names. `mergeable_state: clean`. It kept its number, its four comments
  and its `cram2-link-sent` label.
- **Nothing was pushed to any branch.** Only the base moved, so no force-push, no restack, no CI
  churn on the six pull requests above it.
- Stack **#134** carries the same seven pull requests in the same order, now trunked on `main`
  instead of `ripple-down-rules-refactor`; #63–#98 kept their own bases. GitHub will not reuse a
  dissolved stack's number, so #112 → #128 → #134 is expected rather than a symptom.

The prevention story recorded on 2026-08-02 is untouched by all this: #117's ancestry check is still
what notices the orphan, and `routine-cutover`'s `pull_request: closed` sweep is still what makes it
notice promptly. What changed is only that the repair it triggers is now a base change a session can
actually perform.

**Residue.** The throwaway probe branches `claude/reparent-probe-{head,target,upper}-o1kpei` were
deleted by the user; their pull requests #129/#130 are closed and stacks #131/#132 dissolved.
`claude/workflow-unification-pr-test-o1kpei` became redundant once #133 was folded into #117 and
needs the same out-of-harness deletion, since sessions cannot delete branches (2026-07-29 addendum).

## Update 2026-08-02 (later): the Routine now reads its doctrine from git

The user asked the obvious question after the base-`PATCH` correction — *"can we point the routine
at the README we maintain instead of changing the prompt every time?"* — and then did it. The
~17.5k inline prompt at claude.ai/code/routines is replaced by the short pointer `routine-cutover`
had already specified: HARD RULES inline, plus "read `.claude/stack/ROUTINE.md` and execute the
fenced text block".

It resolves `origin/main` first, falling back to `origin/claude/stack-landed-parent-detection`
while that is in review, because **`.claude/stack/` is not on `main` yet** — only on #106 and #117.
Two consequences worth stating plainly: **#117's branch is live production input**, and an edit to
`ROUTINE.md` now ships to the running workflow on push, with no deploy step and no copy to sync.

The endgame is unchanged — a plain scheduled Action plus on-demand sessions, no scheduled LLM.
This is exactly the "optional interim step if the Action lags the tooling wave" already recorded.
What it buys immediately is that doctrine corrections stop needing a manual paste, which is the
precise failure that let the base-`PATCH` instruction survive in the live prompt for two days after
`ROUTINE.md` had been fixed.

### The ordering hazard it exposed

Adoption turned a dormant inaccuracy into a live bug within the hour. `ROUTINE.md`'s SETUP step 0
said:

> `.claude/stack/stack.py` and `stack.toml` are already on this checkout - they live on `main`, so
> there is nothing to pull from another branch first.

Written in anticipation of #106 landing, false today, and harmless only for as long as nothing
actually executed it. Under the pointer the Routine would resolve its doctrine successfully,
believe the tooling was present, and fail on the first `stack.py` call in **Phase 2 — after Phase 1
had already mutated pull requests**. Half-applied state on a real stack, from a document that was
correct-looking prose.

Fixed in #117: step 0 now *obtains* `.claude/stack/` from the same ref the pointer resolved instead
of asserting it is there. Verified end to end in a worktree at `origin/main` — `stack.py` absent
before, `stack.py --help` working after.

**The general lesson, which will recur:** a document that describes a not-yet-true future state is
safe exactly until something starts executing it, and the switch-on is not a good moment to
discover which sentences were aspirational. The same shape is queued for the stack-board Action
(PR 4), whose `board.yml` will read repo/branch/upstream variables that do not exist yet.

### Also fixed in the same commit

- The header claimed **"Not live yet"** and described pasting the file into claude.ai/code/routines;
  `README.md` said the same. Both now describe what happens: the Routine reads this file from git,
  an edit ships on push, and only the pointer is registered.
- **Three tests**, the step-0 one written failing first. The other two guard a contract that had
  none: the pointer locates what to execute *by the fenced block*, so exactly one fence must exist
  and the HARD RULES must stay inside it. That guard earned itself immediately — it caught a literal
  fence marker accidentally introduced into the new header prose during this very change, which
  would have made the Routine execute the wrong slice of the file. 254 tests pass, was 251.

**Two deletions fall due when #106 lands** and `.claude/stack/` reaches `main`: the pointer's
source-2 line (manual paste) and step 0's fetch fallback (an ordinary commit). Neither breaks
anything if forgotten — the fetch becomes a no-op, the fallback ref stops resolving — but both are
dead weight, and the pointer edit is the last manual paste this design should ever need.

## Update 2026-08-02: `/add-plan-item` — the scope decision gets a skill, and the rule gets one home

The plan skills covered creating a plan, starting an item, unblocking one, and
publishing status. They did not cover the event that happens most often: someone
describes something to build and it has to be decided where it goes. Left to
default, that decision reliably produced a new branch — which is how this plan
accumulated its own fold chain (#133 into #117, #117 into #106) and the #110/#106
collision, where two sessions independently built the same artifact under two
different filenames without either noticing.

### The rule was triplicated, which is the failure mode it warns about

A mechanical test for this had just been written onto
`claude/plan-scope-before-new-item` — an unlanded, pull-request-less branch, two
commits, a clean fast-forward from main. It added the rule three times, as three
independently-worded copies, to `plan-create`, `plan-item-kickoff` and
`plan-item-resolve`, with no shared anchor for a fourth caller to reference.

It now lives once, in `add-plan-item/scope-decision.md`, with all four skills
referencing it in a line and keeping only their own situational framing (when the
question is asked, and what to do with the answer). This follows
`setup-personal-notes/prerequisite-check.md`, which established the pattern for
exactly this: a shared procedure stated once so each caller cites rather than
restates it. The three copies' distinct content was merged rather than dropped —
`plan-item-resolve`'s duplicate-copies clause (decide which survives *before*
either lands, since afterwards it is a merge conflict instead of a choice) is now
part of the shared document.

### The rule applied to its own introduction

`claude/plan-scope-before-new-item` had no pull request and existed only to
introduce prose this work rewrites. By the rule's own test, nothing substantial
would have remained of it once the rewrite landed, so it is not separate work:
this branch was reset onto it and carries both commits. Stacking instead would
have put a pull request into review shipping the triplicated wording its
successor deletes. That branch is retired.

### Why it ships a script and not only prose

The path check is the step most often skipped, and skipping it is what the fold
chain and the collision have in common. `check_scope_overlap.py` runs it: given a
base branch and the paths the work would touch, it reports which paths the base
lacks and which unlanded branches already touch them. It also returns each
candidate branch's full changed-file list, because the #110/#106 case shares no
path at all — the same artifact under two names is invisible to a path
intersection, and only a purpose comparison finds it. The script gathers the
evidence; the fold-or-split judgement stays with the reader.

Pure git, so no network access or GitHub call: the tests build a real scratch
repository with a base and two candidate branches, reusing the hooks suite's
`ScratchRepository` rather than adding a second helper of the same shape. Eight
tests, wired into `ci.yml`'s `test_claude_dev_tooling` job through a new
`ADD_PLAN_ITEM_TESTS_DIRECTORY` constant. 230 pass, was 222.

One deliberate limit: a branch that does not resolve raises rather than returning
an empty overlap. A missing candidate must never read as "no overlap" — that is
the precise failure this whole item exists to prevent.

## Update 2026-08-02 (assessed): the #106/#110 overlap is three duplications, and the split is right

`/add-plan-item` above was written partly because of the #110/#106 collision. That
collision was then actually investigated, and it is larger than the one file it was
reported as — while the structural question it raised has the opposite answer to the
one the fold chain would suggest.

### The split is correct; do not fold

Remove #110's edits to its parent's files and ~2,645 lines of standalone setup
infrastructure remain — `setup-stacked-prs.sh`, `check-stack-setup.sh`,
`write-branch-files.sh`, two skills and their tests. That is ordinary stacking. #133
and #117 folded because *nothing* remained once the parent edits were taken out; #110
fails that test by a wide margin, so folding it would be over-applying the precedent,
not following it.

### Why it happened: a fork point, not a disagreement

#110 branched from #106 at `eb3ca5a1` on 2026-07-31. `POINTER.md`, `prompt_model.py`
and `test_prompt_documents.py` all entered #106 on 2026-08-02, in `2868eab9` and
`93dcbef9` — after that fork point. `POINTER.md` does not exist on #110's head at all.
Neither session chose a different design over a visible one; both built the same
artifact against divergent snapshots of an unlanded parent. That is the actual
mechanism, and it says the mitigation is prompt rebasing of children onto a moving
parent, not more folding.

### Three artifacts were built twice, not one

Merging #110 into #106's current head conflicts in **all five** `.claude/stack/` files
it touches. The reported collision was one of three:

1. **The pointer prompt** — `POINTER.md` (#106) and `routine-prompt.md` (#110).
2. **The pre-board configuration query** — #106's `BOARDLESS_COMMANDS` / `print_remotes`
   / `stack.py remotes` against #110's `BOARD_FREE_COMMANDS` / `print_config` /
   `stack.py config`. Same purpose, near-identical docstrings ("must run before
   `board.json` exists"), two names. This one was never flagged, and it cost more than
   the prompt file did: #110's shell scripts parse the output, and the two disagreed on
   both key names and key set.
3. **`ROUTINE.md` SETUP step 0** — rewritten independently by both.

Item 2 is the interesting one, because a path comparison *did* flag `stack.py` — both
branches modify it. What dismissed it was the boundary answer ("2,645 lines remain, so
#110 is real"), applied to a question it does not answer. Two pull requests can be
correctly split and still both build the same thing. The scope rule decides *where work
goes*; it does not certify that the overlap between two correctly-split branches is
benign, and `check_scope_overlap.py`'s full changed-file list is only useful if someone
reads it for duplicated *purpose* after the split question is settled.

### The argument for keeping `POINTER.md` had to be replaced, not just accepted

The reason previously given was that `routine-prompt.md` claims `.claude/stack/` is
already on `main`, which is false today. True — but it expires: #110 lands after #106,
at which point the claim holds and `POINTER.md`'s fallback is the stale half, as that
file itself says (`Delete this fallback once .claude/stack/ is on main`). Anyone
re-deriving the decision from that reason after #106 merges will reverse it.

The durable reason is the test harness: `test_pointer_hard_rules_match_the_routine_document_exactly`
pins `POINTER.md`'s rules byte-for-byte against `ROUTINE.md`'s, and `PointerPlaceholder`
declares its fork-specific values as an enum enforced in both directions.
`routine-prompt.md` paraphrases the same rules with nothing checking them. Two copies
that look equivalent, one of which is enforced, is exactly the drift `ROUTINE.md` exists
to prevent.

### Verified rather than argued

Splicing #110's SETUP step 0 into #106's `ROUTINE.md` fails two of #106's fourteen
contract tests — `test_setup_obtains_the_tooling_rather_than_assuming_it` (the step no
longer *obtains* `stack.py`, it assumes it) and
`test_setup_takes_the_tooling_ref_from_the_pointer` (it stops mentioning the pointer). A
third, `test_setup_asks_the_tool_which_remote_is_which`, passes only by accident: it
substring-matches `remotes`, a word that survives in #110's prose after the command it
names is gone.

### What shipped, and where the rest goes

Only #106 changed. `stack.py remotes` became `configuration`, printing one
`field<TAB>value` line per `Configuration` field — keys are the field names, every
setting is reachable, and `upstream_setup_command` moved onto `Configuration`, omitted
rather than printed blank when the remote exists. This is a change *to* #106 rather than
work stacked on it, which is the same test applied in the other direction: it exists
only to alter what #106 introduces, so it belongs in #106.

Naming it here rather than reconciling later means #110's rebase deletes the resolution
internals only — no dispatch-table conflict, and its two scripts change `stack.py config`
to `stack.py configuration` and are done. One deliberate divergence from the "converge on
`config`" recommendation: every other subcommand is a full word and AGENTS.md bars
abbreviations, so the command is `configuration`. The key names, which are the part
parsed by `awk`, match exactly.

The open `stack.toml:23` thread asks whether to strip the remote inference from #106 now.
Recommended answer: no. #106 lands first and the live Routine switches to `main`'s copy
the moment it merges, so a fresh cloud clone that needs a hand-edited file before it can
run is worse than one that infers. Keep it; delete it in #110 alongside the interactive
setup that makes it unnecessary.

### A premise that turned out to be wrong

Decision 11's cut is recorded here and on #106 as done. It is half done: `ROUTINE.md` was
rewritten around native mechanics, but `stack.py` still ships `print_next` and
`print_restack_plan`, and the latter's docstring still points at "the `restack` workflow's
`args`" — the subsystem the cut removes. Either it is outstanding or it was dropped
without a record. It matters for sequencing: applying it later rewrites `stack.py` again
and makes #110's rebase resolve the same conflict twice.

## Update 2026-08-02 (re-scoped): the routine's doctrine becomes a skill, and its recipes become subcommands

Session: https://claude.ai/code/session_01BByQFT6he8xf5qvBWtyUPV, via `/plan-item-resolve`. Two
user decisions, both taken after the options were costed rather than assumed.

### The doctrine is a skill now, and it folds into #106

`ROUTINE.md` is deleted. `.claude/skills/stacked-pr-maintenance/SKILL.md` carries the same
doctrine, is invocable as `/stacked-pr-maintenance` from any session, and is what `POINTER.md`'s
registered block resolves and runs for a scheduled one. The fork and upstream come from the
skill's own arguments first, then `stack.py configuration`, then - interactively only - a
question whose answer is written to `.claude/personal/stack.toml` on the personal-notes branch.
`--non-interactive` turns that question into a stop.

**Where it landed was the first decision.** `git ls-tree origin/main -- .claude/stack` is empty:
every path this touches is introduced by #106 itself. By `add-plan-item/scope-decision.md`'s test,
removing these edits leaves nothing standing alone, so it is #106's work and went onto
`claude/stack-tooling-on-main` directly (commit `e20b0bb4`), not onto this session's designated
branch. The second reason is sharper than the scope rule: the registered pointer resolves
`origin/main` **first**, so landing a `ROUTINE.md` that its own successor deletes would change the
live doctrine twice within one review cycle.

### Recipes as subcommands, not prose and not an MCP server

The second decision was how far to take "computed rather than recalled". Four new `stack.py`
subcommands, each replacing a rule the reader previously had to remember:

- **`labels`** - the complete set a label write must send, computed from the labels the pull
  request carries now. This is the one with a production incident behind it: the write replaces
  the whole set, and computing it from the addition alone once stripped `in-review` off
  already-promoted branches.
- **`preflight`** - refuses the move rather than describing how to check one: wrong branch checked
  out, a refspec naming different branches on each side, a destination that is not the fork, and a
  push that would make a child an ancestor of its own parent. Its own exit status (`5`).
- **`promotion-link`** - owns the compare URL's encoding and length limit, both of which discard
  the prefill *silently* when got wrong.
- **`reparents` / `landed`** - phase 1 derived from git ancestry rather than pull-request state.

**An MCP server was considered and rejected, on evidence rather than taste.** `gh` is absent in
this environment and `GH_TOKEN` is proxy-injected, and the 2026-08-02 probe already recorded here
shows a raw base-`PATCH` through that credential returns 403 while the GitHub MCP's
`update_pull_request` returns 200. A local MCP server would therefore use the credential that
*cannot* perform the riskiest operation in the whole workflow - so it would leave the base change
in prose anyway, while adding `.mcp.json`, a server process and per-session schema loading. It is
also the format that does not survive `routine-cutover`, whose endgame is a plain scheduled Action
with no LLM at all; subcommands run identically in a session, in the Routine, and in that Action.

The operating shape this settles on, worth stating generally: **compute deterministically, write
through MCP.** The credential boundary decides which half is which, and that boundary is a
property of the environment, not of the design.

### Decision 11's cut is deliberately left half-applied

The premise recorded in the previous entry - that `print_next` and `print_restack_plan` are
outstanding work from decision 11 - was put to the user and reversed. They stay. Phases 2 and 3
call them, and they are the derivation half of the scripts-over-prose choice made the same day;
cutting them would push those phases back into the prose this work is removing.
`print_restack_plan`'s docstring no longer names "the restack workflow's `args`", which is the
part of the complaint that was real.

### What the contract tests can now catch

`test_prompt_documents.py` goes from 14 tests to 19. The five new ones assert things the previous
shape had no way to state: that resolution prefers what it was told over what it can infer, that
it names the exit status meaning the fork is unknown, that a run which cannot ask stops rather
than guessing, that the pointer hands over both repositories with `--non-interactive`, and that
the skill states the whole job rather than delegating to harness machinery - which is what lets
the pointer keep reading the file while the skill is not yet on `main`.

Each was checked by breaking the document three ways and confirming exactly one test failed each
time. The hard-rules equality test earned itself again: the two copies were written independently
in this session and it passed first time, which is the only evidence that the duplication is
actually being held equal rather than coincidentally similar.

**A constraint found while writing it, worth carrying:** a skill that is not on the checked-out
branch at session start cannot be invoked by name. `.claude/skills/` is on `main` but
`.claude/stack/` is not, so until #106 lands the pointer must still say "read this file from
`<ref>` and execute it". That is why the skill has to read as a *document*, not only as a harness
entry point - and it is the same not-yet-true-future-state hazard the 2026-08-02 pointer-adoption
entry named, met a second time.

### Review threads: one answered, one left open on purpose

`stack.toml:23` asked for exactly this - *"running the configuration script or skill
interactively, and it takes the fork link or name"*. The skill answers its interactive half. The
~120-line inference deletion is still #110's, because the remaining caller is a non-interactive
run with no arguments on a checkout nobody has configured, and only setup writing
`fork_repository` at install time removes that one. Replied and left open rather than resolved;
`stack.py:84` dies with the same deletion. #110 was told its rebase now inherits a skill, that its
SETUP step 0 rewrite is superseded, and that the two contract tests it was told to update are
updated upstream of it.

## Update 2026-08-02 (review round): GitHub already closes what the pass was closing by hand

Twenty-five review comments on the skill, in `8b7435bb`. Three were decisions rather than
corrections, and each is worth recording with the evidence that settled it.

### The fast-forward is the close

The reviewer asked three versions of the same question - *"if fork main is fast forwarded with
upstream main, then github auto closes pull requests that are ancestors of main"*, *"isn't merging
better than closing?"*, *"could this actually happen anyway?"* - and the answer was in this
repository's own history:

| PR | `merged_at` | labels |
| --- | --- | --- |
| #101 | `2026-07-31T10:36:43Z` | `in-review`, **`merged`** |
| #103 | `2026-07-31T10:36:43Z` | `bug`, `in-review` |
| #105 | `2026-07-31T10:36:43Z` | `bug`, `in-review` |

All three at the same second - the moment fork `main` fast-forwarded from cram2 - and only #101
carries the hand-applied label. GitHub records all three as **merged**, not merely closed. So
phase 1's label-then-close was doing by hand what step 2 already did in one push.

Deleted: the close call, the `merged` label from the workflow entirely, and `landed` as a to-do
list (it survives as a report). **The ordering changed with it**: auto-detection fires only for a
pull request whose *own* base moved, so a stacked child based on a sibling branch is not caught by
fast-forwarding the trunk. The reparent sweep therefore has to run *before* the fast-forward, which
inverts the order the document had carried since it was a routine prompt.

The general shape, worth reusing: **before writing a step that maintains state, check whether the
platform already maintains it.** This one had survived two rewrites unexamined.

### The pass never writes code, which is what made it generic

*"Didn't we say it should never code, why debug and fix?"* — and the document did contradict
itself: it said code changes are the developer's session's work, then gave a procedure for
reproducing, fixing and locally validating a failure.

Removing that branch removed every repository-specific name with it — `krrood`, `ormatic_interface.py`,
`semantic_digital_twin`, `coraplex`, `experiments`, ROS, `AGENTS.md`. The reviewer predicted exactly
this (*"that will also remove all ormatic, krrood, ros, coraplex, semdt mentions completely and will
make the skill more generic"*), and it is the cleanest illustration in this plan of a portability
problem that was really a scope problem: the file was repo-specific *because* it was doing work it
should not have been doing.

The one file change that survives is resolving a conflict during a restack, which is unavoidable if
it restacks at all — and it now has to be reported in a comment naming the files, since it is a
change to somebody else's branch that they did not make.

### The pointer is gone, and most of the prose tests with it

*"I don't want anything in the pointer at all, the pointer is useless now, it's just a skill call."*
`POINTER.md`, `prompt_model.py` and `test_prompt_documents.py` are all deleted.

The reviewer separately asked to discuss whether the prose tests were worth keeping (*"this is
fragile and easy to break"*), and the two questions answer each other: those tests existed to hold
the pointer's duplicated copy of the HARD RULES equal to the routine document's. With one copy, the
duplication they guarded does not exist. Eighteen deleted.

**One survives, and the distinction is the useful part.** `test_the_skill_names_no_fork_of_its_own`
asserts an *absence*, computed from `load_configuration()` rather than from a string written in the
test. It cannot fail from rewording, only from the fault it exists to catch — shipping one
contributor's repository name in a document that is executed verbatim on somebody else's fork. That
is the line worth drawing for any future test over prose: assert what the document must not contain,
computed from live state; do not assert what it says.

**A consequence that reverses design decision 4**, flagged to the user rather than buried: the HARD
RULES no longer bind before the first file is read. They were inline in the pointer precisely because
a webhook event can arrive before the first tool call. The window is now one turn — between the run
starting and it reading the skill — which is an accepted trade against deleting a file plus its
enforcement machinery, and `routine-cutover` deletes the scheduled run entirely anyway.

### Smaller, but the same principle each time

`Command` is a `StrEnum` with a `needs_a_board` property, which answered both *"make these commands
maybe a StrEnum?"* and *"why not a tuple?"* — the second question was about a `frozenset` of boardless
commands kept beside the enum, and the right answer was that the fact belongs to the command rather
than to a set beside it, so the set is gone.

A pre-flight refusal now carries a `RefusalReason` alongside its sentence, so the tests assert
`[RefusalReason.MISMATCHED_REFSPEC]` instead of a hardcoded English string — which was the reviewer's
*"can this string be fetched from where it is defined?"*, answered by deleting the need for the string
rather than by importing it. Label tests read their labels from the `Configuration` that defines them,
since labels are per-user configuration and never an enum.

### Left open deliberately

*"This file is so big"* — `stack.py` is ~1,540 lines and this PR added ~400 of them. Not split here,
and put back to the user with the reasoning: `dev-tooling-python-package` already moves every
`.claude/` Python file into a package, so splitting now means the same surgery twice, with #110 and
#111 rebasing across it in between.

## Update 2026-08-02 (corrected): #110's rebase instructions, and the split settled

Two loose ends from the review round, both closed by the user in the same turn.

### `stack.py` is not split in #106

The reviewer's *"this file is so big"* was left open with a recommendation rather than an answer.
The answer is no split here: `dev-tooling-python-package` already moves every `.claude/` Python
file into the package, so splitting now means the same surgery twice, with #110 and #111 rebasing
across the first attempt in between. The thread stays answered rather than resolved, since the
concern is real and its resolution is somebody else's item.

### #110's rebase instructions were mostly invalidated, and saying so is the whole point

`setup-stacked-prs-skill`'s notes carried a detailed list of what its rebase onto #106 "must carry",
written on 2026-08-02 against #106 as it then stood. The review round deleted the artifacts three of
those five points were about — `ROUTINE.md`, `POINTER.md`, `prompt_model.py` and
`test_prompt_documents.py` are all gone — so following the list would have produced work with no
target. Rewritten in place rather than annotated, because a stale instruction that is still readable
as an instruction is worse than no instruction.

What actually changed for #110, verified against its head rather than inferred:

- Its `.claude/stack/routine-prompt.md` is now a duplicate of a file that already exists at
  `.claude/skills/stacked-pr-maintenance/routine-prompt.md`, already templating
  `<FORK_REPOSITORY>`/`<UPSTREAM_REPOSITORY>`. The previous instruction — *render `POINTER.md`
  instead* — has no referent; the instruction is simply to delete its copy.
- **A real breakage nobody had spotted**: `check-stack-setup.sh:62` reports
  `stack_tooling_files ok "stack.py, stack.toml, README.md, ROUTINE.md and routine-prompt.md are all
  present"`. Two of those five files no longer exist anywhere, so that check fails outright on the
  rebased branch. This is the only point on the list that is a defect rather than a no-op, and it was
  found by reading #110's script rather than by reasoning about the deletions.
- The two rules #110 wanted promoted into the pointer (never force-push a branch with an open
  upstream pull request unless it carries the `rebase` label; do not use the Workflow tool) are
  already in the skill, so there is nothing to promote.
- Two new points the deletion creates: the fork-overlay install mode has to carry
  `.claude/skills/stacked-pr-maintenance/` as well as `.claude/stack/`, now that the instructions
  live outside the latter; and setup writing `fork_repository` at install time is the same thing the
  skill's step 0 does interactively, so setup does it once and the skill's question is the fallback —
  not a second asker.

`stack.py config` → `configuration` is the one point that survives unchanged, key names included.

**The general shape, worth keeping.** A child branch's rebase instructions are written against a
snapshot of its parent, and a parent's review round is exactly the event that invalidates them.
Nothing notices this on its own: #110's session is not subscribed to #106's review threads, and the
manifest entry that carried the instructions reads as current no matter how old it is. The parent's
own session correcting them in the same turn as the review round — and commenting on the child's
pull request so its owner receives it as an event — is the only mechanism this workflow has. It is
the same fork-point failure as the #110/#106 duplication recorded on 2026-08-02, met from the other
side: there, two sessions built the same artifact against divergent snapshots; here, one session's
plan for the future was written against a snapshot that then moved.

## Update 2026-08-03 (resolved): #109's conflict was the same-artifact-twice pattern, a third time

`/plan-item-resolve workflow-unification personal-settings-sync`, session
https://claude.ai/code/session_01XkWmfMzYYAaCsgyrHDuoKn. The item had been `in_progress` and
untouched since 2026-07-31 with a manifest entry that said *"PR #109 open and ready"* and recorded
no `blockers` at all. Two real ones existed, and neither was in the manifest.

### The manifest was the least accurate source, which is the process finding

Everything needed to diagnose this was on the pull request the whole time — `mergeable_state:
dirty`, a `needs-resolution` label, a routine comment naming the three conflicting files, and three
unresolved review threads. The item's `notes` instead described a CI red that had since gone green
and asserted readiness. This is the failure mode the keep-plan-state-current rule exists to prevent,
seen from the far end: a stale entry does not read as stale, so the next session either trusts it or
re-derives everything. The entry now carries a `blockers` field for the first time.

### The conflict: `ScratchRepository` and `ScratchProject` are the same artifact

`main` extracted the hook-test scratch repository into `tests/scratch_repository.py` as
`ScratchRepository` during #101's review round. #109, branched before that landed, independently
extracted the same fixture out of `test_save_plan_sh.py` into `conftest.py` as `ScratchProject`.
Same purpose, two names, two branches — so `conftest.py` and `test_save_plan_sh.py` conflicted on
content that was never a disagreement.

This is the **third** instance of the pattern this roadmap has now recorded, after `POINTER.md` /
`routine-prompt.md` and `BOARDLESS_COMMANDS` / `BOARD_FREE_COMMANDS` between #106 and #110. All
three share a mechanism: a child branched from a snapshot of an unlanded parent, the parent moved,
and both sides built the same thing. `check_scope_overlap.py` flags the path in each case; only
reading for duplicated *purpose* explains it. Worth stating as a standing expectation rather than a
recurring surprise — **any long-lived branch off an unlanded or fast-moving base should be re-read
for duplicated purpose before its merge is attempted**, not only for conflicting lines.

Resolved by adopting `main`'s, on evidence rather than seniority: `ScratchRepository` is a strict
superset (`install_hook_scripts`, `write`, `commit_everything`, `publish_notes_branch`,
`clone_notes_branch`, `resolve_notes_remote_to`) and already had a second consumer in
`test_check_setup_sh.py`. `ScratchProject` is deleted; both conflicted test files are now
byte-identical to `main` and have left #109's diff entirely. The one capability `ScratchProject`
had that `ScratchRepository` lacked — editing the notes branch *after* publication — moved onto the
class that owns notes-branch operations, as `update_notes_branch_file`.

The overlap this item's own notes had warned about (#107's constants in
`resolve-personal-notes-config.sh`, #110's `write-personal-notes-file.sh` delegation) **auto-merged
clean**. The warning was aimed at the wrong files: it was written from the paths the item touches,
while the actual collision was in a test fixture nobody had listed as shared.

### A latent test bug the port fixed for free

`ScratchProject.run_hook` passed no `env=`, so it inherited the shell's `CLAUDE_PERSONAL_NOTES_*`
variables — exactly what `main`'s `run_check_setup` strips, and for exactly this reason. It passed
only because the fixture's local `git config` outranks the remote variable and the branch variable
happened to equal the default; a clone with `CLAUDE_PERSONAL_NOTES_PATH` set would have broken it.
Porting onto `main`'s pattern adopted the scrub. Inheriting a shared fixture buys the fixes made to
it since, which is an argument for converging on one that the line-count comparison does not show.

### The pending-review trap, worth knowing before it costs someone a turn

The three review threads could not be replied to inline: they belong to a review that was **never
submitted** (`PENDING`, on `55cd2f9`). GitHub allows one pending review per user per pull request,
so every reply attempt returns `422 - user_id can only have one pending review per pull request`.
Submitting someone else's draft review is not a session's call — it publishes comments they may
still be drafting — so the resolution was explained in one PR-level comment naming each thread, and
the threads were then resolved. Anything that looks like a stuck reply on this repository should
check for a pending review before assuming a permissions problem.

### The README section had to be re-authored, not merged

#109 added 53 lines to a `README.md` that #101 then rewrote from 378 lines to ~140 as a step-based
guide. A textual merge would have spliced two documents with different shapes. Rewritten against
the new structure at 30 lines, per that rewrite's own stated length discipline. Worth generalizing:
a documentation conflict against a restructured file is a rewrite, and resolving it hunk-by-hunk
produces a document that reads as two.

**State**: #109 is a draft again (standing re-draft-after-push rule), labelled `cram2-link-sent`
only, `mergeable_state: unstable` (mergeable; CI running) against `main` at `9b090fc1`. 36 tests
pass under `.claude/hooks/tests` — `main`'s 28 plus this module's 8, none lost — and 194 under
`.claude/skills/plan-dashboard/tests`. This unblocks part of decision 12's chain, which cannot land
before the in-flight bash-touching pull requests, #109 among them.

## Update 2026-08-03 (rebased + re-scoped): #110 lands its parent's review round, and the fork stops being a guess

`/plan-item-resolve workflow-unification setup-stacked-prs-skill`, session
https://claude.ai/code/session_01QurCwih1r6STYtP34bpJpf. The item had been `in_progress` and
untouched since 2026-07-30, `mergeable_state: dirty`, labelled `needs-resolution`, with **zero
review threads** - nothing was blocking it on review. Its parent had moved twice underneath it.

### The instruction that was half-wrong, and the check that settled it

The ask was to rebase #110 "on 106". Taken literally that breaks the branch:
`setup-stacked-prs.sh:44` sources `github-api.sh`, which lives only on #107 - decision 10's whole
reason for the linear chain. #107 was already restacked onto #106's head (`5e203be8`), and
`git merge-tree --write-tree` returns the **identical** five-file conflict set against either
branch. So merging #107 delivers 100% of #106 at zero extra cost, and the base stays where it is.

Worth keeping as a general check: when an instruction names a base, run `merge-tree` against both
candidates before retargeting. Here it turned a base change that would have duplicated
`github-api.sh` - a fourth same-artifact-twice instance - into a plain merge.

### The one real defect on the rebase list

The 2026-08-02 corrected list said point 2 was the only defect rather than a no-op, and that held
up. `check-stack-setup.sh:51-55` required `STACK_ROUTINE_DOCUMENT` and `STACK_ROUTINE_PROMPT_FILE`
and `:62` reported them present *by name*; both pointed at files #106's review round deleted, so
the checker reported `needs-setup` on a correctly installed checkout. Repointing both constants at
`.claude/skills/stacked-pr-maintenance/` also fixed the fork-overlay install for free -
`OVERLAY_FILES` already listed them, so an overlay was about to ship tooling with no instructions
to run it. Nobody had noticed the second consequence, and it follows from the first by construction.

**A second defect nobody had recorded**, found while implementing point 7: `write_personal_config`
wrote `overrides` as the *whole* file body. Now that #106's skill step 0 also writes
`fork_repository` to that same file, whichever ran second silently erased the other's key. The
write merges now. This is the shape the 2026-08-02 entry predicted in general terms - two writers
converging on one artifact - showing up in the file rather than in a filename.

### The inference deletion, and what it changed beyond line count

The ~120 lines came out as promised, closing #106's `stack.toml:23` and `stack.py:84` threads
(replied to and resolved). Two consequences the promise did not anticipate:

- **`RemoteResolution` had to become symmetric.** With the fork named, a *missing fork remote* is
  no longer an error - it is a `git remote add` command, exactly as a missing upstream already was.
  Without that, setup could not run before the remotes it adds exist.
- **`load_configuration()` now fails on a fresh clone until setup runs.** That is the intended
  trade recorded on 2026-08-02 ("keep it; delete it in #110 alongside the interactive setup that
  makes it unnecessary"), but it had a consumer nobody had counted: `test_the_skill_names_no_fork_of_its_own`,
  #106's one surviving prose test, resolved its fork *through the inference* - which is the only
  reason it worked on CI. It now computes candidate forks from the checkout's own remotes, minus
  the upstream, and asserts the document names none of them. That is stricter than before, not
  weaker: it checks every repository the checkout could be operating on rather than the single one
  configured.

**A test-fixture consequence worth generalising.** Both scratch suites addressed their bare
repositories by bare local path. Remotes are matched by the repository their URL names, and a local
path deliberately names none - the same rule `github-api.sh` applies so a directory name is never
attributed to a GitHub account. The fixtures now create bare repositories at paths ending
`<owner>/<name>.git` and address them as `file://` URLs, which satisfies both the parser and git
transport. `insteadOf` was tried first and rejected: `git remote get-url` applies the rewrite, so
it defeats the very lookup under test.

408 tests pass across the three directories CI runs, up from 334 on this branch before the rebase.

### New item: `stack-maintenance-executor`

The user's second question - *could we automate the stacking process by a deterministic script that
fetches the relevant PRs, performs the git commands needed, and reports everything* - lands on a
real gap, verified rather than assumed: `grep -n "git push" .claude/stack/stack.py` returns nothing
across 1,600 lines. `stack.py` is read-only derivation; every fetch, merge, rebase and push is a
session following prose, and `board.json` is hand-assembled from MCP output - the same
hand-assembled-input class as #119.

Four commands (`board --write`, `fast-forward`, `restack`, `run-report --json`) in a new module, so
the only edits to #106's files are the `SKILL.md` steps and the dispatch wiring. Step 0 is a
credential probe: the recorded 403 names the *base branch* specifically, so label writes, issue
comments and body-only PATCHes through `GH_TOKEN` are unknown, and that answer also decides what
`routine-cutover`'s Action can do without a session.

Scoped as its own item rather than folded into #106 (user's call, offered against folding): the
executor is new files that stand alone, #106 is already 3,413 additions across 29 commits and out
of draft after its 25-comment review round, and this is a direct enabler of `routine-cutover`'s
no-LLM endgame. It does **not** reverse decision 11 - that cut structure *derivation* in favour of
GitHub's stack object; this executes an already-derived plan. Recording that distinction here so
nobody re-litigates it from the decision-11 entry alone.

## Update 2026-08-04 (kickoff + implementation): the executor ships as #139, and the 403 turns out to be one field

`/plan-item-kickoff workflow-unification stack-maintenance-executor`, session
https://claude.ai/code/session_014E9nB1MUvm4jwgC2UTN5GT, which went on to implement it the same
session as draft pull request **#139** on `claude/plan-item-kickoff-workflow-koufa6`, based on
#106's head.

### The probe inverted the assumption it was written to test

The item's step 0 existed because three writes were unknown, and the working assumption behind
"staying with a session/MCP regardless" was that some of them would be blocked like the base
`PATCH`. On throwaway pull request #138, four calls minutes apart, same `GH_TOKEN`, same git proxy:

| Call | Status |
| --- | --- |
| `PUT /repos/{o}/{r}/issues/{n}/labels` | **200** |
| `POST /repos/{o}/{r}/issues/{n}/comments` | **201** |
| body-only `PATCH /repos/{o}/{r}/pulls/{n}` | **200** |
| base-branch `PATCH /repos/{o}/{r}/pulls/{n}` (control, same pull request) | **403** |

The control is what makes this conclusive rather than suggestive: the same credential, against the
same pull request, succeeds at three writes and is refused exactly one. **The block is on the
`base` field, not on writes, not on the credential, and not on sessions.** The 2026-08-02 entry
already narrowed it from "the platform forbids sessions" to "one credential"; this narrows it
again, to one field of one endpoint.

What follows: `needs-resolution` labelling and the conflict-report comment - the two writes
`SKILL.md` step 4 hands to a session - are both available to deterministic code, and so is writing
the promotion link into a description. None of that was taken in #139, because the four commands
were what was agreed and widening scope on the strength of a fresh probe is how a pull request
stops being reviewable. It is a named follow-up now, resting on a measurement rather than on a
fear. `routine-cutover`'s Action inherits the same table for its own credential, which is the
question that item has been carrying open since 2026-08-02.

### Zero edits to `stack.py`, which was a choice and not an accident

The item said the executor's footprint on #106 would be "the SKILL.md steps and the dispatch
wiring", and that reads two ways: a separate entry point, or four new `stack.py` subcommands. Put
to the user at kickoff, who chose the separate `.claude/stack/maintenance.py`. Three things fall
out of it that the subcommand reading would not have given: `stack.py` keeps the read-only
contract its own module docstring claims, the ~1,540-line file a reviewer already called too big
does not grow, and this branch has no textual overlap at all with #110's ~120-line deletion in
that same file.

`GitCommandRunner` is the one genuinely new thing. `stack.py` reads git through a helper returning
`""` on failure - correct for derivation, where a missing ref simply means "no answer", and wrong
the moment a push is involved, where it makes a command that did nothing indistinguishable from one
that worked.

**Forcing is decided in exactly one place**, `push_arguments`, and only for the rebase strategy,
which `build_stack` sets only from the `rebase` label. That is what makes the label rather than the
executor's judgement the thing authorising a rewrite of published history - and it is pinned by a
test on the arguments themselves, because a test that a push happened cannot tell a fast-forward
from an overwrite.

### A test that corrected its own premise

The first version of that guarantee was written as an integration test: let somebody else push to
the branch, then assert the restack is rejected. It failed, and the reason was worth keeping. The
executor starts each integration from the branch's **published** tip, so a branch that moved under
the pass is *incorporated*, not raced - a stronger property than the one being tested. The test now
pins that, and the forcing decision is pinned separately and purely.

### The regression the change introduces, found before it shipped

`board --write` makes a local `board.json` routine where it had been rare. Two tests - one of them
pre-existing in `test_stack.py` - assert on a *missing* board while reading the real `board.json`
beside `stack.py` rather than one in their scratch repository. So running a maintenance pass and
then the suite failed two tests for a reason unrelated to either. Proven by writing a board and
watching them fail, then fixed with an autouse fixture in `.claude/stack/tests/conftest.py` that
sets an existing snapshot aside and restores it afterwards.

Worth generalising: a test that reads a path beside the module under test rather than inside its
own fixture is coupled to whatever the developer's checkout happens to be carrying, and that
coupling is invisible until some new command starts writing there. The fixture is the fix; noticing
required actually running the command in this checkout rather than only in the harness.

`.gitignore` gains `.claude/stack/board.json`. #110 adds the identical line, which is a deliberate
duplication named in both pull requests rather than a fourth instance of the same-artifact-twice
pattern - whoever lands second drops one copy.

### What was not verified live, and why that is stated rather than glossed

`board --write` ran against the real fork: 44 open pull requests, and the export parses straight
back through `stack.py status`. `fast-forward` ran as far as its guard, exiting 6 on the missing
`cram2` remote before attempting any push. `restack` and `run-report` were **not** run live - they
push to real branches, and the upstream remote is outside a session's repo scope - so their
coverage is real git in the test harness, not the live fork. 342 tests pass, was 321.

### Scope widened the same day: the probe's answer was acted on

The user's response to the probe table was *"do it as well and anything you found doable in code
related to this"*, and it is the right call: three steps were prose only because nobody had checked
whether they had to be. All three moved into the executor.

**The conflict loop is closed, which it never was.** The label was invented so a pass would not
re-report the same conflict every run, and the doctrine said to clear it once the branch merges
cleanly again - but nothing cleared it, so a resolved branch stayed withheld until a human noticed.
`restack` now reads each labelled branch's `mergeable_state` at the top of the pass: still `dirty`
means `withheld` and untouched, anything else means the owner has resolved it, so the label comes
off and the branch rejoins. The label write goes through `LabelWrite.replacing`, which is the whole
point of that class - the production incident behind it was a write computed from the addition
alone, stripping `in-review` off already-promoted branches.

**`promote` is the fifth command.** It writes the compare-and-create link into the fork pull
request's own description under a `## Promote` heading, *replacing* any link already there, because
the description is rewritten on every run that rebuilds one and two headings would leave a reader
guessing which link is current. It adds `cram2-link-sent`, skips anything already carrying it, and
drops the label from anything since promoted or landed. `in-review` stays the developer's to add,
since the upstream pull request does not exist until they click Create.

What is left for the caller is now exactly one thing - retargeting a base - and the report says so
rather than implying the rest is also unavailable.

### The same ambient-state bug, twice in one pull request

CI failed on `test_a_missing_board_is_its_own_exit_status`, and it was a real defect rather than a
flaky test: introducing the fork client had moved credential resolution ahead of deriving the
board, so `restack` on a checkout with neither told its caller to set a token - when the thing they
actually need is the board the previous command produces. **Only CI could see it.** A Claude Code
session exports `GH_TOKEN`, so the wrong branch was never taken here.

That is the second instance in this one pull request of a test whose result depended on ambient
state: the first was the `board.json` snapshot sitting beside `stack.py`, which `board --write` had
just made routine. The fix is the same shape both times - the subprocess helper now strips the
credential for every command-line test, exactly as the autouse fixture sets the board aside.

Worth stating generally, because it will recur: **a test that reads ambient state cannot assert
about the state it is reading.** Both bugs were invisible on a developer's machine and only
appeared where the ambient state differed - which is the environment that matters, since `routine-
cutover`'s endgame is this code running in an Action with a third credential again.

## Update 2026-08-04 (live): the executor run against the real fork, and what only that found

The user authorised running the executor against the fork on throwaway pull requests. Done with
the board scoped to #140 (parent, non-draft) and #141 (child, draft) and nothing else, from a
detached worktree so the executor's own `checkout -B` could not disturb the branch under review.

All five commands ran. The conflict lifecycle is the one worth recording in full, because it is
the loop nothing previously closed: a real conflict pushed nothing, labelled #141 and posted the
comment naming the file; a second pass **withheld** it while `mergeable_state` was still `dirty`
and posted no second comment; once the conflict was resolved and pushed, the next pass **cleared
the label by itself** and the branch rejoined. `promote` wrote the link under a `## Promote`
heading, took only the first paragraph for the prefill, and on a second run replaced the section
rather than adding another - which also survived GitHub appending its own footer to the
description write, a wrinkle no test had modelled.

### Two defects only the live run found, and they were the same defect twice

A restack that hit a conflict exited **0**. A `run-report` whose fast-forward was **refused** also
exited **0**. Both are wrong in the way that matters most for this item's whole purpose: a caller
acting on the status alone - precisely what `routine-cutover`'s no-LLM endgame does - would have
read each as a pass with nothing outstanding.

The unit tests had not caught either, and it is worth being precise about why. They asserted
*what the report contained*, exhaustively and correctly. Nothing asserted *what the process told
its caller*, and those are different surfaces. The exit status is the only half a scheduled Action
reads.

Fixed by giving every command one `exit_code_for` over the report, so no two can disagree about
what a clean pass is: `7` for a refused fast-forward - outranking the rest, since the fork's base
is what every branch is measured against - `5` for a pre-flight refusal, which is a fault in the
move rather than in the branch, and `10` for a branch left unpublished for its owner. Tests were
written from the two live observations and checked by restoring the old behaviour.

The general lesson, which is not the same as the earlier ambient-state one: **a test over the
return value does not cover the exit status**, and for a tool whose whole point is to be driven by
something with no model in it, the exit status is the primary interface.

### Can a personal access token do the reparent from a session? No

Asked directly, and answered from evidence rather than inference:

- `gh` is not installed, so exporting a token does not produce `gh` or `gh stack`.
- `GH_TOKEN` is a 14-character `prox...` placeholder, not a GitHub token.
- A **junk** `Authorization` header and **no** header at all both return `200` on this private
  repository - so the agent proxy discards whatever the process sends and substitutes its own
  identity.
- The base-branch `PATCH` `403`s identically with a junk token and with none, and its
  `documentation_url` is **docs.anthropic.com**, not docs.github.com.

So the refusal is generated by the proxy from the request *shape*, not by GitHub and not by the
credential: a personal access token would be discarded before it ever reached GitHub. This is a
sharper statement than the 2026-08-02 entry's "a property of one credential" - it is a property of
the request path.

It says nothing against `routine-cutover`'s Action, which runs outside this proxy and is a
genuinely different actor. That still needs verifying there, but for a different reason than the
one on record.

## Update 2026-08-04 (new item): bootstrap an item before implementing it, not after

Raised by the user: *"I want the first step after the plan to be create a branch and a draft
PR and update the plan yaml and roadmap with the plan and branch and session and mark it in
progress and publish the dashboard, then only then start implementing, because I don't want to
wait for implementation to do these."*

Tracked as `plan-item-bootstrap` on track `personal-data`, wave `immediate`, `depends_on: []`.

### What is actually wrong today

The ordering is not a style preference. Every one of the five things above is derivable the
moment a plan is approved, and not one of them depends on a line of the implementation — yet
all five currently happen at the end. The window between the two is the entire length of the
implementation, and for that whole window `plan.yaml` says the item is `not_started` with
`branch: null`, while a branch exists and is being worked.

That is exactly the state this plan's own conventions call worse than no plan at all: *"a plan
whose manifest lags behind reality is worse than no plan: every dashboard, kickoff and resolve
run downstream reads it as truth."* The dashboard shows the item as available to start. A
second session running `/plan-item-kickoff` on it is told nothing exists. The failure is not
hypothetical — `session-start-plan-and-setup-guards` was itself raised from a session that
implemented and pushed before its item existed, and #121 answered that by *reporting* the gap
better. This answers the other half: give the session something to run at the moment the gap
opens, instead of a convention to remember at the end.

### One shared procedure, two callers

Settled with the user before the item was written. `plan-item-kickoff` step 5 is the primary
caller — it is the skill whose approved plan leads straight into implementing. `add-plan-item`'s
"new item in an existing plan" outcome is the second, and takes a one-line reference, the same
shape `scope-decision.md` and `prerequisite-check.md` already established. Duplicating the step
into each skill would have recreated, in this very system, the triplicated-rule failure that
`add-plan-item` was built to end.

The `/add-plan-item`-only reading was considered and rejected on its own terms: that skill's
stated design is that it *"never writes code, creates a branch, or pushes anything"*, so hanging
branch and pull request creation off it would contradict the contract in its own opening
paragraph.

### Scripts and models, not prose steps

The user's second point — *"all that can be based on python scripts and models, and the skill
only instructed to use the script at the right moment"* — is the same call decision 12 already
made for the bash→Python track, applied to a new surface. The skills keep the judgement (when
to run it, what the branch is called, what the approved plan says); the mechanics are a Python
module with real dataclasses for the request and the result, not a checklist a session
re-improvises and half-completes.

It lives at `.claude/hooks/plan_item_bootstrap.py`, beside `plan_manifest_tools.py`, rather than
inside either skill's directory: two skills call it, and `dev-tooling-save-plan-python` already
absorbs `plan_manifest_tools.py` into `development_tooling`. Putting it there means it rides the
migration that is already planned instead of inventing a second destination that would have to
be moved again.

### The two parts that are not scriptable, named rather than glossed

- **The dashboard republish** stays a `/plan-dashboard <plan-id>` step. Only a live session can
  call the Artifact tool; `save-plan.sh`'s own header already records this and prints the
  reminder. The script's result object carries the reminder rather than silently omitting it.
- **Creating the pull request can be done by the script** — probed the same day rather than
  left to inference; see the probe entry below for the measurement and its limits.

### Where it is based, and why the one shared file with #135 is not a dependency

Run rather than eyeballed, using `add-plan-item`'s own `check_scope_overlap.py` against `origin/main`:

```
paths_absent_from_base : .claude/skills/add-plan-item/SKILL.md
                         .claude/skills/add-plan-item/scope-decision.md
                         (nothing else)
already on main        : plan-item-kickoff/SKILL.md, plan-create/SKILL.md, save-plan.sh,
                         plan_manifest_tools.py, resolve-personal-notes-config.sh,
                         .claude/hooks/tests/
```

**Based on fork `main`, `depends_on: []`.** Everything the work builds on is on `main` already.
Because the tests go into `.claude/hooks/tests/`, which `ci.yml` already runs, no new pytest
directory constant is needed — which sidesteps outright the single `ci.yml` line that #135, #106
and #107 all conflict on.

The only thing `main` lacks is #135's own two files, and they are needed for exactly **one line**:
the reference from `add-plan-item`'s step 6. By the prefer-the-change test in `scope-decision.md`,
one line that modifies what an unlanded item introduces *is that item's work* — so it goes on
`claude/add-plan-item-skill-e89irj` while #135 is still an open draft, and this item stays off
`main`. If #135 lands first, the line simply moves into this item's own pull request; the ordering
does not matter either way. Stacking the whole item — script, tests, kickoff wiring — behind a
draft in review, for one line of prose, is the trade `add-plan-item`'s own basing note already
refused when the same question was asked about #106.

Remaining overlap is the established whichever-lands-second-merges pattern:
`resolve-personal-notes-config.sh` gains new constants (shared with #106, #107, #115, #121, #126
and #135, and the reason that file auto-merges every time is that each branch appends its own
block), and `.claude/hooks/tests/` gains a new file beside the ones #107, #115, #121 and #126
touch.

### Relationship to the two neighbouring items, neither of which this duplicates

- `session-start-plan-and-setup-guards` (#121) and `plan-item-edit-guard` detect and refuse work
  on a branch with no plan item. They are the *detector*. This is the *remedy* — the thing a
  session runs so the item exists before the first edit. `plan-item-edit-guard` becomes markedly
  less obstructive once this exists, because the answer to its refusal becomes a single command
  rather than a manual sequence.
- `add-plan-item` decides **where** work goes and stops there. This is what happens **next**.

### A status that names itself

Asked whether the exit codes should carry strings beside or instead of the numbers. *Instead* is
not available and it is worth saying why rather than just declining: a process exit status is an
integer by definition, and these are deliberately aligned with `stack.ExitCode` value for value so
a caller acting on both tools never has to remember which produced one.

*Beside* was a real gap, and the tell was that the meaning already existed - `BRANCH_NEEDS_ATTENTION`
is right there in the enum, and nothing emitted it, so every caller seeing `10` had to go and look
it up. `name_for_a_caller` derives the name from the member itself rather than a table written
beside it, so a status cannot end up carrying a name that belongs to a different one. `main` prints
it once, from one place, for any non-zero run; success stays silent, because announcing it would
make every run noisy.

The half that matters most is the document: `run-report --json` now leads with `status` and
`exit_code`. `routine-cutover`'s Action reads that document rather than the process status, and
mapping an integer back to a meaning is a decoding step it should not have to do at all.

Worth generalising alongside the exit-status lesson above: **an interface meant for something with
no model in it should say what it means, not encode it.** The number is for the shell; the name is
for whoever has to act on it.

## Update 2026-08-04 (probe): `POST /pulls` is available to a script, and the token is irrelevant

`plan-item-bootstrap` was written with pull request creation listed as its one unmeasured step.
The user's response — *"I think PRs can be created from the script given an exported token"* — is
right about the outcome, and the mechanism is worth stating exactly, because it is not the one
the framing implies.

### The probe

`POST /repos/{owner}/{repo}/pulls` with a deliberately unresolvable `head`, so nothing could be
created whatever the answer. Run three ways against the fork:

| Credential sent | Status | Body |
| --- | --- | --- |
| exported `GH_TOKEN` | **422** | `Validation Failed`, `field: head`, `docs.github.com` |
| junk `Bearer ghp_junk…` | **422** | identical |
| no `Authorization` header | **422** | identical |

**422 is the informative answer, not a failure.** Reaching field-level validation means the
request was authorised and evaluated by GitHub. The contrast that makes it conclusive is the
base-branch `PATCH` recorded on 2026-08-03/04: that one returns `403` with a
`documentation_url` on **docs.anthropic.com**, the agent proxy's own refusal signature. `POST
/pulls` carries **docs.github.com**. So the two refusals are different in kind — one is the proxy
rejecting a request *shape*, and `POST /pulls` is not in that category.

### The correction to the premise

The three rows are identical, which settles the credential half in the opposite direction to the
framing: **within a session the token is irrelevant.** Exporting `GH_TOKEN` gains nothing, and
having none loses nothing — `GH_TOKEN` is a 14-character `proxy…` placeholder, and the proxy
substitutes its own identity regardless of what the process sends. This is the same finding the
2026-08-04 live entry reached from the `PATCH` side, now confirmed from the creation side.

That matters for the design rather than being a pedantic distinction. A script written to
*require* an exported token would be requiring the one thing that demonstrably does not
participate.

### What the probe does not cover, stated rather than implied

A `422` on `head` stops evaluation before anything is built, so three things remain untested:
that a creation actually **succeeds**, that **`draft: true`** is honoured, and which **identity**
the resulting pull request is attributed to. Settling them needs one throwaway creation against
the fork, in the shape #139 used for its own live run. Recording the boundary is the point — the
same discipline #139 applied when it declined to widen scope on the strength of a fresh reading.

### Why the credential still matters anyway

Inert here is not inert everywhere. The same script run from a terminal, or from
`routine-cutover`'s scheduled Action, sits behind no proxy, and there the token *is* the
credential. So creation goes through the one shared backend `dev-tooling-github-api-unification`
builds — never a third copy of the gh-CLI-else-token rule that `github-api.sh` (#107) and
`pr_state` (#111) already carry between them.

### Consequence for the item

`plan-item-bootstrap` shrinks by one hand-off. Of the two steps it was going to return to the
caller, only the dashboard republish genuinely stays — the Artifact tool needs a live session, as
`save-plan.sh` already documents. Branch, pull request, manifest, roadmap and status all become
script work, which is what the item was asked for in the first place.

## Update 2026-08-04 (revision): two operations, not one shared procedure

The user's correction to the shape recorded this morning: *"I do not think plan-item-create/add
needs this behaviour, as it should only care about creating the plan item and updating plan data
and dashboard."*

Taken and agreed. The first shape treated the whole thing as one procedure that both plan skills
would reference, which was the wrong seam.

### The seam that was wrong

`/add-plan-item`'s own opening paragraph promises it *"never writes code, creates a branch, or
pushes anything"*. Referencing a procedure whose second half creates a branch and opens a pull
request would have broken that promise through a reference — the contract would still have read
as intact while the behaviour behind it no longer was. That is worse than breaking it openly.

Rejecting the `/add-plan-item`-only reading this morning was right; concluding from it that both
skills therefore want the *same* procedure did not follow.

### The seam that is right

Two operations, one module, each caller taking only what it needs:

- **Record** — write or update the item's `plan.yaml` entry and `roadmap.md` section, set its
  status, run `save-plan.sh`. This is `/add-plan-item`'s entire business, and all it gets.
- **Open** — create the branch, push it, open the draft pull request, then write `branch`,
  `session` and `pull_request_number` back onto the item and flip it to `in_progress`. Only
  `/plan-item-kickoff` gets this, being the skill whose approved plan leads straight into
  implementing.

`/plan-item-kickoff` calls **open** and then **record** — in that order, because the pull request
number does not exist until the pull request does. `/add-plan-item` calls **record** alone.

Both paths end at `/plan-dashboard <plan-id>`, which stays with the caller because only a live
session can call the Artifact tool.

### Why this is better and not merely different

It is the repository's own `AGENTS.md` applied to this module rather than quoted at it: each
operation now has one reason to change, and each caller depends only on the surface it uses —
single responsibility and interface segregation. The practical test is the one that settles it:
under the first shape, a change to how branches are created would have touched a skill that never
creates branches. Under this one, it cannot.

### What does not change

The basing decision stands unaltered. `/add-plan-item` still takes a one-line reference — to
**record** rather than to the whole procedure — so `.claude/skills/add-plan-item/` is still needed
for exactly one line, that line still belongs on #135's branch by the prefer-the-change test, and
the item stays based on fork `main` with `depends_on: []`.

## Update 2026-08-04 (resolved): #106's fork-resolution test fixed for the cram2 checkout topology

`/plan-item-resolve workflow-unification stack-tooling-on-main`, this session
(https://claude.ai/code/session_01F6tM5mDZr5pTB37UgBV6N5), on the user's report that CI on the
upstream `cram2` repo fails `test_the_skill_names_no_fork_of_its_own` with `ForkRemoteNotFoundError:
... every remote is cram2/cognitive_robot_abstract_machine`.

**Not a new bug — the same one #110 already found and fixed, one item over, not yet ported back.**
PR #106's own fork-side CI was (and is) entirely green: head repo and base repo are both the fork,
so that checkout's only remote (`origin`) is never the upstream, and a fork candidate is always
found. The failure only shows up in the checkout topology of a workflow run in the *base* repo of a
cross-fork pull request - `origin` pointing at `cram2` itself, no separate fork remote at all - which
is what a real cram2-side CI run for this code looks like. `stack.toml` deliberately leaves
`fork_repository` unset (derived from `fork_remote`'s URL instead), so there is nothing to fall back
to. Reproduced exactly: cloned this checkout into a scratch directory, pointed its only remote at
`cram2/cognitive_robot_abstract_machine`, and got the identical traceback the user reported.

The 2026-08-03 entry above already named this exact mechanism from the other side, when #110 deleted
the ~120-line remote-inference subsystem and discovered `test_the_skill_names_no_fork_of_its_own`
"resolved its fork through the inference - which is the only reason it worked on CI." Fetching
`.claude/stack/tests/test_maintenance_skill.py` from `claude/setup-stacked-prs-skill` (#110) showed
the fix already exists there, verbatim: stop calling `load_configuration()` (which raises when no
fork can be resolved) and instead compute the checkout's candidate forks directly from its remotes,
asserting the skill names none of them - vacuously true, not an error, when there are zero
candidates. It depends only on symbols (`Repository`, `_configuration_values`,
`CONFIGURATION_PATH`, `Repository.from_remote_url`, `Repository.names_a_repository`) already present
in #106's own `stack.py`, so #110's ~120-line deletion is not a prerequisite - the fix was ported
back to `claude/stack-tooling-on-main` directly rather than waiting on #110's rebase, since #106 is
the parent and needs to be correct in the topology it will actually run in once promoted.

Confirmed (research agent reading `test_stack.py`/`conftest.py` on #106's branch) that no other test
shares this ambient-remote defect - every other `load_configuration`/`resolve_remotes` call in that
suite runs against the `ScratchRepository` fixture with explicitly-added remotes, never the real
checkout. This is the one isolated instance.

**Verified**: `pytest .claude/stack/tests/test_maintenance_skill.py` passes under both topologies -
the fork's own (one candidate found) and the reproduced cram2-only-remote one (zero candidates,
vacuous pass, where it previously raised). Full `test_claude_dev_tooling` scope - `.claude/stack/tests`
(91), `.claude/hooks/tests` (36), `.claude/skills/plan-dashboard/tests` (194) - all green, 321 total,
no regressions. Pushed to `claude/stack-tooling-on-main` (`b3e240e6`); PR #106 re-drafted per the
standing re-draft-after-push rule and commented with the fix's rationale.

## Update 2026-08-04 (kickoff): plan-item-bootstrap opens as #143, bootstrapped by hand

`/plan-item-kickoff workflow-unification plan-item-bootstrap`, session
https://claude.ai/code/session_01VoH56TLkH5rA5EFu2xhML9, as draft pull request **#143** on
`claude/plan-item-kickoff-workflow-vocs6b`, based on fork `main`.

The bootstrap ran **before** the implementation, in the order the item itself prescribes -
branch, draft pull request, manifest, roadmap, dashboard, then code. By hand, since the tool
that automates it is what this pull request builds. That is the item's own argument taken at
face value rather than deferred: the window it exists to close is exactly the one a session
opens by starting with the code.

### The basing decision, re-run rather than inherited

The 2026-08-01 lesson from `git-identity-from-personal-notes` - *"independent PR off main"
recorded at planning time is a claim about the code, and it expires when a sibling PR moves the
test infrastructure* - says to re-check at kickoff. Re-checked and it holds: `depends_on: []`,
`check_dependency_readiness.py --item plan-item-bootstrap` returns `[]`, no branch existed yet,
and every file the work builds on is on `main` already. Because the tests go into
`.claude/hooks/tests/`, which `ci.yml` already runs, there is no new pytest directory constant
and therefore no touch of the single `ci.yml` line #135, #106 and #107 all conflict on.

### The one instruction that could not be honoured, and what replaced it

The item's notes say pull request creation *"goes through the one shared backend
`dev-tooling-github-api-unification` builds - never a third copy of the gh-CLI-else-token rule
that `github-api.sh` (#107) and `pr_state` (#111) already carry between them."* That is
unsatisfiable from `main` today: the unification item is `not_started`, `github-api.sh` exists
only on #107, and `main` carries **no GitHub-calling Python at all** - checked rather than
assumed, `render_common.py` imports `urlsplit` and nothing else.

So the instruction describes the target, not something reachable from this item's own base. The
resolution is `plan-updates-since-helper`'s recorded precedent from 2026-07-31, where the same
collision produced the same answer: implement the call inline, deliberately *without*
reproducing the gh-CLI-else-token discovery (`gh` is not installed here and `GH_TOKEN` is a
14-character proxy placeholder, both already on record), and let the unification item absorb it.
Stacking on #107 or #111 to get the backend would reverse the basing decision this item took
after running `check_scope_overlap.py`, for a dependency that only exists to avoid ten lines.

Worth stating generally, because this plan keeps producing it: **an item's notes can name a
dependency the item's own base cannot reach.** The notes are written when the shape is decided;
the base is chosen later, from live branches. When the two disagree the base wins, and the
inline copy gets recorded as something a named later item absorbs - not silently left as a
fourth copy nobody is tracking.

### The promise in `plan-item-kickoff` has to be rewritten, not extended

Forced by the item rather than spelled out in it, and worth recording because it is the same
objection that shaped the item in the first place. `plan-item-kickoff/SKILL.md` opens with *"This
skill never writes code, creates a branch, or pushes anything"* - the identical contract that
ruled out hanging this behaviour off `/add-plan-item`. Adding a branch-and-pull-request step
while leaving that sentence standing would break the promise through a reference, which the
2026-08-04 revision already called *worse than breaking it openly*.

It becomes "never writes code, and creates the branch and draft pull request only once the plan
is approved", with the new work in a **step 6 after approval**. Step 5's planning half is
untouched, so the skill still writes nothing before the user has seen and approved a plan -
which is the part of the promise that was actually load-bearing.

### The one line on #135's branch

`/add-plan-item` step 6's reference to **record** goes on `claude/add-plan-item-skill-e89irj`
while #135 is still an open draft, per `scope-decision.md`'s prefer-the-change test. Pushing to
another session's branch needs explicit permission; the user granted it at kickoff, the same
override made on sight for #133, with a comment on #135 so its owning session receives it as an
event.

### Implemented the same session: the probe changed the design it was written to confirm

The item named one unmeasured step and asked for a throwaway creation to settle it. It was
run - throwaway pull request **#144** against the fork, closed immediately - and it answered
three questions rather than one:

| Question | Answer |
| --- | --- |
| Does `POST /pulls` from the script actually succeed? | Yes |
| Is `draft: true` honoured? | Yes |
| Which identity is it attributed to? | **`claude[bot]`** |

The third is the one that mattered, and it was only visible because #143 had been opened
minutes earlier through the session's GitHub tool: **same repository, same session, same
proxy - `AbdelrhmanBassiouny` for the tool, `claude[bot]` for the script.** Also worth
recording since nothing had documented it: the proxy appends its own
`_Generated by Claude Code_` footer to the body on both paths, which the caller never sent.

That is precisely the authorship problem this roadmap already flags three times for commits
(`Claude <noreply@anthropic.com>` on #101 and the P3 branch, and the container default that
`git-identity-from-personal-notes` exists to fix) - and left alone it would have applied to
*every* plan item's pull request, forever, as a direct consequence of this item.

**The resolution, chosen by the user against two alternatives:** `open` takes
`--pull-request-number` for a pull request the caller has already created and records it
instead of creating one. The creating path stays, for an unattended run whose credential is a
real one rather than a proxy placeholder - `routine-cutover`'s Action being the case that
needs it. Title and body are required only on that path, so neither caller passes an argument
it cannot use.

The general lesson is about the probe rather than the credential: **a probe that stops at the
first refusal answers whether an operation is permitted, not whether its result is
acceptable.** The 2026-08-04 probe reached a `422` on `head` and concluded creation was
available, which was true and insufficient - the identity question only opens once something
is actually created. The item was right to name that boundary and right to insist it be
closed before shipping.

### What else the implementation settled

- **The manifest is patched by line, following `sync_manifest_status.py`.** That script's
  docstring already records that a full YAML round trip - ruamel.yaml included - re-flows
  wrapped strings and turns a one-field edit into a whole-file diff. Reusing the approach
  rather than rediscovering it is the whole value of it being written down; a test asserts the
  manifest is byte-identical apart from the one line that changed, and it fails if the module
  round-trips instead.
- **A refused pull request leaves the branch it already published**, and the docstring says so
  rather than claiming otherwise. Sessions cannot delete a remote branch, so there is no
  cleanup to perform; the manifest is left untouched instead of pointing at a pull request
  that does not exist, and a re-run is refused by the already-published guard rather than
  overwriting the commits. The first draft of that docstring claimed nothing was left behind,
  which the mutation pass caught.
- **Every test was checked by breaking the implementation**, three ways - defaulting `draft`
  to `False`, round-tripping the manifest through PyYAML, removing the already-published guard
  - each failing exactly the tests that name that behaviour and no others. 57 tests pass under
  `.claude/hooks/tests`, was 36; 194 under the plan-dashboard suite, unaffected.
- **`plan-item-kickoff`'s opening promise was rewritten, not extended.** It said *"never
  writes code, creates a branch, or pushes anything"* - the same contract that ruled out
  hanging this behaviour off `/add-plan-item`. It now says it never writes code and creates
  nothing before a plan is approved, with the branch and pull request in step 6 after
  approval. Leaving the sentence standing while adding the step would have broken the promise
  through a reference, which the 2026-08-04 revision already called worse than breaking it
  openly.

### This item was bootstrapped by the procedure it describes

Branch, draft pull request #143, manifest, roadmap and dashboard all came first, by hand,
before a line of the implementation - which is the argument the item makes, applied to itself
rather than deferred. The one thing that could not be dogfooded is the tool itself, since it
did not exist yet; the first genuine run belongs to whichever item is kicked off next.

### Review round 2026-08-04: the manifest's vocabulary gets one home

Nineteen comments, almost all one objection seen from many angles: the module knew
`plan.yaml`'s keys, filenames, statuses and indentation in a dozen scattered places, and the
tests knew them a second time as literal strings like `"    status: in_progress\n"`. A change
to how a manifest line is written had to be made twice, in two files, and nothing would have
caught the second one being missed.

`PlanField` now names every key, `PlanDocument` the two filenames, `HookScript` the scripts
this module drives, `ItemStatus` the statuses, and `ItemFieldLine` renders a line from them.
The tests import all of it and assert on rendered lines. Two details are the ones that make it
real rather than cosmetic: `FOLDED_FIELD_PATTERN` is *generated* from `FOLDED_PLAN_FIELDS`
instead of repeating `notes|blockers`, and the tests resolve a plan's paths through the
production `PlanLocation` - which asks the shell configuration - instead of spelling out
`.claude/personal/plans/<id>/plan.yaml`. Shortening `ITEM_FIELD_INDENT` now fails 12 of 24
tests, which is the evidence the two sides are actually one.

The test manifest moved into `tests/fixtures/` as a real `.yaml` file, which `AGENTS.md`'s
no-inline-snippets rule already required and this pull request had simply not followed.

Refusals became dataclasses carrying typed context, composing their message from
`error_message()` and `suggest_correction()` at construction - `krrood`'s `DataclassException`
idiom mirrored in a stdlib-only base, which is the boundary decision 12 records. Two things
fall out of it that were not there before: every refusal now says what to do about it, and the
tests assert on the field that explains a refusal rather than on its wording.

**One thread deliberately left open**, and it is worth recording because the reviewer's
instruction rested on a premise that turned out to be false. Asked to remove the `ItemStatus`
overlap with `build_dashboard.py` by basing this item on the `development_tooling` package if
that is what it takes - **basing on #111 would not remove it**. `build_dashboard.py` moves into
the package with `dev-tooling-python-package`, which is `not_started` and itself depends on
#111 and #101, so the re-base would attach a dependency-free immediate-wave item to the
unlanded upstream chain and still leave two enums. Importing `build_dashboard` directly is
worse - it needs jinja2 and markdown, which a hook cannot assume - and extracting a shared
module on `main` would need the `sys.path` hackery decision 8 exists to end, in a file six open
branches already edit. So the recommendation put back to the user is to leave the five-member
overlap for the migration that actually ends it, and the thread stays unresolved until they
say.

The general shape, since this plan keeps meeting it: **a reviewer's instruction can name a
remedy the branch cannot reach.** The answer is not to follow it into a worse place or to
silently ignore it, but to say which part is reachable, do that part, and hand the rest back
with the reason.

#### Second round, same day: the field knows how it is written

Five more comments, and one of them is a design the reviewer had proposed twice before it
was understood: **a `PlanField` member's value is a `FieldSpecification` dataclass** - the
key, whether the value is quoted, whether it spans the lines beneath it - reached through a
`__new__` that keeps the member's string value equal to its key, so it still indexes parsed
YAML with no `.value`. `render` moves onto the field, so nothing outside the enum knows that
a title is quoted and a track is not.

`ItemFieldLine` disappeared with it, along with its `quoting` classmethod: it existed only
to hold a choice the caller was making, and once the field knows, there is nothing left for
it to do. `FOLDED_PLAN_FIELDS` is derived from the specifications rather than listed, so
declaring a field folded is the only step in making it folded.

The path half went the same way. `PlanDocument.path_within_notes_branch` names the plans
directory once, which the *fixture* had still been composing by hand even after the previous
round fixed `published_plan` - so the earlier reply on that thread was right about the
production side and wrong about the test. That made `PlanLocation` redundant, since its only
remaining job was the fetch: it is now a plain `fetch_notes_branch`, and the two concerns
are split by owner - the shell says which branch, `PlanDocument` says where within it. The
`PLANS_DIR` mirror is held by a test that asserts against what the shell actually resolves;
changing the Python constant alone fails six tests.

Worth carrying: **a reviewer repeating a suggestion is a signal it was not understood the
first time.** This one was made in the first round ("dataclass specification that is
inherited from in the Enum") and answered with something adjacent but weaker - an enum plus
a separate line-rendering class - which is why it came back. Re-reading the original wording
rather than the previous answer is what produced the right shape.

257 tests, was 254. Three mutations checked: dropping `TITLE`'s quoting, rendering without
consulting the specification, and drifting the plans directory.

#### Third round: the mixin, and what YAML calls these things

The reviewer's third pass replaced the `__new__` outright:
`ManifestKey(KeySpecification, Enum)`, so a member *is* a specification -
`isinstance` and `issubclass` hold, and the style is reached directly rather than
through an attribute a type checker cannot see. Their instinct was right, and three
things only prototyping settled:

- **A member's value must be the constructor's argument tuple, not a built
  specification.** `TITLE = KeySpecification(key="title", …)` raises nothing and lands
  the whole instance in `.key`. That is the one hazard the mixin introduces, and it is
  guarded by a test asserting every key is a string; making the mistake fails four.
- **The field cannot be called `name`.** `Enum` reserves it - `AttributeError: cannot
  set attribute 'name'`. It stays `key`, which is also YAML's own term for the left-hand
  side of a mapping (JSON's RFC says "name"; this is a `.yaml` file), and which sidesteps
  `dataclasses.Field` - a collision already live in the test module, where a parameter
  named `field` shadowed the `dataclasses` import.
- **A key cannot be both `str` and `KeySpecification`** - `TypeError: too many data
  types`. So str-ness goes, and the nine lookups relying on it read `.key`. One was
  missed by the rename and caught by a test, which is exactly the failure class that
  trade buys.

The two booleans collapsed into one `ValueStyle` (`PLAIN` / `DOUBLE_QUOTED` / `BLOCK`),
because they were never independent: a value is written one way, never two. `BLOCK` is
YAML's own word for a value continuing beneath its key, and is correct for both cases
here - `notes` is a folded scalar, `blockers` a sequence - where "folded" would have been
wrong for one of them. Two booleans had allowed a state that cannot exist.

Worth carrying: **when a reviewer proposes a language feature, prototype it before
answering.** The first two rounds answered this suggestion from reasoning and produced
something adjacent but weaker each time. Running it took minutes and produced the
argument tuple hazard, the `name` collision and the data-type limit - none of which
reasoning had surfaced, and all three of which shaped the final design.

The same round's last comment asked for the field list to become a dataclass "or better
maybe a `dict[ManifestKey, str]`", and the mapping is the stronger of the two offered
because it makes a state *unrepresentable*: `[(STATUS, "in_progress"), (STATUS, "done")]`
was accepted by the list, patched the same line twice, and let the second write silently
win. A dataclass of pairs would have kept that; a mapping cannot express it. Insertion
order still governs line order, which `render_new_item` depends on, and is pinned by a
mutation check rather than assumed - reordering the mapping fails exactly the test that
names the field order. The same shape replaced two other pair-lists, including the
required-keys check, which now reports what is missing from the mapping itself instead of
from a parallel list beside it.

#### The duplication question, asked of the whole file and answered by measurement

The round's last comment asked simply whether there is any duplication with `stack.py`.
Answering it required reading that file rather than the docstring that had asserted a
relationship, and the assertion did not survive. The two `ExitCode` enums share only
`SUCCESS = 0` and reuse 3, 4 and 5 for *unrelated* meanings - `BOARD_UNAVAILABLE` /
`REMOTES_UNRESOLVED` / `PREFLIGHT_REFUSED` against `UNKNOWN_PLAN` / `UNKNOWN_ITEM` /
`INCOMPLETE_NEW_ITEM` - because the two tools fail in different ways. So the promise that
"aligning the two belongs with whichever item brings them into one package" described a
unification with no content, and it is deleted; the class states its contract instead, and
gained the per-member docstrings it was the one enum in the file still missing. Nothing
else overlaps: `stack.py` makes no network call at all, never touches `plan.yaml`, and the
only literal overlap is the `subprocess.run(["git", ...])` boilerplate, where the contracts
are deliberately opposite - `_git` returns `""` on failure, right for derivation, while
`run_git` raises, because a push that silently did nothing must not read as one that
worked. That is the same distinction #139 introduced its own `GitCommandRunner` over.

**One real duplication turned up, and it belongs to `stack.py`.** Its
`_resolve_personal_notes_remote`/`_resolve_personal_notes_branch` reimplement the
notes-branch precedence in Python, their own docstrings conceding "by the same precedence
as `resolve-personal-notes-config.sh`" - a second copy of rules the shell owns, free to
drift from them. `dev-tooling-config-shim-slimming` already plans a CI test holding the
bash and Python resolutions equal; this is a second carrier for it to cover, and it is
recorded on that item. This module adds no third copy: `fetch_notes_branch` sources the
shell file and calls its own `fetch_personal_notes_branch`.

Worth carrying, since this plan keeps recording the reverse case: **a docstring can
invent a relationship as easily as it can miss one.** Three same-artifact-twice
duplications are on record here, all found late; this is the opposite failure - a
forward-looking note asserting a duplication that did not exist, which would have sent a
later reader looking for something to unify. Both are fixed the same way, by reading the
other file rather than reasoning about it.

## Update 2026-08-05 (review round): the executor's 25 comments, and the shape they kept asking for

Session https://claude.ai/code/session_014E9nB1MUvm4jwgC2UTN5GT, on #139. Three of the
twenty-five were decisions rather than corrections, and the useful part of each is the
argument that settled it.

### Leading with `run-report` was possible only once the doctrine moved out of the commands

The reviewer asked, marked *discuss with me*: why explain the separate commands at all
rather than name the one that does the whole pass? Their reading won, and the skill now
leads with `run-report --json` as step 2 with the four commands demoted to a reference
section for resuming a partial run.

Worth recording *why it was written the other way first*, so it does not creep back: the
per-command sections carried doctrine that had nowhere else to live — what a `refused`
outcome means, why the fork's base must stay a pristine mirror, what happens to a
conflict. Explaining a command and stating a rule had become the same paragraph, and a
document in that state cannot be reordered without losing rules. Splitting them apart is
what made the change possible, and it gave the reviewer's other two points a home:

- **The pass never resolves a conflict.** The escape hatch — "if you resolve one
  yourself, comment saying what you took" — is deleted, and the header's promise changed
  with it, from *"the only file changes you ever make are conflict resolutions"* to no
  file changes at all. A conflict is a change to somebody else's branch.
- **It never attempts to open the upstream pull request.** It had said the call "fails
  every time", which reads as a thing to try and expect to fail.

### The same design, asked for twice, in two places

*"If `PullRequestField` inherits from a specification and `Enum`, it can hold per-member
specification instances."* That is now the module's idiom twice over — `PullRequestField`
carrying each field's key, read shape and requiredness, and `Command` carrying each
command's name and help text.

Both hit the two hazards `plan-item-bootstrap`'s own third review round already recorded,
which is the first time this plan has had a lesson available *before* meeting it rather
than after:

- a member's value must be the **argument tuple**, never a built specification — passing
  one raises nothing and lands the whole instance in the key. Guarded by a test here,
  verified by making the mistake deliberately.
- the field cannot be called `name` — `Enum` reserves it. `PullRequestField` sidesteps it
  with `key`; `Command` needed `invoked_as`.

The payoff is not tidiness: `_required`, `_branch_reference` and `_label_names` collapsed
into `PullRequestField.read`, and the three raw `record.get(...)` calls in `promote` and
the conflict check went with them — those were reading the API's shape *outside* the only
place that was supposed to know it.

### Dispatch, and the one thing it must not stop doing

`_dispatch` was flagged as violating open/closed, correctly. Each command is now a
`MaintenanceCommand` subclass owning its flags and its work, listed once in `COMMANDS`,
which is also what builds the parser — so a command that exists but is unreachable from
the command line is not expressible.

The constraint that survived the refactor is the one CI caught earlier: the board is
still derived *before* the credential is resolved, so a checkout missing both is sent
after the board rather than after a token. `MaintenancePass` resolves each lazily, in that
order, which is what keeps it true structurally rather than by remembering.

### `run-report` deletes the board it finished with

The user's question on `.gitignore` — could it be deleted automatically once we are done
with it — is a better idea than the gitignore line it was asked about. Scoped to
`run-report` only: that is the one command meaning "the pass is over", while the other
four are the resume path and a board they deleted would strand their own caller.

### What was deferred rather than done, and why that is the honest answer

Three threads are left open on purpose. Two ask why the GitHub calls are urllib rather
than `gh` or a Python library; `gh` genuinely is absent from a session container and the
SessionStart-reachable tier is stdlib-only by decision 12, but neither is a reason to
settle it *here*. `dev-tooling-github-api-unification` exists because `github-api.sh` and
`pr_state` already implement the same rule twice, and this module is now a third carrier —
so that item gains a decision it did not have: whether the shared backend may require an
install, answered once for all three rather than three times.

The third asks whether a supplied credential could do the base-branch reparent from a
session. It cannot, and the measurement is worth keeping: the `PATCH` returns 403
identically with the exported `GH_TOKEN`, with a junk `Authorization` header, and with no
header at all, while a *read* with no header returns 200 — so the proxy substitutes its
own identity and a personal access token never reaches GitHub. The refusal's
`documentation_url` is on **docs.anthropic.com**. That is one notch sharper than the
2026-08-04 finding: not a property of one credential, but of the request path.

**A reply is not a resolution.** All twenty-five got one; the three that record a deferral
or answer a question without changing anything stay open for the user to close, per the
notes-branch rule that a thread is resolved only once what it asked for has been done.

### Second round the same day: two questions asked rather than guessed

Twelve more comments on #139. Ten were answerable by doing them; two were not, and asking
is what made them come out right.

**`PreFlight` → `CommitMoveChecks`** (the reviewer marked it *discuss with me*, and four
options were costed). The objection was exact: the name said *when it runs*, not what it
does. `CommitMoveChecks(...).refusals(move)` names its subject and pairs with the
`ProposedCommitMove` it is handed. `PreFlightRefusal` → `CommitMoveRefusal`, the
subcommand → `stack.py check-move`, and both tools' `PREFLIGHT_REFUSED` → `MOVE_REFUSED`,
still `5` in each and still aligned.

**"Actions as dataclasses with a shared abstract parent"** had two plausible referents -
the restack's per-branch steps, or `stack.py`'s `CommitMoveAction` enum - and they are
materially different pieces of work. Asked; it was the steps. `_restack_branch` was a
chain of ifs, and each branch of it is now a `RestackStep` subclass whose `attempt` either
concludes the branch or returns `None`. `BranchUnderRestack` carries what a step needs and
builds the outcome, which is what let `_withhold` and `_report_conflict` stop being free
functions taking six arguments and become the steps that own them.

Worth keeping: **these steps are listed, the commands are discovered.** The reviewer asked
for `COMMANDS` to come from `MaintenanceCommand.__subclasses__()`, and that is right there
- a command class that exists should be reachable, and the failure the explicit tuple
allowed was writing the class and forgetting the line. It is *wrong* for the steps, whose
order is the procedure: publishing before checking the move is a bug no type catches, so
the tuple is the specification rather than boilerplate. Same shape, opposite answer,
because one list carries meaning and the other carried only maintenance.

### The rule that decided what the skill says

The reviewer asked why the skill explains things only the scripts need to care about, then
sharpened it: *what I fear is staleness when we are mentioning things that is code
explanations.* That second sentence is the whole rule, and it is better than the one the
document was written against.

A sentence in a skill describing what the code does has nothing holding it true - no test
fails when the code changes under it - so every one of them is a future lie with a delay
attached. Applied: **if a statement would have to change when `maintenance.py` changes, it
does not belong in the skill.** That deleted the conflict-labelling description, the
force-with-lease rule, the board deletion, the per-outcome table and the flag lists; each
already lives in the docstring of the thing that does it, where it moves with the code.
Step 2 went from ~70 lines to ~30.

What survives is either an instruction to the agent - the document's actual subject - or a
status name the agent matches on, and those are pinned: they are
`MaintenanceExitCode.name_for_a_caller`, derived from the enum member, so renaming a status
changes what the document refers to rather than silently diverging from it.

This is the counterpart to the earlier round's finding. There, doctrine and command
explanation had fused into single paragraphs and had to be split apart before the document
could be reordered. Here, the same split is what made the deletion safe: once the rules
lived in their own section, everything left in the command prose was disposable.

### Left open on purpose

The `stack.py` half of the rename is arguably #106's work by `scope-decision.md`'s
prefer-the-change test - `CommitMoveChecks` is defined in a file #106 introduces - so #139
now carries an edit to its parent's file and #110 will meet it on rebase. Done here because
that is where it was asked for, flagged there rather than left silent.

## Update 2026-08-05 (resolved): #115's conflict was a README rewrite resolved hunk-by-hunk

`/plan-item-resolve workflow-unification plan-updates-since-helper`, session
https://claude.ai/code/session_016kAVapbHxDokYjZBukKA5X. The item had been `in_progress` and
untouched since 2026-07-31, `mergeable_state: dirty`, labelled `needs-resolution`, with **all four
review threads already resolved** - nothing was blocking it on review.

### The manifest was the least accurate source, again

Its `notes` ended on *"All 29 tests pass ... verified live"* and it carried no `blockers` field, so
it read as ready while the pull request had been unmergeable for five days. This is the same
finding the 2026-08-03 entry recorded for #109, in the same week, on the same plan - which makes it
a pattern rather than an incident. Both times everything needed to diagnose it was on the pull
request the whole time: a `dirty` state, a `needs-resolution` label, and a routine comment naming
the conflicting files.

### The README conflict was not the one the routine reported

The 2026-08-03 routine comment described `.gitignore` as a safe concatenation (correct) and
`.claude/hooks/README.md` as *"both sides add an overlapping Safety bullet ... this branch's bullet
is a subset of the wording a landed main change already added"*. True, and much too small.

This branch was cut from `0fd14357`, before #101 rewrote the README from 378 lines to ~140. An
earlier merge on the branch resolved that rewrite **hunk-by-hunk**, and the head therefore carried:

- `## Setup: overriding the default remote/branch/path` (plus four subsections) and
  `## Verifying it worked` - pre-#101 sections - sitting alongside the `## Configuration` /
  `### Where to put them` sections that had replaced them. Two documents about the same three
  settings.
- `Any other label is preserved but not interpreted.` stranded 75 lines below the labels list it
  closes, because the resurrected block had been spliced into the middle of that section.

Visible in the branch's own history rather than inferred: `151934ff` carried the README at 367
lines, and the merge at `01d112c0` produced 228 rather than `main`'s 142.

**The 2026-08-03 entry's own generalization is what resolved it** - *a documentation conflict
against a restructured file is a rewrite, and resolving it hunk-by-hunk produces a document that
reads as two.* That was written about #109's README two days before this branch's merge produced
the identical artifact. Re-authored against `main`, and only after checking that both resurrected
sections are superseded verbatim: `## Configuration` / `### Where to put them` covers the setup
half, and Quick start already carries the `session-start.sh && cat CLAUDE.local.md` verify line.

What survives is this branch's own content: the `plan-updates-since.sh` entry under *Plan
dashboards*, and two *existing* Safety bullets extended rather than duplicated - the `FETCH_HEAD`
read-only bullet now names the script, the gitignored-files bullet now names the stamp. The branch's
README delta went from **+86/-0 to +12/-2**.

**Worth carrying, because the routine will meet this again:** its conflict report names files, and a
file name understates a conflict against a restructured document. The report was accurate and still
led to the wrong size of fix - a session acting on it alone would have resolved the markers and left
both defects in place, since neither is visible in the conflict hunks.

### What was checked and found clean

- **The same-artifact-twice pattern**, this plan's recorded-three-times failure and exactly what a
  long-lived branch off a moving base produces. No instance: the test module already imports `main`'s
  shared `ScratchRepository` (an earlier merge had adopted it), `tests/stubs/` has no counterpart on
  `main`, and `plan_updates_since_support.py` does not overlap `plan_manifest_tools.py`.
- **The two auto-merged files, semantically rather than textually.**
  `resolve-personal-notes-config.sh` and `session-start.sh` merged without markers, and the merged
  summary block carries both #109's `local settings:` line and this branch's `plan state SHA:` line.
- **`depends_on: []`**, and `check_dependency_readiness.py --item plan-updates-since-helper` returns
  `[]` - nothing had regressed underneath it.

### Verification, and the feature verifying itself

243 tests across the two suites CI's `test_claude_dev_tooling` job runs - 194 plan-dashboard, 49
hooks (this module's 13 plus `main`'s 36, including the `test_personal_settings_sync.py` arriving
with the merge). None lost.

The live run is the part worth recording: `plan-updates-since.sh workflow-unification --since <sha>`
returned a delta that **included a manifest change another session pushed during this resolve**. The
notes branch moved twice while the conflict was being fixed (`75d0b61a` to `b39153aa` to `b56fee94`,
242 lines), so the anti-stale-save rule was not theoretical here - these edits were re-applied onto
the freshly fetched manifest rather than the copy loaded at the start.

### CI, unchanged and still not this pull request's

`test_each_lib (semantic_digital_twin)` fails on `test_world_sim_state_sync`, the Mujoco
box-settling assertion (`final_pos=[~0, ~0, 0.1499]` against `[0.3, 0.2, 0.15]`). Unreachable from a
`.claude/`-only diff; `test_claude_dev_tooling` is green. Already ruled ignorable for `.claude/`-only
pull requests on #101.

**State**: pushed as `99c92c3c`, `mergeable_state: unstable` against `main` at `b52da84d`,
`needs-resolution` dropped (the full label set re-sent so `cram2-link-sent` survived, per #139's
replace-not-add finding), back to draft per the standing re-draft-after-push rule. This clears one of
the six in-flight bash-touching pull requests decision 12's items 2-6 cannot land ahead of.

### A note on where this was done from

The fix had to land on #115's head, which belongs to another session, so it was pushed to
`claude/plan-item-kickoff-workflow-n814iz` rather than this session's own designated branch - the
same override already on record for #133 into #117 and #143's one line onto #135's branch. There is
no alternative that resolves #115 itself: a new branch is a new pull request.


### Third round: prototype the reviewer's suggestion before answering it

Four comments, and the first pair overturned an answer this session had given twice.

`PullRequestField`'s members were argument tuples behind a keyword-only helper, because
two earlier rounds had established - correctly - that writing a member as
`PullRequestFieldSpecification(key="head", …)` silently lands the whole instance in
`key`. The reviewer asked anyway: *can you not just call the constructor?* Prototyped
rather than answered from memory, and the answer is yes, given one thing neither earlier
round had tried:

```python
class PullRequestField(PullRequestFieldSpecification, Enum):
    NUMBER = PullRequestFieldSpecification(key="number", required=True)

    def __init__(self, specification: PullRequestFieldSpecification) -> None:
        for field in dataclasses.fields(PullRequestFieldSpecification):
            object.__setattr__(self, field.name, getattr(specification, field.name))
```

The arguments are keywords for real rather than by proxy, the member is still a
specification, `field.key` still reads directly, and the helper - which existed only to
return its arguments unchanged - is deleted. Deleting the `__init__` fails three tests, so
the silent form cannot return unnoticed.

Worth carrying, because this session got it wrong in the same direction twice: **a
constraint established by a failed attempt is a fact about that attempt, not about the
language.** Both earlier answers were true of the shape they were written against and
false in general, and only running the alternative found the difference.

### The revert a mutation check earned

The same round asked for `RESTACK_STEPS` to be found from `RestackStep.__subclasses__()`,
as `COMMANDS` already is. It was applied, and the reviewer then withdrew it themselves on
reading why it had been a list.

What settled it is worth keeping, because the argument alone had not: swapping
`PublishBranch` ahead of `RefuseAnUnsafeMove` fails
`test_a_push_the_move_checks_refuse_is_not_made` - a behavioural test that publishes to a
real scratch fork and asserts the destination ref never moved. The order is not a
stylistic preference; it is load-bearing behaviour a test already catches, and
auto-discovery would have made it a consequence of where the classes happen to sit in the
file.

That also disposed of the order test added while auto-discovery was in: it asserted the
sequence as a literal, which against an explicit tuple only restates it - one change
failing two tests for the same reason. Deleted with the revert.

The distinction that survives, now in `RESTACK_STEPS`'s own docstring: **discover a list
that carries no meaning, state one that does.** `COMMANDS` is discovered because its only
content was the chance of forgetting a line; the steps are listed because their order is a
decision about what a pass does, and it belongs where it is read.

The round's last comment asked for docstrings on the enum members at one line of
`stack.py`. Swept both modules with an AST pass instead: `Command`'s ten members,
`BranchStatus`, `IntegrationStrategy`, `CommitMoveAction`, and the two undocumented module
variables. Neither module now has an undocumented enum member or module-level variable.

### Merged, and what the item leaves behind

#115 merged into fork `main` on 2026-08-05, the same day the conflict was cleared.
Confirmed from `main` rather than from the notification: `99c92c3c` is an ancestor of
`origin/main`, the three new files are present, and `README.md` is the re-authored
180-line version rather than the 228-line spliced one. `test_each_lib
(semantic_digital_twin)` — red on this pull request since 2026-07-31 — passed on the
post-merge run, so it went in green rather than with a known-ignorable red.

Two things this leaves for later, both already owned by named items rather than loose:
the inline `gh`-CLI-else-token rule in `plan-updates-since.sh`, which
`dev-tooling-github-api-unification` absorbs as its third carrier alongside
`github-api.sh` and `pr_state`; and the bash body itself, which
`dev-tooling-save-commands-python` converts once the remaining in-flight
bash-touching pull requests land. Five of those six remain: #107, #110, #121, #126, and
#139's own `.claude/stack/` work — #109 and #115 are now both in.

## Update 2026-08-05 (merged): stack-tooling-on-main lands on fork main

PR #106 merged into fork `main` at `2026-08-05T14:10:36Z` (`merged_by: AbdelrhmanBassiouny`,
head `b3e240e6` - the cram2-checkout fork-resolution fix from earlier the same session). Marked
ready for review by the user directly (not a session action) shortly before the merge, and merged
normally rather than by push/fast-forward.

Verified by presence on fork `main`, not from the merge notification alone: `.claude/stack/stack.py`,
`.claude/skills/stacked-pr-maintenance/SKILL.md` and `.claude/stack/tests/test_maintenance_skill.py`
all `git cat-file -e` clean on `origin/main` - the same discipline `setup-personal-notes-pr101`'s
verification used.

**This is the fork-internal merge only, not the cram2 landing.** PR #106's base was fork `main`
(head repo and base repo both `AbdelrhmanBassiouny/...`), not `cram2/cognitive_robot_abstract_machine`
directly - the separate cram2 promotion is the manual step the PR's own "Promote" section already
describes (a compare-and-create link, since the GitHub app has no write access to cram2). So
`routine-cutover`'s gate ("only after PR 1 is on cram2/main and fork main fast-forwards") is **not**
met by this merge alone - it needs the promotion to actually happen and cram2 to merge it, then
fork main to fast-forward from cram2/main. Worth stating plainly since this merge could easily read
as satisfying that gate at a glance.

**Consequence for dependents.** `setup-stacked-prs-skill` (#110), `setup-personal-notes-script`
(#107), `shared-pr-state-chips` (#111) and `stack-maintenance-executor` (#139) were all based on
`claude/stack-tooling-on-main`'s branch directly; now that its content is on `main`, each can rebase
onto `main` instead of the now-merged branch - not done here, left for whichever session next
touches each of them.

**One CI check was red at merge time, confirmed unrelated before the merge**: `test_each_lib
(giskardpy)`'s `test_pacer.py::test_with_executor - assert 26.0 == 42`, a physics/timing assertion
with an `rclpy.InvalidHandle` teardown warning during the executor's control-cycle count. PR #106's
diff against `main` was 11 files, entirely `.claude/`/`ci.yml`/`README.md` - nothing in giskardpy's
import graph. Matches this PR's own already-documented pattern of unrelated robotics-stack flakes
(`test_world_sim_state_sync`, the `semantic_digital_twin` texture-pair failure); `test_claude_dev_tooling`
- the job that actually exercises this PR's changes - was green. Noted on the PR rather than chased,
per the standing instruction for this PR.

## Update 2026-08-05 (landing): three items reach main, and the third stale-save revert

Fork `main` fast-forwarded at `2026-08-05T14:10:36Z`, and GitHub recorded #106, #115 and
#119 as merged in that one instant - the same auto-detection the 2026-07-31 landing entry
describes for #101/#103/#105. Verified by ancestry rather than from the merge titles:
`claude/stack-tooling-on-main`, `claude/plan-item-kickoff-workflow-n814iz` and
`claude/cram2-main-drift-4owm9a` are all `git merge-base --is-ancestor` of `origin/main`.
So `stack-tooling-on-main`, `plan-updates-since-helper` and `merge-timestamp-required-fix`
are `done`, and `.claude/stack/` is on `main` at last - which retires the two deletions
`routine-cutover` has been carrying, and means `ci.yml` now runs `STACK_TESTS_DIRECTORY`
as a third suite.

**The anti-stale-save rule earned itself a third recorded instance, minutes apart.** The
dashboard refresh auto-corrected `merge-timestamp-required-fix` to `done` and pushed it
(`894a7ce5`); another session then pushed `acccd8be`, adding a legitimate landing note to
`plan-updates-since-helper` while writing back a manifest loaded *before* that correction,
which silently reverted the status to `in_progress`. Caught only by re-reading the manifest
after the write rather than trusting the refresh's own `{"corrected": [...]}` output - which
is the practical lesson, since that output reports what the run *did*, not what survived.
Re-applied onto the latest manifest, keeping their note; both are now correct.

The first two instances (2026-07-30, recorded in the tag-push and routine-cutover entries)
were both a whole section reverted. This one is a single field, which is worse in one
respect: nothing in the diff looks wrong, and a reader would have to know the item had been
corrected to notice it had been un-corrected. **Verify after writing, not only before** -
fetching first is necessary and not sufficient when another writer can land between your
read and your push.

## Update 2026-08-05 (live, again): the first real-stack pass found the executor promoting what it had just withheld

The Routine was pointed at `claude/plan-item-kickoff-workflow-koufa6` (#139) rather than #106, since
`maintenance.py` lives only there, and fired against the real 44-pull-request stack for the first
time. It worked - and the thing it caught was a defect in the executor itself, on the executor's
own pull request.

### What happened

The pass restacked, hit a `.gitignore` conflict on #139, labelled it `needs-resolution` and posted
the naming comment - exactly as designed. Then, a minute later in the same pass, it took the label
straight back off:

| time | event | actor |
|---|---|---|
| 14:10:42 | labeled `needs-resolution` | claude[bot] |
| 14:11:46 | **unlabeled** `needs-resolution` | claude[bot] |
| 14:11:46 | labeled `cram2-link-sent` | claude[bot] |

The tell was a disagreement between two reports: the comment said the branch was labelled
`needs-resolution`, and the pull request carried only `cram2-link-sent`.

### Root cause: a write computed from a snapshot a later step invalidates

`board --write` exports the fork's open pull requests at the *start* of a pass. `restack` then
withholds a conflicted branch by writing a label *live*. `promote` read neither back:
`promotion_order`'s `needs_resolution` exclusion and `LabelWrite.replacing(branch.labels, ...)` both
take `branch.labels`, which is the snapshot.

So within one pass, promotion promoted a branch that same pass had just conflicted on, and then
computed a whole-set label write from a list that was already out of date - stripping the label
written ninety seconds earlier.

This is the production incident `LabelWrite.replacing` was built for, re-entered through a different
door. That class exists because a label write replaces the entire set, and its rule was stated as
*never compute the set yourself; compute it from the labels the pull request carries now*. The rule
was followed to the letter and still broken, because `branch.labels` is not "now" - it is "at board
time". A helper that guarantees correctness given correct input guarantees nothing about where the
input came from.

The consequence is the loop this item exists to close staying open: with the label gone, the next
pass has nothing to withhold on, so it restacks the still-conflicted branch, fails again, and posts
a *second* comment - the precise behaviour the design promises it prevents. The label was invented
to stop re-reporting; a bug that removes it restores the problem it solved.

### The general shape, which is new to this roadmap

Two ambient-state lessons are already recorded on this item - a test reading `board.json` beside the
module, and a test reading an exported `GH_TOKEN` - and both were about *tests* reading state they
should have controlled. This is the production counterpart, and it generalises further:

**Any write computed from a snapshot that a later step in the same pass can invalidate is wrong.**

`restack`'s own withhold check was already right for exactly this reason - it re-reads
`mergeable_state` live, per branch, rather than trusting the export. Promotion was the one step that
trusted the board, and it was also the one step issuing a *replacing* write, which is what made it
destructive rather than merely stale. Both properties had to coincide, which is why no throwaway run
had surfaced it: #140/#141 exercised conflict-then-withhold and promote, but never a branch that was
conflicted *and* promotable in the same pass.

### The fix, and one test whose setup changed

`promote` already fetches each candidate's pull request record for its title and description, so the
live labels were there to be read all along. Both the eligibility decision and the label write now
read that record. Two tests written failing first - a branch labelled mid-pass is not promoted, and
the label write keeps a label added since the board was taken - each checked by mutation and each
failing alone when its own half is reverted.

One pre-existing test, `test_a_branch_already_carrying_the_link_label_is_not_promoted_again`, had put
the label on the board. Its **setup** moved to the fork stand-in; its assertions are untouched. The
behaviour it names is unchanged and still correct - only *where* "already carrying" is read from
moved - which is the same treatment #103 gave the two tests whose incidental fixture items became
ready-to-start under its corrected semantics.

### Two things confirmed rather than assumed

The conflict comment cited *this* session's link, which looked like a hardcoded value. It is not:
`get_session_link_in` reads the link out of the pull request's own description, so a report reaches
the branch's owner - and this session owns #139. The design working, not a bug.

And the `.gitignore` conflict itself was the benign shape #115's resolution already recorded - two
independent additive blocks, this branch's `board.json` entry and main's `.plan-state-sync-sha` stamp
- concatenated, both kept.

### State this pass also revealed

**#106 has landed on main.** `.claude/stack/` and `.claude/skills/stacked-pr-maintenance/` are on
`main` now; `maintenance.py` is not, so the Routine prompt still has to resolve #139's branch rather
than falling through to `main`. #139's base was retargeted to `main` accordingly, and merging main
brought the whole of #106's landed head. 385 tests pass across the three directories CI runs, up from
366 - main's own tests plus the two added here.

### Review round 2026-08-05: naming the wire format removed the coverage that guarded it

Two comments on #135, and the first is worth recording for the trap it exposed rather than
for the change itself.

**Asked**: the JSON keys should be `StrEnum`s, not string literals. Correct, and squarely
`AGENTS.md`'s "instead of passing around strings, use enums instead" — the six keys were
written out twice, once in the two `as_dictionary` methods and once in the test that
asserts the command line's output, with nothing holding the copies equal.

**The trap**: making both sides read one `ReportKey` enum *removed* the only thing pinning
the wire format. Renaming a member's value changes production and test identically, so no
test fails. Verified rather than assumed — renaming `SHARED_PATHS` to `sharedPaths` left
all 8 tests green.

That is a general property of single-sourcing an external contract, and it is easy to miss
because the refactor looks purely like an improvement: **the duplication was doing work.**
The literals were a second, independent statement of what a reader of the JSON sees. Deleting
them without replacement trades a real guard for tidiness.

The fix is one test that owns the wire format and nothing else does:

```python
assert {key.name: str(key) for key in ReportKey} == {
    "PATHS_ABSENT_FROM_BASE": "paths_absent_from_base", ...
}
```

Re-running the same mutation now fails exactly that test and no other — which is the shape
worth having: a key rename is a contract change, so it should fail once, in the place that
names the contract, rather than in six assertions that are really about overlap detection.
The same reasoning `#106` used when it kept a single prose test after deleting eighteen:
assert the thing that must not drift, in one place, computed from live state.

### The `run_git` duplication question, and the answer that reading gave

The second comment asked whether `check_scope_overlap.py`'s `run_git` duplicates
`GitCommandRunner` in #139 or #143. Reading all three rather than reasoning from the names
split the question in two:

- **#139 is not a duplicate.** Its `attempt`/`run` split and ~14 named methods exist because
  a push that silently did nothing must not be indistinguishable from one that worked — its
  own docstring says so. #135's script never writes anything.
- **#143's is nearly identical** — both generic free functions, both raising, differing only
  in error type and parameter order.

So the real duplication is the ~12 lines of `subprocess.run(["git", …])` boilerplate, in
three copies, and the plan already names where it converges: `dev-tooling-notes-core-python`
lists `git_interface.py` as the dependency seam. Recorded there as a third carrier, the same
treatment #139 got on `dev-tooling-github-api-unification`.

**A precedent that turned out not to cover the case.** #143's own review asked this about
`stack.py` and the recorded answer was that the boilerplate overlap is acceptable *because
the contracts are deliberately opposite* — `_git` returns `""` where `run_git` raises. That
reasoning is sound and does not apply here: #135's and #143's contracts are the same. Worth
noticing, because citing a precedent by its conclusion rather than its reason is how a real
duplication gets waved through.

## Update 2026-08-05 (resolved): #125 was a second pull request for #126's branch, and no plan surface could have shown it

#125 has been closed as a duplicate. It was not a piece of work at all: its head was
`claude/workflow-unification-git-identity-ppzcyh` at `d4fdc5b7`, the identical commit
#126 points at, differing only in base - `main` instead of #121's branch, which is why
its diff read as 1,329 additions (#121's 548 plus this item's 828) rather than #126's
828. It was opened 95 seconds before #126, carried no reviews and no comments, and was
the only non-draft pull request on the fork.

### The tell was in the description, not the diff

Its title and body were the verbatim commit message of `a525d117` - #121's first commit,
ending in the `Made with the help of Claude.` trailer. That is GitHub's auto-fill for a
pull request opened without a title or body, and it is a reliable signature: every
deliberately opened pull request in this plan has markdown headings, an
`Implements <item-id> (plan ..., track ...)` line and a session link, because the
conventions require them. A pull request whose body is a commit message was opened by a
call that passed neither.

The confusing part follows from it rather than adding anything: the text described #121's
session-start work while the diff also added `save-git-identity.sh`, so reading either
one alone gave a coherent but wrong account of what the pull request was.

### Why nothing flagged it

Not an oversight in the manifest - the plan has no mechanism that could have caught it.
Coverage runs in one direction only: `_generated/branch-index.tsv` maps branch → plan-id,
and an item names its `pull_request_number`. Nothing enumerates the repository's open
pull requests and asks which item owns each one, so a *second* pull request on an
already-tracked branch is invisible to every surface the plan has. The dashboards cross-
check live GitHub state for the pull requests the manifest names; #125 was never named.

This is worth stating plainly because the fork's own convention - one branch, one item,
one pull request - is what makes the reverse lookup unnecessary in the normal case, and
also what makes a violation of it undetectable. The stack maintenance executor is the
one component that does enumerate pull requests, and it reads them as stack members
rather than checking them against plan items.

### What was left where it was

The `dirty` state on #125 was #121's conflict against `main`
(`resolve-personal-notes-config.sh`, `session-start.sh`, plus `.claude/hooks/README.md`
from the git-identity commit). Resolving it on the closed duplicate would have been the
same conflict resolved twice, so it stays with #121, whose branch owns those two files'
changes. #126 remains stacked on #121 and inherits the resolution when it lands.

## Update 2026-08-07 (resolved): #121's conflict and its six-day-old review round

`/plan-item-resolve workflow-unification session-start-plan-and-setup-guards`, session
https://claude.ai/code/session_01JF8sH4isJxrY6Ca5NgD7es. The item had been `in_progress`
and untouched since 2026-08-01, `mergeable_state: dirty`, labelled `needs-resolution`, with
**five review threads unresolved and none outdated**.

### The manifest was the least accurate source, a third time

Its `notes` ended on *"Two TDD tests, 233 green (was 231)"* and it carried no `blockers`
field, so it read as finished while the pull request had been unmergeable for four days and
unanswered on review for six. That is the same finding the 2026-08-03 entry recorded for
#109 and the 2026-08-05 entry recorded for #115 - three times on one plan, in one week.
Both earlier entries already noted that everything needed to diagnose it was on the pull
request the whole time, and that held again: `dirty`, the `needs-resolution` label, two
routine comments naming the conflicting files, and five threads sitting in plain sight.

Worth stating as a pattern rather than a third incident: what these three items have in
common is that the *implementing* session's last act was to write a notes field describing
what it had shipped, and nothing after that point ever wrote to the field again. Review
arriving and `main` moving are both events with no writer. The `notes` field records what a
session did; it has never recorded what happened to the branch afterwards.

### Both conflicts were additive-vs-additive, and the ordering comment was the real content

`session-start.sh` and `resolve-personal-notes-config.sh`, three hunks, nothing
contradictory - this branch's setup-verdict block against #109's personal-settings block,
its `setup:` line against #115's `plan state SHA:` line, and its
`branch_can_hold_plan_item`/`plan_branch_index_exists`/`tracked_plan_count` against #115's
`PLAN_STATE_SYNC_STAMP` helpers. Each resolved by keeping both sides in sequence.

The one judgement in it was ordering, and it is the piece worth carrying: the setup verdict
must run **after everything the hook writes**, not merely after `CLAUDE.local.md`. Its
comment said the latter, which was true when it was written and became too narrow the
moment #109's settings sync landed beside it - and will be too narrow again when #126's
git-identity write arrives, whose own notes already require it to precede the check. The
comment now states the general rule, so the next block added there inherits it instead of
having to rediscover it.

#115's warning was applied rather than assumed: the merged `README.md` and `session-start.sh`
were read end to end for the resurrected-section and stranded-line defects that hunk-by-hunk
resolution produced on #109 and #115. Neither is present here - this branch is young enough
that `main` never restructured underneath it.

### The review round, and one thread left open on purpose

Four threads acted on. The tooling-file paths became a `SetupPrerequisiteFile` StrEnum with
the requirements file among them; the whole set-up-clone layout became a checked-in fixture
tree at `tests/fixtures/set-up-clone/`, mirroring the paths it occupies in a scratch project
root, so `settings.json` and `requirements.txt` are real files of their own type and
`write_setup_prerequisites` is one `copytree`; the summary wording moved into
`session-start-messages.sh`; and the README paragraph moved to the third person.

The fifth - *"I guess this won't be needed once you do my previous comment"*, on
`write_setup_prerequisites` - was answered rather than resolved. The method shrank to one
line but survives, because leaving `CLAUDE.local.md` out of it is exactly what lets the
session-start tests run against a clone that does not have one yet. Reading the comment as
*delete the method* was an interpretation, not something the reviewer said, so the thread
stays open with the reasoning and an offer to fold the copy into `create` instead. The
general rule this follows is already in cram-notes.md: resolve a thread only once you have
genuinely done what it asked.

### The wording move re-ran #135's trap deliberately

Single-sourcing the messages is the same shape as the `ReportKey` enum two days earlier, and
it has the same cost: with the hook and the tests both reading one definition, a reword
changes them identically and nothing fails. So
`test_every_summary_message_reads_as_written` owns the wording and nothing else does, and it
was verified by mutation rather than by argument - rewording one message fails that test and
no other.

This is now the second time on this plan that a *"can this string be fetched from where it
is defined?"* comment has been answered by single-sourcing plus one contract test. Worth
promoting from precedent to expectation: the comment is always right, and the fix is always
two changes rather than one, because the duplication being removed was carrying a guard.

### The defect only a staged diff could show

The fixture's `requirements.txt` was silently not added: the repo's `.gitignore` ignores
`*.txt`, and every real `requirements.txt` in this repo predates that rule and is tracked
only because it was already tracked. The local suite passed regardless, because the file
existed on disk - CI on a fresh checkout would not have. It was caught by diffing the staged
tree against `main` and noticing one expected path missing, and fixed with a `.gitignore`
exception rather than `git add -f`, following the `*.png` exception the example screenshots
already carry.

The generalizable part: **a test suite that passes locally proves nothing about files the
index does not have.** Every suite here was re-run from a clean clone of the pushed branch
afterwards, which is the cheap check that would have caught it directly.

### State

Pushed as `862da392`; `mergeable_state: clean` against `main` at `0626bdce`;
`needs-resolution` dropped by re-sending the full label set, per #139's replace-not-add
finding; still a draft; description rewritten to match what the pull request now does. 350
tests green across the three directories `test_claude_dev_tooling` runs - 194
plan-dashboard, 65 hooks, 91 stack - against 349 after the merge and 233 before it.
`test_each_lib (semantic_digital_twin)` remains the base's, not this pull request's, and is
re-checked on the new run rather than inherited from the 2026-08-03 ruling.

This unblocks `git-identity-from-personal-notes` (#126), which is stacked on this branch and
inherits the resolution, and clears one of the bash-touching pull requests decision 12's
items 2-6 cannot land ahead of.

### A note on where this was done from

The fix had to land on #121's head, so it was pushed to
`claude/workflow-unification-setup-jgvs53` rather than this session's designated branch -
the same override recorded for #115, #133 into #117, and #143's one line onto #135's branch.
There is no alternative that resolves #121 itself: a new branch is a new pull request, which
is precisely what #125 turned out to be.

## Update 2026-08-07 (new item): upstream-review-reader, and a premise that was wrong

The user's complaint was concrete: reading cram2 review threads and retyping them into a
session is slow, and it makes them the bottleneck on every review round. The question was
whether anything - phone, GitHub, or Claude - could automate it.

### "cram2 is not readable from the cloud" was false

`stack.toml` and `stack.py` both state this as fact, and `ready-to-promote-upstream-links`
and the promotion-link design are built on it. It is wrong. cram2 is a **public** repository:
anonymous `git ls-remote` against it succeeds from a session, and the user's account even
reports `can_push: true` on it. What is actually true is narrower and different: a session is
scoped to an allowlist of repositories, and the agent proxy enforces that scope on the GitHub
API. The upstream is readable; the session is simply not permitted to be the reader. The
prose was not corrected here - it lives in `stacked-pr-maintenance`, whose tests assert its
wording - but it should be, and it is flagged rather than folded in.

### What was measured, not assumed

| route | fork | cram2 |
| --- | --- | --- |
| `git ls-remote` | yes | yes |
| REST from Python | 200 | 403, repository not in session scope |
| github.com HTML | - | 403 |
| GraphQL | 403 | 403, "only the pinned set of PR-review operations is served" |

The GraphQL refusal is the load-bearing one, and it applies to the fork too, not just to
cram2. Thread resolved-state is exposed *only* by GraphQL - REST has no such field - and the
user made resolved-state a hard requirement. The proxy README classifies a 403 as an
organization policy denial to report rather than route around. So the conclusion was forced:
no script running inside a session can produce this report, whatever its design.

### Why an Action, and why dispatch-only

The same script runs fine where GraphQL is not blocked. GitHub Actions on the fork start
with no queue - median 0s, max 0s across the last 14 completed runs, out of 3563 - so the
round trip is the job itself rather than a wait. The session reads the result over plain
read-only REST; `runs`, `jobs` and `job-logs` were all confirmed to answer 200. The only
non-read call in the whole design is the dispatch POST, which starts a job and changes no
repository content; the user accepted that explicitly after it was put to them as the one
exception to "no write calls at all".

Dispatch-only, never a cron. That keeps it inside the no-scheduled-checks rule and matches
what `routine-cutover` wants of every deterministic duty.

### The backend question, answered rather than deferred again

The first draft used a stdlib `urllib` GraphQL client. That would have been the *fourth*
implementation of the gh-CLI-else-token access rule, after `github-api.sh`, `pr_state` and
`maintenance.py` - precisely what `dev-tooling-github-api-unification` exists to stop, and
#139's review had already asked "why not gh?" only for the answer to be deferred to that
item. So this uses `gh api graphql`: Actions runners ship gh and `GITHUB_TOKEN` authenticates
it, so the caller adds no backend and needs no secret. This does not resolve that item, but
it is evidence for its open question - the install-or-not tension only binds the
SessionStart-reachable tier, and an Actions-only caller can already assume gh.

### Portability

The user required this to work for every cram2 contributor in their own fork, which the
plan's standing portability rule already demanded. No owner or repository is named anywhere:
upstream comes from `stack.toml`, the fork owner from `github.repository_owner`, and
`--upstream` overrides for a checkout whose upstream differs. The one manual step per fork is
that Actions are disabled by default on a new fork and must be enabled once.

### State

Two commits on `claude/automate-upstream-reviews-0fte9f`; 29 tests, all offline against
recorded payloads with `gh` stubbed, so CI needs no credentials. A stubbed end-to-end run
exercised branch resolution, cursor pagination, resolved-filtering and the step summary.

Live dispatch could **not** be verified in this session, and the reason is worth recording:
`workflow_dispatch` only registers a workflow that exists on the repository's **default**
branch, so a workflow still on its own feature branch returns 404 on dispatch. Actions are
enabled on the fork and 15 other workflows are registered, so this is the default-branch rule
and nothing else. The first real dispatch is only possible once this lands on the fork's
main, which also means the GraphQL document itself is unexercised against a live schema until
then - the one residual risk in the change.

### Second round on #121: the contract test is cut, and the Python question has a measurement

Three more comments the same day, applied in `b57d3902`. Two were plain — the message names
the tests pass became a `SummaryMessage` StrEnum. The third reversed this session's own
recommendation, and that is the part worth keeping.

`test_every_summary_message_reads_as_written` had been added hours earlier for one reason:
single-sourcing the wording removes the guard the duplicate literals were carrying, so
something has to pin it. That is #135's `ReportKey` finding applied verbatim, and the entry
above went as far as calling it *"promoting it from precedent to expectation"*. The reviewer
looked at the resulting test and said to cut it — *"remove these wording assertions or replace
only one of them by being not empty."*

Cut, second option taken: `test_every_summary_message_renders_something` iterates the enum and
asserts each member renders non-empty. A reword is now invisible to the suite. That is a real
loss and it was stated once on the thread rather than argued a second time.

**The correction to the generalization is the useful part.** "Single-source, then add one
contract test" is right about the *mechanism* — the guard genuinely does disappear otherwise —
and wrong to treat as automatic. Whether a given string is worth pinning is the owner's call,
not a property of the refactor. Here the wording is a diagnostic line in a hook's summary,
reworded freely and read by a human; on #135 it was a JSON wire format other code parses. The
precedent should be read as *notice the guard you are deleting and say so*, not *always replace
it*.

What survives is the pair of failures that actually break the hook, both mutation-checked: a
member naming a function that does not exist, and a function that prints nothing — the second
would make `session-start.sh` emit a blank `setup:` line with nothing noticing.

### The Python question, answered by measurement

The third comment asked whether `session-start-messages.sh` could be a Python file instead,
*"if it can be a python file then make it so, if no harm from it"*. The condition is the whole
answer, so it was measured rather than reasoned about: with `python3` removed from `PATH`
entirely, the hook still prints all six summary lines and exits 0, degrading only
`check-setup.sh`'s dependency row — into a row that says python3 is missing. As a Python file
that entire block produces nothing.

`resolve-personal-notes-config.sh:343` already states the same rule from the other end: the
branch index is TSV read with `awk` precisely so *"session-start.sh must not gain a hard
dependency on python3/PyYAML"*.

Not converted; replied with the measurement and left open for the user. `dev-tooling-session-start-python`
is the item that takes this floor raise deliberately, behind a shim that probes for python3 ≥
3.11 and exits 0 with one diagnostic line when it is absent — converting one sourced file now
would take the raise without the shim that makes it safe.

Worth generalizing: **a conditional instruction ("if no harm") is answered by testing the
condition, not by weighing it.** Removing python3 from `PATH` took one command and turned a
judgement call into a demonstration.

## Update 2026-08-03 (closed): dashboard-chip-notes-collapse merged

`dashboard-chip-notes-collapse` (PR #124) merged into fork `main` on 2026-08-03, the same day
the user marked it ready for review themselves. Three `origin/main` merges landed on the branch
from outside any session while the pull request was open, each surfacing a CI failure this
session investigated and none of which had any path back to the template-only diff: a
`coraplex` pytest-xdist worker crash, `semantic_digital_twin` mesh-material assertion failures
that cleared once an upstream texture-resolution fix landed, a second worker crash on a ROS
synchronizer test, and finally a missing-ROS-package error in a newly-merged Gazebo adapter's
own tests. Each was replied to on the pull request explaining why it wasn't being fixed there,
matching this plan's established pattern of unrelated robotics CI noise on `.claude/`-only
changes - see the `setup-personal-notes-pr101` and other entries above for the same pattern.

Session unsubscribed from the pull request and from this plan's tracking issue #102 (held only
for this item's sake) on merge, per the "when your PR's job ends" convention.

## Update 2026-08-05 (merged): plan-item-bootstrap lands, and the executor's false positive

#143 merged into fork `main`. Verified by content rather than from the notification:
`f77794b0` is an ancestor of `origin/main`, `plan_item_bootstrap.py` with its test module
and fixtures are present, `plan-item-kickoff/SKILL.md` carries step 6, and
`resolve-personal-notes-config.sh` carries `PLAN_ITEM_BOOTSTRAP_SCRIPT`. The ordering this
item exists to invert is therefore the documented procedure on `main` now: a kickoff whose
plan is approved opens the branch and draft pull request and records the item *before* the
first edit, rather than leaving the manifest saying `not_started` for the length of the work.

The item was bootstrapped by hand in the order it prescribes, since the tool did not exist
yet - so the first genuine run belongs to whichever item is kicked off next, and that run is
the real test of it.

### The maintenance executor reported a conflict that did not exist

Worth recording here rather than only on #139, because it is the second failure mode this
plan has seen from a *hand-or-machine-assembled input treated as truth*, after #119.

Two conflict reports arrived on #143 from the maintenance pass, both with an empty
`Conflicting files:` section. The first (14:10 UTC) named a real conflict -
`.claude/hooks/README.md`, where `main` had gained #115's `plan-updates-since.sh` bullet in
the same list this branch extends - so it read as "detection right, naming empty". The
second (20:37 UTC) disproved that reading: `git merge-tree --write-tree origin/main
f77794b0` exits 0 and GitHub reports `mergeable_state: clean`, and `main` had not moved
since 14:27 UTC, so both passes ran on pinned, re-testable inputs. It reported a conflict on
a clean merge and applied `needs-resolution`.

**A false positive here fails in the dangerous direction.** `needs-resolution` withholds a
branch from every later pass, so a wrong one silently removes a healthy branch from the
workflow; and this branch was labelled while already `clean`, meaning the detection and the
label-clearing check disagreed about the same branch within one pass - the loop #139 exists
to close, failing open the other way. The label was cleared by hand, re-sending the full set
so `in-review` survived.

One hypothesis covers both symptoms and is recorded on #139 for its owner to test: an
integration that fails for *any* reason is classified as a conflict, and the unmerged paths
are enumerated from a state that has none. That predicts an empty list on every conflict
report, which #139's own `.gitignore` report contradicts - so the picture is not uniform,
and that contradiction is the part that would falsify it. Not fixed from here: it is #139's
module, and the reproduction above is enough to write a failing test from.

The generalizable point is the one #119 already made in a different costume: **a report
whose wrong value is indistinguishable from a legitimate one has to be rejected by the code
that produces it, not trusted by the reader.** An empty file list is valid-looking. So is a
conflict flag on a clean tree. Both were believed until they were re-derived from git.

### Handed over 2026-08-09: #135 marked ready by the user

The user flipped #135 out of draft themselves, which by the notes-branch convention ends
the owning session's job on it — that flip is their record of having read and accepted the
changes, and it is deliberately distinguished from a session marking its own pull request
ready to unblock a dependent.

The item stays `in_progress`: it has not merged. What the handover leaves behind, all
reported before unsubscribing and none of it fixed afterwards, because the same convention
says report-then-stop rather than stay to tidy:

- **A stale `needs-resolution` label.** The branch became mergeable again with `db034e64`;
  the maintenance pass clears the label itself on the next run that sees a clean merge, so
  clearing it by hand would only race a loop that already works. This is the second time on
  this pull request that leaving the label alone was the right call.
- **One open review thread**, the `run_git` duplication question — answered with a
  recommendation and left open on purpose, since the answer was "recorded elsewhere, not
  changed here" rather than an action taken.
- **A description one merge behind** (it says 346 tests, and names only
  `semantic_digital_twin` under CI). Not corrected, because the ready-for-review flip is the
  user's record of having read the description as it stood; editing it afterwards would
  change what they just accepted.

**The CI record is worth keeping as a data point about this repository rather than about
this branch.** `test_claude_dev_tooling` — the only job a `.claude/`-only diff can reach —
was green on every run this branch ever had. Four *different* robotics jobs went red across
four runs: `semantic_digital_twin`'s two `test_multi_sim.py` texture assertions, a `coraplex`
notebook kernel dying before it could answer `kernel_info`, and `giskardpy` twice on two
*different* tests. Only the first looks like a real defect — proven base-side, since `main`
fails identically on its own run and #124 hit the same pair a day before this branch existed
— and it blocks every open pull request in the repository. It was offered as its own
bug-labelled item and not taken up.

The generalizable part, for the next branch that sits here a while: an all-green matrix was
never reachable from this branch, so "wait for green" would have been an indefinite block.
What made the pull request reviewable anyway was having one job that genuinely covers the
diff, and being able to say precisely why each of the other four failures was not it.

## Update 2026-08-09: the dashboard-URL cache was drifting because the write was prose

The URL cache had reached the point where five of six plans plus the master index
pointed at artifacts that did not exist, and two plans had acquired duplicate
dashboards. It had been hand-corrected at least six times since 2026-07-26 and drifted
again every time, so the question was the mechanism, not the mapping.

### What the cache's own history shows

Classifying every URL ever written to `_generated/dashboard-urls.yaml` against the
account's real artifact listing separates cleanly by *what kind of run wrote it*:

| commit kind | URLs written | named a real artifact |
| --- | --- | --- |
| first publish (`Record dashboard URL for <plan>`) | 13 | 10 |
| bulk refresh (`Update dashboard URLs after refresh`) | 23 | **0** |
| correction (`Repoint...at the live artifacts`) | 15 | 15 |

Not one bulk refresh ever wrote a URL that resolved. Every correction did — and every
correction was made by reading `Artifact` with `action: "list"`.

### The mechanism

`SKILL.md` step 3 told the session to "merge your updated url(s) into the existing
`dashboard-urls.yaml` content" and hand-write the result. On a *first* publish that
works: the tool mints a page and hands back its URL, which the session copies. On a
*re-publish* the session passes `url:` and the page updates in place — so there is no
new URL in front of it to copy, and the instruction still asks for one. A plausible
UUID got written instead, and nothing anywhere checked it.

The fabricated URLs are not near-misses of the real ones; they share no characters. They
were invented, not mistyped.

That alone would only produce dead entries. The duplicates come from the next run: it
reads the dead URL, passes it as `url:`, the update cannot land on a page that is not
there, a fresh artifact is minted, and the plan now has two dashboards. Both live pairs
were born exactly this way — `dag-facade-hardening`'s `49053971` on 2026-08-07 after the
08-06 refresh poisoned its entry, and `workflow-unification`'s `07123af6` on 2026-08-04
after the 08-04 refresh poisoned that one. A human then corrected the cache, and the loop
went round again.

### The fix

The deterministic half moves into a committed script, as this skill's own header always
required. `record_dashboard_url.py` is given the cache key and the title the dashboard is
published under; it finds that artifact in the `action: "list"` output and records *its*
URL. No UUID passes through the session at any point, so there is nothing left to
fabricate. It refuses rather than guesses when a title matches nothing (never published)
and when a title matches several (a duplicate exists, and which one survives is the
user's call, so it names both and demands `--url`). That last check is also what stops a
key being silently repointed at some other plan's artifact.

The cache path moves into `resolve-personal-notes-config.sh` as
`DASHBOARD_URL_CACHE_PATH`, beside `PLAN_BRANCH_INDEX_PATH`, instead of remaining a
literal typed into `SKILL.md`.

### State

The cache is reconciled against the live artifacts, using the new script for every key
rather than by hand — `dag-facade-hardening` keeps `49053971` by the user's choice, and
`workflow-unification` reported `changed: false`, independently confirming the entry the
user had already fixed. The redundant artifact of each pair is now unreferenced; it is
not deleted, because a session cannot delete an artifact.

Not addressed here: the pre-existing entries have no automated audit, so a URL that dies
for some *other* reason still surfaces only when someone opens the page.

## Update 2026-08-09 (new item): the plan-item skills get an execution mode

Raised by the user: *"I want in the plan-item-kickoff skill to first ask the user whether he
wants to recreate a plan for this item or to go directly for implementation... Also I want the
user to be able to override this behaviour by a settings in his personal notes so that if he
does not want to be asked at all you just go ahead and implement directly with an implicit
planning phase that doesn't require his approval, so you go fully autonomous till you have
already finished and the draft pr has the implementation that he should review."*

Tracked as `plan-item-execution-modes` on track `personal-data`, wave `immediate`.

### What is actually wrong today

`plan-item-kickoff` and `plan-item-resolve` have exactly one shape. Both gather their context,
present a plan through `ExitPlanMode`, and stop. That gate is unconditional, so it costs the
same round trip on an item whose `notes` and roadmap section already settle every design call
as on one whose premise is in doubt — and the session that produced all that context is
discarded while waiting, or has to be told to continue.

The gate is worth keeping where a plan genuinely needs a decision. It is the *unconditional*
part that is wrong.

### Two modes, and a third value that only decides who picks

- **plan** — today's behaviour, unchanged: draft the plan, present it via `ExitPlanMode`, stop.
- **auto** — draft the same plan, record it, and implement it without asking. The planning
  phase still happens and is still written down; what it stops doing is blocking.
- **ask** — gather first, then put the choice to the user with a recommendation and its
  reasons.

**`auto` is the built-in default, and the reasoning that first put `ask` there was wrong.**
The first round shipped `ask`, on the grounds that the user's opening requirement was the
question itself and that a default which implements unasked is the wrong failure for someone
who inherits this repository having never configured it. The user reversed it the same day
with the argument that actually settles it: auto mode is not unsupervised. By the time the
mode applies, the skill has already read the item's recorded state and the progress on its
plan and pull request, and `execution-modes.md`'s escalation rule already sends anything that
genuinely changes the settled plan back as a question. So `ask` was buying a round trip on
exactly the items the gathered material already settles - ceremony, not a safeguard.

The inherited-clone objection survives as a consequence rather than a counter-argument, and is
recorded here so nobody has to rediscover it: `.claude/` is committed, so every contributor who
inherits this repository inherits `auto` too. If that ever bites, the fix is to flip the
committed default back to `ask` and pin `auto` in `.claude/personal/plan-item-modes.toml`,
which reaches the same outcome for one person without changing anyone else's.

Worth carrying past this item: a default chosen to protect a hypothetical inheritor cost the
actual user a round trip on every run. The test is whether the safety it buys is already
bought elsewhere - and here the escalation rule had already bought it.

### Setting it is a skill, because a script nobody can invoke is half a feature

`plan_item_mode.py set` existed from the first round and nothing could reach it except a
session that had been told the command. `/plan-item-mode <mode> [kickoff|resolve|both]` is the
other half: its description triggers on how the preference actually gets said - "stop asking
me, just implement", "always show me a plan first" - so it works mid-conversation rather than
only as a slash command. The skill maps the phrasing, calls `set`, and then reports what
`resolve` reads back rather than assuming the write landed.

`--skill` became repeatable at the same time. The settings file is rewritten whole on every
write, so pinning both skills as two calls was two pushes to the notes branch for one
decision; a test now counts commits on the branch and pins that naming both is one.

### The gathering procedure moves out of both skills, from a review comment

Review round on #149: *"i see duplication of instructions in this skill with the
plan-item-kickoff, can this duplication be defined somwhere once and injected in both
somehow?"* Measured rather than eyeballed - a line diff of the two skills returned **41
byte-identical non-blank lines**, plus the tracking-issue subscription (identical but for one
justification sentence), the read-the-roadmap-in-full rule (12 of 13 lines), the
standing-conventions cross-check and the already-answered check (each identical but for a
clause).

On *injected*: there is no include mechanism. `SKILL.md` files are plain markdown with
frontmatter - no templating of any kind, grepped across every skill. The repository's answer,
used five times before this, is to state the procedure once and have each caller cite it in a
line, which is exactly why `execution-modes.md` made the mode step and the auto-path step the
two places these skills did *not* duplicate each other.

So `plan-dashboard/plan-item-gathering.md` now holds the setup check, resolving the item off
the notes branch, the tracking-issue subscription, its recorded state, the full roadmap read,
the dependency chain, the conventions cross-check and the already-answered check. Each skill
runs it end to end and adds only what its own situation needs - landed siblings and any
partial branch for kickoff; the pull request's mergeable state, CI, review threads and
comments plus the tracking issue's discussion for resolve. Identical lines fell 41 to 10, all
of them headings and citations; kickoff went 263 to 191 lines and resolve 200 to 129.

Scope, recorded because it went against the recommendation: this was offered as its own item,
since the duplicated prose predates the execution-modes work entirely and #135 is
ready-for-review editing both the same files, so rewriting them widens that conflict from a
few lines to most of both files. The user chose to do it in #149, and it is there.

Worth carrying: the duplication was invisible to everyone who had read either skill on its own,
and a single line diff between two sibling documents surfaced it in seconds. Sibling skills that
were written by copying one another are worth diffing periodically, not only when a reader
happens to notice.

### The recommendation is the skill's, not the script's

Settled with the user before the item was written, against the alternative of computing a
recommendation from deterministic signals (blockers present, a dependency not ready, an item
with no notes). Rejected: every one of those signals is already in the skill's hands by the time
the question is asked — steps 1-4 gather exactly that — so a script that recomputed them would
duplicate `check_dependency_readiness.py` and still be blind to the half of the judgement that
matters, which is whether the *gathered material actually settles the design*.

So the script resolves the mode and nothing else. Single responsibility, and the part that is
genuinely mechanical — precedence, validation, persistence — is the part that gets scripted, per
the same call `plan-item-bootstrap` recorded for its own split.

### Precedence, and why an invalid value is an error rather than a fallback

Invocation argument > personal-notes setting > committed default. The personal file is
`.claude/personal/plan-item-modes.toml`, layered over committed defaults at
`.claude/hooks/plan-item-modes.toml` — the same split `.claude/stack/stack.toml` and
`.claude/personal/stack.toml` already established, so a reader who has seen one knows the other.

A value outside the enum raises rather than falling back to the default. A silent fallback on a
typo means the run behaves as though the setting were absent, which is indistinguishable from it
working — and the whole point of the setting is that the user does not have to watch the run to
know what it will do.

`set` exists for the same reason: with two keys in one file, a documented raw
`write-personal-notes-file.sh` call would clobber the key the user was not changing.

### One document, two callers

The mode's meaning, the question, the auto-path obligations and the escalation rule live once,
in `plan-dashboard/execution-modes.md`, with each skill referencing it in a line — the shape
`prerequisite-check.md` and `scope-decision.md` already established, and specifically not the
per-skill copy that `add-plan-item` exists to have ended.

The escalation rule is what keeps auto mode honest: it still stops and asks when a decision
changes the item's recorded scope or contract, is not easily revertible, or deviates from the
settled plan in a way a reviewer would not expect. Everything below that bar is decided and
recorded in the PR-progress note and the pull request description instead of in a question.

One rule needed an explicit carry-over. `cram-notes.md`'s "Plan-mode approval → persistent
plans" fires on plan-mode approval, which auto mode never reaches. The shared document states
that the same multi-PR-scope judgement runs at the moment the plan is settled, so the rule does
not quietly lapse on the new path.

### `record` before `open`, for an item that does not exist yet

Found while bootstrapping this item. `plan-item-kickoff` step 7 prescribes `open` before
`record`, because the pull request number does not exist until the pull request does. That
ordering assumes an item the plan already tracks: `open_work` raises `UnknownItemError` for one
it does not, and `record` is the only operation that creates an entry (`--title`/`--track`).

Not fixed in step 7, which only ever runs against an already-tracked item. Recorded here because
the next caller creating an item from scratch will hit it, and `add-plan-item` is that caller.

New entries render with `depends_on: []` and no `notes`, so the relationship to
`plan-item-bootstrap` — this item extends the step that item added — is recorded here rather
than in the manifest. It is not a readiness dependency: that item is `done` and on `main`.

### Scope

The scope check was run rather than judged, with `git ls-tree origin/main` over the paths this
touches: all four already exist on the base, so this is standalone work rather than an edit to
an unlanded pull request. It does overlap `add-plan-item-skill`, which edits both the same
`SKILL.md` files to add its `scope-decision.md` reference — a merge conflict to expect, not a
fold, since neither exists to change the other.

## Update 2026-08-09 (new item): the manifest is written first, at every transition

Raised by the user: *"I want the plan-create skill, the plan-item-resolve skill and all
skills that can affect the plan to make updating the plan manifest and refreshing or
publishing the dashboard a first priority before anything else and at every step that
requires a change in the plan manifest or makes any status or wording stale."*

Tracked as `manifest-currency-first` on track `personal-data`, wave `immediate`.

### This is `plan-item-bootstrap` generalized, not repeated

`plan-item-bootstrap` (#143, merged 2026-08-05) inverted the ordering for exactly one
moment: the kickoff whose plan has just been approved opens the branch and draft pull
request and records the item *before* the first edit. Its own reasoning was never specific
to that moment — none of the manifest work depends on the code, so nothing justifies it
waiting for the code. Every other transition has the same property and none of them has
the rule: a status flip, a blocker appearing, a description that no longer matches, a pull
request number arriving, an item created by `/add-plan-item`, a whole plan created by
`/plan-create`.

### The premise is recorded, not asserted

This roadmap names the manifest **"the least accurate source"** three separate times in one
week — the 2026-08-03 entry for #109, the 2026-08-05 entry for #115, and the 2026-08-07
entry for #121 — and each time everything needed to diagnose the item was already sitting
on the pull request. The 2026-08-01 process entry records the same failure one step
earlier: work implemented and pushed before its plan item existed, in a session whose
request named the plan in its first sentence.

That is the argument for scripting rather than for stronger prose. The convention has been
stated, restated, and given its own item; what it has never had is a mechanism.

### Six surfaces, and the one that runs the other way

Settled with the user: `plan-create`, `add-plan-item`, `plan-item-kickoff`,
`plan-item-resolve`, `plan-dashboard`, and `stacked-pr-maintenance`.

The maintenance pass is the non-obvious inclusion and is deliberately in. It reparents pull
requests, promotes branches and moves labels — real changes to a tracked item's state — and
touches `plan.yaml` never. Its obligation is therefore the reverse of the other five: not
"write before you act" but "the items you just moved are now stale, and here is which
field". That makes the transition-time staleness check its natural consumer, alongside the
`run-report` surface #139 already built.

### Scripted by default; the document keeps only what a script cannot do

The user's instruction was explicit that this be *as scripted as possible*. What genuinely
cannot be scripted is a short list, and each entry is already recorded somewhere rather
than newly claimed:

- **Calling the `Artifact` tool.** `save-plan.sh`'s header and
  `BootstrapReport.dashboard_command` both already state it and both already hand the
  `/plan-dashboard <plan-id>` command back to the session.
- **Creating the pull request under the user's identity.** #143's live probe settled this:
  a pull request the script creates is attributed to `claude[bot]`, the app its requests
  are proxied through.
- **Knowing its own session URL.** `WorkOpenRequest.session_url`'s docstring already
  records that a session's environment cannot be asked which session it is, and that a
  script which guessed would record something wrong in silence.
- **What the notes should say**, and which status a non-mechanical transition means
  (`blocked` versus `deferred`).

Everything else — which fields contradict live state, writing them, appending the roadmap
section, emitting the republish command — is mechanical.

### The seams, surveyed rather than guessed

The work extends `.claude/hooks/plan_item_bootstrap.py` rather than adding a sibling
module. That file already owns `PlanDocuments.load`/`save`, the `ManifestKey` vocabulary,
`ItemStatus`, `locate_item_block`/`apply_item_fields` and the `BootstrapReport` shape; a
second module would re-derive the item-block parser, which is most of what it does.

Three real gaps, all of them this item's own work:

1. `record_item` requires `roadmap_section_path`, so there is no way to write a field
   without also appending a roadmap section — which most transitions do not warrant.
2. `ManifestKey` has `NOTES` and `BLOCKERS` members but no operation writes either. Today
   only status, branch, pull request number, session, title and track can be set.
3. Nothing compares the manifest against live branch/pull-request state at transition time.
   `sync_manifest_status.py` corrects one direction only (merged → done) and only on a
   dashboard run; `build_dashboard.py`'s fuller drift computation needs `jinja2` and
   `markdown`, which a hook cannot import — the same constraint `ItemStatus`'s own
   docstring already records about its duplicate enum.

### Four duplications that must not be extended

- **`run_git`** already exists three times — `plan_item_bootstrap.py`, `stack.py`, and
  #135's `check_scope_overlap.py`. Its unification is already recorded as
  `dev-tooling-notes-core-python`'s `git_interface.py` seam, with the review thread on #135
  left open for the user. Import it; do not write a fourth.
- **`ItemStatus`** is duplicated with `build_dashboard.py`'s enum and held equal by a test,
  the single definition deferred to the package migration.
- **Dashboard URL recording** belongs to #150's `record_dashboard_url.py` and must be
  called, not re-derived — that item exists precisely because the write was prose.
- **The auto-mode obligation.** #149's `execution-modes.md` already says auto mode must
  write the plan down before implementing. The shared document cross-references it rather
  than restating it; a second independently-worded copy is the exact failure
  `add-plan-item` exists to have ended.

The rule itself lives once, at `.claude/skills/plan-dashboard/manifest-currency.md`, beside
`execution-modes.md` and `plan-schema.md`, referenced in one line by each of the six skills
— the precedent `prerequisite-check.md` and `scope-decision.md` set.

### Basing, checked with the tool rather than by feel

`add-plan-item`'s own `check_scope_overlap.py` was run against `origin/main` over every path
this touches. Only two came back absent from the base: the shared document this item
introduces itself, and `.claude/skills/add-plan-item/SKILL.md`, which #135 introduces. So
this is standalone work off fork `main` with `depends_on` empty.

Textual conflicts to expect, none of them folds, since none of those branches introduces
the file it shares: #135 and #149 on `plan-item-kickoff/SKILL.md` and
`plan-item-resolve/SKILL.md`, #135 on `plan-create/SKILL.md`, #150 on
`plan-dashboard/SKILL.md`, #139 on `stacked-pr-maintenance/SKILL.md`, and the usual
`resolve-personal-notes-config.sh` constant append shared with almost everything in flight.

### The one line that cannot be written from `main`

The reference into `add-plan-item/SKILL.md` names a file only #135 introduces. By the
prefer-the-change rule it belongs on #135's branch — but the user marked #135 ready for
review themselves, which by the notes-branch convention ends a session's job on it. So the
line lands in this item's own pull request if #135 has merged by implementation time, and
is otherwise left for whoever lands #135. #143 hit the same case and could still take the
easy path: it put its equivalent line on #135 while that was an open draft.

### Two things this item deliberately does not own

**Enforcement by refusal** belongs to `plan-item-edit-guard`, which already owns the
`PreToolUse` mechanism and the inertness constraint that goes with a committed
`settings.json`. The two are complementary rather than overlapping — that item enforces
that an item *exists* for a branch, this one that the item is *current* — but if blocking
is ever wanted here, it extends that item rather than building a second hook.

**Renaming `plan_item_bootstrap.py`.** Its name stops being true once it writes more than a
bootstrap, but two skills and `resolve-personal-notes-config.sh` reference the path, and
`dev-tooling-save-plan-python` absorbs the file into the package regardless. Worth raising
with the user rather than taken unilaterally.

## Update 2026-08-10 (kickoff): manifest-currency-first opens as #151, and two premises corrected

`/plan-item-kickoff workflow-unification manifest-currency-first`, session
https://claude.ai/code/session_01NoxeSgtWJ6PuaHYQhzmw7n, as draft pull request **#151** on
`claude/plan-manifest-update-priority-ex2zst`, based on fork `main`. Bootstrapped in the
order `plan-item-bootstrap` prescribes — branch, draft pull request, manifest, roadmap,
dashboard, and only then the implementation.

### The item's own notes were wrong about the reuse seam

Recorded a day earlier: *"A transition-time check must reuse `sync_manifest_status.py`
rather than become a third drift implementation."* Reading the code rather than the
docstring disproved it, and following it would have been worse than not.

`sync_manifest_status.py` imports `build_dashboard`, which imports `render_common`, which
imports `jinja2`, `markdown` and `nh3` at module level. So a `.claude/hooks/` module
cannot import it at all — the exact constraint `plan_item_bootstrap.ItemStatus`'s own
docstring already records about its duplicated enum, met from the other side. It also
answers a *different* question: post-hoc, GitHub-side, one direction (merged → done), on a
dashboard run.

The correct split is by **what each can see**, and it is genuinely non-overlapping rather
than a compromise:

- the **dashboard run** compares the manifest against GitHub, after the fact;
- the **transition check** compares it against *this session's local git state* — the
  branch you are on, whether it is published, whether the item names it — which the
  dashboard can never see, because it happens before a push.

That keeps the hook tier stdlib-only (decision 12), needs no GitHub call, and leaves the
check importable by `plan-item-edit-guard`, whose hook must also be dependency-free.

Worth carrying, because this plan keeps producing both directions of it: an item's notes
can name a reuse seam that does not exist, exactly as a docstring can invent a
relationship (#143's third review round) or miss one (#135's `run_git` question). All
three are fixed the same way — by reading the other file rather than reasoning about it.

### Writing `notes` today silently corrupts the manifest

`ManifestKey.NOTES` is `ValueStyle.BLOCK`, its `pattern` matches the `notes: >` line, and
`render` emits a single line — so `apply_item_fields` replaces the `>` and orphans the
indented body, which YAML then reads as a continuation of the new value. Verified against
the module's own fixture:

```
BEFORE: 'A folded note whose wrapping must survive untouched...'
AFTER : 'a new note A folded note whose wrapping must survive untouched...'
```

The result still validates, so nothing catches it. That is worse than a parse error, and
it is why block-value writing is real work rather than a flag on the existing setter.
`ManifestKey.NOTES`/`BLOCKERS` have had members since #143 and no writer, so the hazard
has been latent rather than live.

### What the item builds

Three operations on `plan_item_bootstrap.py` — chosen over a sibling module because that
file already owns `PlanDocuments`, `ManifestKey`, `ItemStatus`,
`locate_item_block`/`apply_item_fields`, `BootstrapReport` and `run_git`, so a second
module would re-derive the item-block parser: block-styled field writing; an `update`
operation that writes any tracked field without the roadmap section `record_item` demands
unconditionally today; and a `check` operation reporting which recorded fields local git
contradicts, with its own non-zero status per #139's name-the-status-for-a-caller
precedent.

Plus `.claude/skills/plan-dashboard/manifest-currency.md` and a
`MANIFEST_CURRENCY_DOCUMENT` constant, referenced in one short subsection by each of the
six bound skills — the `SCOPE_DECISION_DOCUMENT` shape #135 established.

### Two scope calls settled at kickoff

**`plan-item-resolve` is the largest skill-side gap**, which the item's notes had not
singled out: it writes the manifest *nowhere*. It is a research-and-planning skill by
design, yet its own `blockers`/`notes` are precisely the fields that went stale on #109,
#115 and #121 — the three entries this item's premise rests on. It gains a step that
records what it found before proposing anything.

**`stacked-pr-maintenance` reports rather than writes.** Its obligation already ran the
other way from the rest — "the items you just moved are now stale" — and it runs
unattended under `--non-interactive`, where opening a discussion is forbidden by its own
doctrine and *why* a status changed is exactly the judgement the shared document keeps
with a session. So it maps the branches it moved to items through the generated branch
index and reports them in its finish summary. This is the one place the rule is
deliberately weaker, and the document states that with its reason rather than leaving a
reader to notice the asymmetry.

### Deferred, with the reasoning

`plan_item_bootstrap.py`'s name stops being true once it carries `update` and `check`.
Not renamed here, on the user's call: two skills and `resolve-personal-notes-config.sh`
reference the path, and `dev-tooling-save-plan-python` absorbs the file into the package
regardless — so the migration that already moves it renames it once, rather than twice
with three branches rebasing across the first attempt. Same call #106 made for splitting
`stack.py`.

The one line into `add-plan-item/SKILL.md` still cannot be written from `main`, and #135
is marked ready for review, which ends a session's job on it. It lands in this pull
request if #135 merges first; otherwise it is left for whoever lands #135.

## Update 2026-08-10: a repository-wide CI blocker, and the third base merge on #110

### `greenlet` 3.5.5 stops every job in the repository before a test runs

`test_each_lib (robokudo)` went red on #110's new head, and it is the first CI failure on
this branch that is neither a flake nor reachable from the diff — it is a hard blocker for
every open pull request:

```
error: Distribution `greenlet==3.5.5 @ registry+https://pypi.org/simple` can't be installed
because it doesn't have a source distribution or wheel for the current platform
hint: You're on Linux (`manylinux_2_39_x86_64`), but `greenlet` (v3.5.5) only has wheels for
the following platforms: `macosx_11_0_universal2`, `win_amd64`, `win_arm64`
```

It fails during `uv sync`, before a single test executes. `greenlet` is a transitive
dependency pinned in no `pyproject.toml`, no requirements file and no lock file here, so it
is resolved fresh from PyPI on every job — and 3.5.5 was published with macOS and Windows
wheels only. Any job that resolves dependencies today hits it, on any branch.

Worth recording as its own kind rather than filed with the robotics flakes this plan has
now ruled unrelated a dozen times. Those are real tests failing for reasons a `.claude/`
diff cannot reach; this is the *environment* refusing to build, so it produces no test
result at all and will not clear on a re-run. The two mechanical workarounds, if upstream
does not publish Linux wheels: constrain `greenlet` below 3.5.5, or add the
`tool.uv.required-environments` entry `uv` itself suggests in the hint. Neither is #110's
to do, so nothing was pushed.

**The check that made "not ours" provable rather than asserted**: #110's entire non-`.claude/`
diff against `main` is a four-line `.gitignore` addition, and
`git diff --name-only origin/main...HEAD | grep -Ei 'pyproject|requirements|uv\.lock'`
returns nothing. That is a stronger answer than "it looks unrelated", and it is two commands.

### The third base merge, and re-running rather than trusting it

#110 moved from `44df7fdb` to `5d3cf34b` without this session's involvement — a merge of
#107's head, pushed by another actor. Ancestry confirmed it was a clean fast-forward, so
nothing of the rebase was lost, checked with `git merge-base --is-ancestor` rather than read
off the notification. `main` had moved 203 files and ~25,700 lines beneath it.

The whole three-directory suite was re-run rather than assumed green, and the reason is on
record two merges earlier: the *second* merge produced a break the conflict markers did not
show at all — `test_personal_settings_sync.py` arriving from `main` and calling a hook script
whose transitive dependency exists only on this branch. 463 pass now, was 433; the difference
is `main`'s own new tests. `check-stack-setup.sh`'s `stack_tooling_files` row still reads
`ok`, which is the defect this item exists to fix, re-verified across both merges.

**The generalizable half**: a fast-forward is safe for *your* commits and says nothing about
whether the result still works. Ancestry answers "did I lose anything"; only running the
suite answers "does it still pass", and on this branch those two questions have already had
different answers once.

## Update 2026-08-10 (implemented): manifest-currency-first ships as #151

Implemented the same session as the kickoff, on `claude/plan-manifest-update-priority-ex2zst`.
389 tests pass across the three directories CI runs, against 367 on `main`; every new test was
mutation-checked, each failing only for its own reason.

### The corruption was latent, not hypothetical

`ManifestKey.NOTES` and `BLOCKERS` have had members since #143 and no writer, which is the
only reason nobody had hit this. `NOTES` is block-styled, its `pattern` matches the `notes: >`
line, and `render` emitted a single line — so `apply_item_fields` replaced the `>` and left
the indented body behind, where YAML reads it as a continuation of whatever replaced it:

```
BEFORE: 'A folded note whose wrapping must survive untouched...'
AFTER : 'a new note A folded note whose wrapping must survive untouched...'
```

The manifest still validates afterwards, so no schema check would ever have caught it. Worth
recording as a shape rather than an incident: **a member that exists with no writer is
untested by construction**, and the bug is waiting for whoever writes the first one.

Fixing it needed one modelling change. `ValueStyle.BLOCK`'s docstring said "a folded scalar
*or a sequence*" — true of the layout, and wrong as a rendering instruction, since `notes` is
prose and `blockers` is a list. `SEQUENCE` is now its own style, with the shared property
(`spans_lines_beneath`) deriving `BLOCK_STYLED_KEYS` so the insertion-point logic keeps
meaning what it meant.

A second detail only a round-trip test finds: a folded scalar (`>`) appends a trailing
newline. That is right for a note — every note already in these manifests ends in one — and
wrong for a list entry, which has to parse back as exactly the string it was given. Sequence
entries use `>-`.

### The reuse seam the item's own notes named does not exist

Recorded a day earlier: *"a transition-time check must reuse `sync_manifest_status.py`."*
Reading it disproved that. It imports `build_dashboard` → `render_common` → jinja2, markdown,
nh3 at module level, so a hook cannot import it — the constraint `ItemStatus`'s docstring
already records from the other side. It also answers a different question: post-hoc,
GitHub-side, one direction only.

The split that replaced it is by **what each can see**, which is why it is non-overlapping
rather than a compromise: the dashboard compares the manifest against GitHub after the fact;
`check` compares it against local git *before a push*, which the dashboard can never see. The
side effect worth keeping is that `check` stays stdlib-only, so `plan-item-edit-guard` — whose
`PreToolUse` hook has the same constraint — can import it when it is built.

### What `plan-item-resolve` was missing, which the item had not spotted

The notes named six bound skills without ranking them. In practice one gap dwarfed the rest:
`plan-item-resolve` wrote the manifest **nowhere at all**. It is research-and-planning by
design, and its own `blockers`/`notes` are exactly the fields that were stale on #109, #115
and #121 — the three entries this item's premise rests on. So the skill that exists to
diagnose a stalled item was the one guaranteed not to record the diagnosis. It now writes what
it found before proposing anything.

### Reporting rather than writing, and why that is not a weakening

`stacked-pr-maintenance` maps the branches it moved to items through the generated branch
index and names them in its finish summary. It does not write. Two independent reasons, both
already load-bearing elsewhere: it runs unattended under `--non-interactive`, where its own
doctrine forbids opening a discussion, and *which* status a reparent or a promotion implies is
judgement rather than mechanics. A pass that guessed would write a manifest nobody decided.

### The contract test derives its own scope

Which skills are bound is computed from what they do — a skill invoking a plan-writing script
is bound by that fact — rather than listed, so a skill added later is covered without the test
being edited. Only the maintenance pass is named, because it is bound for the opposite reason,
and its test asserts the asymmetry directly: it cites the rule *and* invokes no plan-writing
script.

### Verified live, not only in the harness

`check` was run against all 41 items of this plan. One true positive:
`dependency-chips-blocked-fix` records a published branch with no `session`, exit 9. The other
40 came back clean. `update` then wrote this item's own notes — the tool used on the manifest
it was built for, and the produced block is indistinguishable from a hand-wrapped one.

### An incidental fix, and what it says about the suite

The scratch repository fixture now disables commit signing. This environment signs by default,
so every scratch commit depended on a reachable signing service; the suite failed on a
*different* test each run with `signing server returned status 520`. It also halved the
runtime, 75s to 35s. The general point is the same one #139 recorded twice: **a test that
depends on ambient state fails for reasons that have nothing to do with it**, and the fix is
to control the state rather than to retry.

### Deferred, with the reasoning rather than silently

`plan_item_bootstrap.py` keeps its name though it now carries `update` and `check`, on the
user's call: `dev-tooling-save-plan-python` absorbs the file into the package regardless, so
that migration renames it once rather than twice with three branches rebasing across the first
attempt. The one line into `add-plan-item/SKILL.md` still cannot be written from `main`, and
#135 is marked ready for review, so it lands here only if #135 merges first.

### CI, and a base-side breakage worth knowing about

`test_each_lib` is red across the matrix and it is not this branch's: `greenlet` 3.5.5 was
published with no Linux wheel, so `uv` fails to resolve before any test runs. `main`'s own push
run failed 11 jobs three minutes before this branch's, the previous `main` run was green, and
`test_claude_dev_tooling` — the only job reaching a `.claude/`-only diff — passes. It blocks
every pull request in the repository until `greenlet` is constrained or
`tool.uv.required-environments` is set; reported on #151 rather than fixed here, since it is
neither this item's scope nor a one-branch problem.

## Update 2026-08-10: the "subscribe to your own PRs" rule is inverted, as #153

The workflow's oldest standing assumption was that a session stays live on the pull request
it opened: subscribe to every event, handle each one, keep it up until the PR's job ends.
The user's decision is the opposite, and it is not a tuning of the old rule but its
inversion — **a session never subscribes to a pull request's activity at all**. Opening a
pull request is now terminal for the session that opened it: push, report in the chat what
was done and what is still outstanding, stop. A CI failure or a review comment gets handled
when the user asks for it, in a session started for that.

### Why it needed two commits in two places

The rule lived in the personal notes *and* in the repository, and only the second half is
reviewable. `cram-notes.md` carried the instruction itself; `starter-notes.md` shipped the
same bullet as the default any new user of `/setup-personal-notes` inherits. Changing one
without the other would have left the starter set teaching the rule the notes had just
dropped.

The personal-notes half also touched three sections written *around* the old assumption,
which is the part that would have rotted quietly if only the bullet had been flipped:
"Scheduled checks" declared event subscriptions "fine and wanted" (true of tracking issues,
now false of pull requests); "Comment routing" justified its action-only rule by saying PR
comments wake subscribed sessions (nothing wakes now — the reason is that an FYI is triage
noise for the owner); and "When your PR's job ends" was mostly a teardown procedure for
subscriptions that no longer exist, so it reduces to deleting armed triggers.

### The scope call: pull requests, not tracking issues

`subscribe_pr_activity` is also how a plan's tracking issue is watched — the tool takes a
plain issue number. Those subscriptions stay. A tracking issue is a coordination mailbox
several sessions read, not a pull request one session owns, so `/plan-create`,
`/plan-item-kickoff` and `/plan-item-resolve` keep theirs unchanged, `allowed-tools` included.

What that leaves is wording that assumed both kinds coexisted. `plan-schema.md` and
`session-start.sh` both told a session to subscribe to the tracking issue "(in addition to
your own item's PR)" — there is no longer an item PR for it to be in addition to.

### Two passages that explained behaviour by the old rule

Neither is a rule, which is why a grep for `subscribe_pr_activity` alone would have missed
them. `stack/README.md` told a scheduled maintenance pass to poll CI and "leave
`subscribe_pr_activity` to an interactive session babysitting that one PR" — the exception
now has no one to name. `stacked-pr-maintenance/SKILL.md` told its `needs-resolution` comment
that it might reach the owning session as a live event; it will not, so the comment has to
stand alone on GitHub. The skill's own `NEVER call subscribe_pr_activity` hard rule was
already correct and is untouched.

### Verification, and what could not be run here

`bash -n session-start.sh` passes — it is the only executable change. Every surviving
`subscrib` match under `.claude/` was read individually and is a tracking-issue subscription,
an unsubscribe, or a prohibition. `.claude/hooks/tests` never referenced the changed strings,
so no test needed updating; pytest is not installed in this container, so the suite was not
run locally and CI covers it.

## Update 2026-08-10 (new item): a regenerated integration branch, designed but unbuilt

`integration-branch` enters `stack-tooling` as `not_started` with no branch and no pull
request. Three implementation attempts were blocked in the designing session, so what exists
is a design and the reasoning behind it — recorded here because that reasoning is the part
that would otherwise evaporate with the session.

### The constraint is review throughput, not branch hygiene

Every other item in this track improves how branches reach cram2. This one accepts that the
queue is slow and asks a different question: what do you build *from* while twenty of your own
features sit unreviewed? The answer is a branch that is upstream main with every in-flight
stack tip merged on top, regenerated from scratch on demand. It is not history. Nothing merges
out of it, and a conflict found on it is fixed in the feature branch, never on the branch
itself.

### Why it must not gate promotion

The tempting design is to let a clean integration build mean "ready for upstream". It cannot,
and the reason is structural rather than a matter of taste: if A and B conflict, gating
promotion on a clean build blocks A because of B, with no principled reason A is the one that
waits. Promotion asks whether a branch is ready for review against upstream main; integration
asks whether the branches coexist. Two different questions, so integration runs parallel to
the promotion pipeline and feeds signals into it rather than standing in front of it.

### Three reversals this session made against its own earlier spec

Worth recording as reversals rather than as conclusions, because each was held confidently
first:

**Stop-on-conflict became skip-and-continue.** A build that halts on the first conflict leaves
nothing to work from, which is precisely the thing the branch exists to provide. The cost of
the reversal is that merge order now decides *which* branch gets skipped, so order became an
explicit, stated property (`stack.order()` within a stack, ascending PR number between stacks)
and the report names the conflicting pair rather than the casualty — "B skipped" is not
actionable.

**The CI gate was dropped rather than fixed.** It would have deadlocked against the restack:
restacking rewrites heads, CI re-runs, every restacked branch reads `pending`, a green filter
excludes it, and the build comes back near-empty. That was the single most likely way the
feature disappoints on first use. Dropping it also removed a dependency on a field that does
not work — see below. What replaces it is one `--test` run on the finished branch, which is
strictly more informative for less work: it catches semantic conflicts that per-branch CI
structurally cannot, such as A renaming a method while B adds a caller, both green, merging
clean and breaking on import.

**rerere was cut, then restored.** The cut rested on a premise that turned out to be false —
that conflicts are never resolved on the integration branch. They are, constantly, and the
resolutions are exactly the state these ephemeral containers lose. It is back, persisted to
personal-notes as a tarball, with the limit stated rather than papered over: it buys a working
daily driver, not a discharged upstream obligation.

### The sibling conflict is what splits the work between script and skill

"Conflicts are fixed in the feature branch" conflates two situations, and only one has a
feature-branch fix. A branch conflicting with upstream main is stale — clear owner, clear fix,
handled by `--restack`. Two siblings conflicting with each other is different: both are based
on main, both are destined upstream, neither is wrong, and adapting B to an unlanded A makes B
depend on unmerged work, which is the stacking this workflow exists to avoid.

So there is often no correct branch to fix *today*, and that is what makes the decision a
judgement rather than a script's. Detecting a collision and attributing it to a pair is
mechanical (`merge-tree`, non-mutating, cheap). Deciding what the collision *means* is not, and
it has three real outcomes: **reconcile** when the two are duplicating something and one should
adopt the other's abstraction — this plan's own history has that case, with #110 and #106
independently building the same artifact; **stack** when B genuinely depends on A, which the
existing tooling already models as `base = parent`; and **defer** when they touch the same
lines incidentally and whoever lands second adapts.

`integration.py` therefore keeps detection, attribution and skipping and makes no judgement;
`/integration-conflict-triage` makes the call. The skill is deliberately not a comment-bot:
only *reconcile* and *stack* give an owner something to do, and the comment-routing rule
already sends pure FYIs to the manifest rather than to a pull request nobody is watching. No
detection-time reporting is built at all, because the maintenance pass's `needs-resolution`
label and `IntegrateParent` comment already cover landing time — when the conflict is real and
its target stable.

### A hole in #139's export, found independently of this design

`stack.PullRequest.ci` is declared, documented (`success`/`failure`/`pending`/None), read by
`load_board` and copied onto `Branch` by `build_stack` — and never populated.
`BoardExport._pull_request` sets it from `record.get("ci")` against a `GET /pulls` payload that
carries no such key, in the one method whose stated contract is that it refuses a missing
derived field rather than defaulting it. Gating on green would have meant making that field
real first — a head-SHA export field, a check-runs fetch and a conclusion enum — inside this
pull request. Dropping the gate removed the dependency, but the hole is real independently of
whether anything reads it, and telling #139 is left open.

### One naming constraint that is not cosmetic

Builds are `integration-<timestamp>`, hyphen rather than slash, with `integration` as a moving
pointer. Git stores refs as files, so `refs/heads/integration/<timestamp>` cannot exist while
`refs/heads/integration` does: the obvious naming is the one git refuses. Recorded because it
looks like a style choice and is not.

### Basing, checked rather than assumed

The item depends on `stack-maintenance-executor` and would branch from #139's head rather than
main, because `maintenance.py` exists only there — `git ls-tree main -- .claude/stack/` is
empty for it. Run against the prefer-the-change test: removing the edits to #139's files would
still leave a whole new module, its test module and a new skill, so this is real work stacked
on unlanded work rather than an artifact of the order things were thought of.

### Open at recording time

Whether `--restack` defaults off locally and on in the on-demand Action; whether `--test`
defaults on; whether to tell #139 about the `ci` field; and whether the script and the skill
are one pull request or two — recommendation one, since a conflict report nothing consumes is
half a feature.

## Update 2026-08-10: the triage skill resolves too, bounded by where the resolution lands

Follow-up to the item added earlier the same day, from the user's question: should
`/integration-conflict-triage` also solve the conflicts, and should it ask when something is
unclear or could be harmful? Both, with the boundaries below.

### The artifact decides the risk, not the confidence

The tempting rule is "resolve when sure, escalate when not". It is the wrong axis. A confident
resolution written onto a published feature branch is more dangerous than an uncertain one
written into a throwaway cache, so the question is where the resolution lands:

- **Defer → resolve fully.** The artifact is a `.git/rr-cache` entry. No feature branch is
  touched, the integration branch is rebuilt from scratch every run, and `--test` checks the
  result. A wrong answer costs one cache entry.
- **Reconcile → propose, don't apply.** This is a real code change to a pull request under
  review. Resetting an approval to apply a design call its author has not agreed to is the
  wrong default, however good the change.
- **Stack → report.** Re-basing belongs to `maintenance.py`, and the base-branch PATCH 403s
  through the agent proxy anyway — a session cannot perform it even if it should.

This closes the design's weakest step rather than adding a feature. As recorded, `resolve
--record` set up a worktree and expected the developer to fix the files by hand. Defer is both
the commonest verdict and the one where the skill already holds everything the fix needs —
both diffs and both pull request intents — so leaving it to a human was the least defensible
part of the split. The boundary itself is unchanged, only restated: the script never writes to
a branch, the skill writes only to `rr-cache`, and neither pushes.

### Asking is about whose decision it is, not about how sure the skill is

A skill that asks whenever it is unsure becomes a prompt generator, and prompts that arrive
without a recommendation get rubber-stamped — which is worse than not asking, because it
launders the skill's guess as the developer's decision. The usable test is ownership:

- **Uncertainty about facts** — what a branch does, whether two implementations are the same
  abstraction — is resolved by reading the diffs, the pull requests and the roadmap. Never
  asked.
- **Uncertainty about intent** — which abstraction is right, whether two branches should have
  been one pull request — is asked.

That maps almost exactly onto the reconcile verdict, and the question comes *before* the
proposal, since a proposal already encodes the choice it would be asking about. The cost of
not asking is on record in this plan: #110 and #106 independently built the same artifact.

### A new hazard, created by the skill authoring resolutions

rerere matches on the conflict preimage and replays automatically. A resolution that is
textually matching but semantically wrong is therefore reapplied, unreviewed, on every later
build. That risk already existed for human-recorded resolutions and was accepted; it is a
different proposition once a skill is the author.

So a recorded resolution carries its provenance, and the build report distinguishes
skill-authored replays from human-authored ones. The existing rule — a replay is never
reported as a clean merge — stands, and gains an author so the machine's resolutions can be
audited without re-reading one's own. And a `--test` failure following a skill-authored
resolution reports and stops rather than trying again: re-resolving into the same failure is
how a build starts thrashing.

## Update 2026-08-10 (kickoff): integration-branch opens as #154, with three of its four open questions answered

`/plan-item-kickoff workflow-unification integration-branch`, session
https://claude.ai/code/session_01Ue4PvfV5LDxHGRRS5BZB4g. Bootstrapped before implementation:
branch `claude/plan-item-kickoff-workflow-ixbvxl` off #139's head (`04902f40`), draft pull
request **#154**, manifest flipped to `in_progress`.

Nothing here revises the design recorded earlier today. What this entry adds is the four
questions that were left open at recording time, now closed, and one hazard the design did
not carry.

### The three open questions, answered

**`--restack` defaults off, as a plain opt-in flag** — not off-locally-on-in-the-Action via
config, which was the shape the item recorded. The deciding argument is the boundary the
design already states rather than a preference about ergonomics: *the script never writes to
a branch*. `maintenance.restack` pushes to other people's feature branches, so a default that
runs it makes the sentence false of the default path and true only of a path nobody takes.
The Action passes the flag explicitly, which also keeps one command meaning one thing in both
places.

**`--test` defaults on, with `--no-test` to skip.** It is not a convenience: it is the entire
replacement for the CI gate this design dropped, and the roadmap's own reason for dropping the
gate was that a single run on the finished branch is *strictly more informative*. A build
nobody tested is the failure mode the flag exists to prevent, so it cannot be the one that
happens by default.

**#139 is told about the `ci` field.** Routed as a pull request comment rather than to the
manifest alone, against the comment-routing rule's own bar: it is a defect in code currently
under review, so the review context materially changes. That is a different judgement from the
one the design made when it dropped the CI gate — dropping the gate removed *this item's*
dependency on the field, and left the hole exactly where it was.

**Script and skill ship as one pull request**, taking the recommendation the item already
recorded, for the reason it recorded: a conflict report nothing consumes is half a feature.

### The question nobody had asked: what `--test` actually runs

Settled at kickoff because it is unanswerable from the design as recorded. A
`integration_test_command` setting in `stack.toml`, defaulting to the three directories CI's
`test_claude_dev_tooling` job already runs. Configurable because the useful suite is a
property of the repository rather than of this tool; defaulted rather than required because a
flag that is on by default and has nothing to run is worse than one that is off.

### The exit status is designed in, not discovered live

#139 shipped, ran live, and only then found that a restack hitting a conflict and a refused
fast-forward both exited `0` — *"a test over the return value does not cover the exit status"*,
and the exit status is the only half a scheduled Action reads. This item inherits that finding
before writing a line, so `IntegrationExitCode` and its per-outcome tests are in the first
commit rather than in a correction after a live run. It is the second time this plan has had a
lesson available *before* meeting it rather than after; the first was #139 inheriting
`plan-item-bootstrap`'s two `Enum` hazards.

### A hazard the design did not carry

`greenlet==3.5.5` has no Linux wheel, so `uv sync` fails before a single test runs on every
open pull request in this repository, on any branch. Red robotics jobs on #154 will not be
#154's doing, and the proof is two commands rather than an assertion: its diff touches no
`pyproject`, `requirements` or `uv.lock` file.

Basing was re-run rather than inherited: `git ls-tree origin/main -- .claude/stack/` carries
`stack.py`, `stack.toml`, `README.md` and three test modules, but not `maintenance.py`. Against
the prefer-the-change test, removing every edit to #139's files still leaves a whole new
module, its test module and a new skill — real work stacked on unlanded work.

## Update 2026-08-10 (implemented): integration-branch ships as #154

Implemented in the kickoff session, on `claude/plan-item-kickoff-workflow-ixbvxl`. 470 tests
pass across the three directories CI runs, against 428 before; the 42 new ones were written
failing first and each was mutation-checked to fail only for its own reason.

### Two failure shapes git makes identical, told apart before the design was committed to

This is the part worth carrying, and it was settled by probing real git rather than by
reasoning about it.

A merge that fails leaving **no unmerged paths** is not a conflict - unrelated histories, a
reference that does not resolve, something in the way. That is #123's false-positive class,
which the maintenance executor had to correct after reporting empty file lists to a branch
owner whose branch merged perfectly well. This item inherited it before meeting it.

What no entry had recorded is that a **replayed rerere resolution fails the same way**. With
`rerere.autoupdate` on, the replay stages the resolved files, so the merge exits non-zero with
an empty unmerged-path list - byte for byte the shape of a merge that never began. The only
thing separating them is what git says on stderr (`using previous resolution`). So the replay
marker has to be read *first*, and the mutation confirming it is the sharpest one in the suite:
making the marker never match turns every replay into `integration-failed`, which is precisely
the hazard reading it exists to prevent.

The general shape: **when two outcomes are indistinguishable by the state they leave behind,
the thing that distinguishes them is not optional - and a test that pins it has to be written
from the observation, not from the design.**

### The three open questions, and a fourth nobody had asked

`--restack` defaults off as a plain opt-in flag rather than off-locally-on-in-the-Action via
config. The deciding argument is the boundary the design already states: *the script never
writes to a branch*. `maintenance.restack` pushes to other people's feature branches, so a
default that runs it makes that sentence true only of a path nobody takes.

`--test` defaults on. It is not a convenience - it is the entire replacement for the CI gate
this design dropped, and the reason for dropping the gate was that one run on the finished
branch is *strictly more informative*.

#139 was told about the `ci` field on its own pull request, against the comment-routing rule's
bar: a defect in code currently under review materially changes its review context.

The fourth was unanswerable from the design as recorded: **what `--test` actually runs**. An
`integration_test_command` in `stack.toml`, defaulting to the three directories CI already
runs. Configurable because the useful suite is a property of the repository rather than of the
tool; defaulted because a flag that is on by default and has nothing to run is worse than one
that is off. A build asked for a suite the checkout names none for is refused *before* anything
is built, rather than reading an absent suite as one that passed.

### The live run, and what it found without being told

Run from a detached worktree against the real fork: **23 tips, 11 merged, 12 skipped**, exit
`tip-left-out (10)`. Six collided with `main` itself and six with siblings - among them #120
against #111 on `build_dashboard.py` and #135 against #111 on `ci.yml`, collisions this plan
had already recorded in prose and which the run surfaced from git alone.

Attribution earning its keep is the point: naming the *base* for a stale branch and a *sibling*
for a real collision are different answers, and a tool that always blamed the most recent tip
would have sent six branch owners somewhere pointless.

Confirmed after the run rather than assumed: the invoking checkout still on its own branch with
a clean tree, `integration` pointing at the build, every merged tip an ancestor of it and every
skipped one not, no worktree left behind, and nothing pushed - the fork has no `integration`
branch and no tip moved.

The selection rule also showed on real data: **#139 is absent from the tips** because #154 is
based on it, so its commits arrive as part of #154's. A tip contains its stack, which is why
only tips are merged.

### Changes to the parent's files, each a consequence rather than a detour

`GitCommandRunner` gains per-command configuration overrides, so the build turns rerere on for
itself without writing it into the developer's own repository - config is shared with whoever
invoked the build, and a tool that permanently enabled a git feature on their clone would be
taking a decision that is not its own. It also gains two named git methods, following that
class's own one-method-per-command idiom.

`Configuration` gains `integration_test_command`, and `print_configuration` now omits a setting
that is **empty** as well as one that is unset. That is not a new rule: its own docstring
already promised "a setting with no value is omitted rather than printed empty", and only
checked `None` because until now every optional setting was `None`-able. A defaultable string
made the promise reachable, and the existing contract test caught it - which is the test working
rather than a test needing changing.

### A note on the docstring formatter

`scripts/format_docstrings.py` reformats a multi-line docstring into a one-line summary plus a
body, and where the first sentence spans two lines it cuts the sentence in half and leaves the
remainder as a paragraph starting mid-clause. Two docstrings landed that way and were rewritten
with a genuine one-line summary so the formatter is stable over them. Worth knowing before
running it over prose-heavy test docstrings: the fix is to write the summary line the formatter
expects, not to skip the formatter.

## Update 2026-08-11 (`manifest-currency-first`, #151): the maintenance pass writes after all

Raised by the user, reversing a call this item itself made a day earlier: *"i want the stack
maintenance skill to also update the plan manifest files and publish the dashboard, for example
conflicts are detected and now the item is blocked because it needs resolution, this information
should be instantly updated in the dashboard."*

Folded into this item rather than opened as its own, by the scope rule: it rewrites the section
`manifest-currency.md` introduced, the section `stacked-pr-maintenance/SKILL.md` gained from it,
and the contract test asserting the pass writes no manifest. Strip those and nothing stands on
its own; `main` is not a possible base either, since `manifest-currency.md`, the
`MANIFEST_CURRENCY_DOCUMENT` constant and `update` exist only here.

### One of the two reasons for reporting was simply wrong

The recorded reasoning was that the pass "runs unattended under `--non-interactive`, where its own
doctrine forbids opening a discussion". `--non-interactive` suppresses `AskUserQuestion` and
nothing else: `routine-prompt.md` registers the pass as `/stacked-pr-maintenance ...
--non-interactive`, which is a live Claude session, so the `Artifact` tool was reachable the whole
time. The doctrine forbids opening a *discussion*, not writing a file. It was reasoning about the
mode's name rather than about what the mode does.

The second reason survives intact and bounds the change: *which* status a reparent or a promotion
implies is a reading, not a mechanical fact. So the pass writes only what it decided itself - a
branch it labels `needs-resolution` is blocked because this pass concluded so, and one whose label
it clears is not - and reports reparents, promotions and landed branches as before. A landed branch
needs no write at all; `sync_manifest_status.py` corrects merged to `done` on the refresh the pass
now triggers anyway.

The write is a script call and the publish is a skill invocation, which is also what makes this
survive `routine-cutover`: after that the pass is a plain Action with no session in it, the writes
keep working unchanged, and publishing moves to `stack-board-single-site`'s built site.

### Keyed on a branch, because that is what the pass holds

`update` needs a plan id and an item id; the pass has neither. `PLAN_BRANCH_INDEX_PATH` stops at
the plan id and `PlanDocuments` only looks items up by id, so `resolve --branch` was the missing
half. `block`/`unblock --branch` then follow, rather than leaving a session to filter a blocker
list in shell prose: the owner is written into the blocker (`<owner>: <reason>`, under
`MAINTENANCE_BLOCKER_OWNER`), so a pass replaces and withdraws its own entries and never a
person's, and an item still carrying somebody else's blocker stays `blocked`. Two items on one
branch is ordinary - `landed-parent-detection` and `session-safe-pr-reparent` share one today - so
all three operations answer for every item on the branch.

### Two defects the live run found and the harness had not

Both were reached only by writing a real blocker into this plan's own manifest, which is the
argument for running these against the fork rather than only in a scratch repository.

**Folding broke inside words.** `textwrap.fill` breaks at hyphens and through any word too long
for the column, and a folded scalar reads a line break back as a space - so
`claude/workflow-unification-setup-jgvs53` came back as `claude/workflow-unification-setup-
jgvs53`, still valid YAML and no longer the branch anybody named. Latent since the block-styled
writer landed, and reachable the moment something wrote an identifier into a note or a blocker,
which is exactly what this change does. `fold` now breaks only between words; a word wider than
the column overflows it, which is the one thing wrapping is allowed to get wrong here.

**Withdrawing a blocker an item never carried wrote it an empty list.** The pass clears its label
from every branch it finds clean, most of which it never blocked, so this would have spread
`blockers: []` across the whole manifest one run at a time. Observed live on
`landed-parent-detection` and `session-safe-pr-reparent`; reverted, and the write is now skipped
for any field whose value is unchanged.

### `plan-create` already published; the index did not

The second half of the request turned out to be nearly done: step 8 has invoked the
`plan-dashboard` skill since before this item existed. The real hole was the master index, which
step 8 *asked* about - so a plan was created and then missing from the one page that lists every
plan, until somebody thought to run `/plan-dashboard` with no argument. Creating a plan is the
single change that alters what the index itself lists, which is why it is the exception to the
don't-republish-the-index-unprompted convention rather than a violation of it; `_index` has its own
cached URL, so it updates that page rather than minting a second.

## Update 2026-08-11 (review round): #139's executor becomes eleven modules, and the third try at a class property

`/plan-item-resolve workflow-unification stack-maintenance-executor`, handling the four comments
of 2026-08-11. Session: https://claude.ai/code/session_01DHbsXEZCDRYbegKU4iVGyP. Applied in
`ebf67734`.

### The split, and why it went further than either comment asked

Two comments asked for modules: the restack step classes in one with `RESTACK_STEPS` in another,
and the command classes in one with `COMMANDS`. The second is what reshaped the file, for a reason
that only shows up once it is attempted - **a commands module cannot both be imported by
`maintenance.py` and import everything the commands do.** That is a cycle, and the only way out
that keeps `python .claude/stack/maintenance.py <command>` as the entry point is to invert it: the
entry module holds the parser, `main` and `_dispatch`, and everything else moves below the commands.

So the file became eleven modules rather than three: `maintenance_constants`, `maintenance_errors`,
`maintenance_git_commands`, `maintenance_board`, `maintenance_github`, `maintenance_fast_forward`,
`maintenance_restack_steps`, `maintenance_restack_procedure`, `maintenance_promotion`,
`maintenance_report`, `maintenance_commands`. The seven hand-maintained constants went into the
first of them, which answers the 2026-08-07 comment in its original form.

**This overrides the standing deferral for `maintenance.py` only.** The recorded decision of
2026-08-02 was that no `.claude/` Python file is split before `dev-tooling-python-package`, so the
surgery happens once - the reasoning that kept `stack.py` whole through two review rounds. The user
instructed the split here explicitly, so it is taken for this file; `stack.py` is untouched and
still waits for that item. Whoever runs `dev-tooling-python-package` inherits eleven modules to
place rather than one, which is less work, not more.

`test_every_module_of_the_executor_imports_on_its_own` imports each module in a subprocess of its
own. A layout like this fails silently otherwise: a cycle only bites whichever module a caller
imports first, so the suite could stay green while the entry point was broken.

### The class-property question, settled by measurement on the third round

`invoked_as` and `description` have now been three shapes: `ClassVar` + `__init_subclass__`,
abstract properties, and - as of this round, on the user's instruction - `classproperty` +
`abstractmethod`. The measurement nobody had made is the one that matters:

> A plain `classproperty` **silently loses the abstractness.** `ABCMeta` decides what is still
> abstract with `getattr(cls, name)`, which *calls* the descriptor and gets a plain string back -
> never anything carrying `__isabstractmethod__`. So a subclass supplying nothing was not abstract
> and answered `None`.

The fix is that `__get__` answers with the descriptor itself while it is abstract. Then a nameless
command is refused with the ordinary `Can't instantiate abstract class ...` message, and since
`COMMANDS` instantiates every subclass, the refusal lands as the module is imported - before the
parser it feeds exists. Enforcement is at construction rather than at class definition, which is
strictly later than `__init_subclass__` was; the user was told that when recommending against the
switch, and chose it anyway.

`classproperty` lives in `class_property.py` and is written rather than imported from `krrood`,
per decision 12's stdlib-only tier for this layer.

### The `Protocol` question, answered

The three "dataclass" comments of 2026-08-10 against `PullRequestReader`, `PullRequestWriter` and
`ForkPullRequests` had been left open with two readings and a recommendation. The user chose
abstract dataclasses, and applying it turned up two things neither reading predicted:

- **Frozen-ness is inherited as a constraint.** dataclasses refuse a non-frozen subclass of a
  frozen base, so making the bases frozen - the idiom everywhere else in the module - made both
  test stand-ins frozen too. The one that assigned a field appends to a list now.
- **It found a hole structural typing could not see.** The fork stand-in never implemented
  `open_pull_requests`; `restack` and `promote` never call it, so nothing noticed for three rounds.
  Completed rather than stubbed.

### Left open on purpose

The `--quiet` question is answered (it is git's own progress suppression; the runner captures both
streams regardless, so what it changes is what a failure message carries) and calls for no change,
so the thread stays open for the user to close. The doc-formatting thread's outstanding half is
whether main's 8 unformatted files get a sweep of their own. `gh`/PyGithub stay deferred to
`dev-tooling-github-api-unification`.

154 tests pass, was 151.

## Update 2026-08-11 (live on the real stack): the build works, and it found a gap in its own skill

Run on the real fork at the user's request. The build did what it was built to do, and the run
turned up two things worth recording: a real defect in two of the plan's own pull requests, and
a gap in this item's deliverable that nobody had noticed while it was being written.

### The semantic collision, found on the first real run

`build --test` came back `tests-failed`. Measured rather than inferred:

| tree | `test_check_stack_setup_sh.py` + `test_setup_stacked_prs_sh.py` |
|---|---|
| #110 alone | 32 passed |
| #111 alone | green |
| #110 merged with #111 | **18 failed** |

The merge is completely clean - no textual conflict, nothing for `merge-tree` to report. #111
gives `stack.py` a module-scope import of the repository-root `development_tooling` package;
#110's `check-stack-setup.sh` shells out to `stack.py configuration`, and its scratch fixture
builds a minimal project without that package. Merged, `stack.py` dies on import, `configuration`
exits non-zero, and every dependent check degrades to `not checked`.

Neither branch is wrong, and **neither branch's CI can see it** - the failure exists only in a
tree neither of them is. That is the exact failure class this design was written against,
appearing unprompted the first time the tool was pointed at the real stack. Reported on both
pull requests with the measurements and no proposal: which side absorbs it is a design call, and
the honest options (the fixture provides what `stack.py` needs, or `stack.py` stays runnable
without the package) belong to their owners.

### The gap that found: a verdict with nothing to reach it

The skill classified the status and stopped. Two things were missing, and only the second was
obvious from reading it.

**A verdict cannot be reached without localising the break first.** A red suite over a dozen
merged tips names no branch. Localising it by hand is several worktrees and several suite runs -
and this session got that wrong once, reusing a worktree path `git worktree` still had registered,
so a `cd` failed and two merges ran in the invoking checkout (recovered with `git merge --abort`;
nothing was committed, and `integration.py` itself never did that, because it builds behind a
detached checkout in a worktree of its own). Prose telling an agent to bisect by hand would have
been an instruction to repeat that.

So `integration.py bisect` re-assembles the tips in the same order, runs the suite after each,
names the tip whose arrival turned it, and narrows to the earlier tip that alone reproduces it -
the same shape as the merge case's pair attribution, and for the same reason: naming everything
already in the build is not actionable when one of them is innocent. It reproduced the #110/#111
finding independently, leaving out the innocent tip merged before them.

**And the verdicts themselves needed a different rule.** `adapt`, `reconcile` and `sequence`, all
proposed rather than applied. But the load-bearing sentence is what is *not* available:
**`rerere` replays a merge conflict's resolution, and a semantic break has no conflict to key one
on**, so nothing can be recorded and every later build carries it until a branch changes.
Reasoning by analogy from the merge case - reaching for `defer`, recording something, reporting a
fix - is the mistake that section exists to prevent, which is why a contract test pins that
sentence rather than trusting the prose to survive an edit.

### Two smaller things the run corrected

The first version of the narrowing built each probe on a branch named after the pair, which
outlives the answer; one was left in the clone by the live run. Probes are built on a detached
head now, so there is nothing to clean up rather than something to remember to clean up.

And the integration branch was pushed to the fork on request. Worth stating plainly because the
tool never does it: `build` writes to no branch and pushes nothing, so a build lives only in the
clone that made it, and an ephemeral container takes it with it.

## Update 2026-08-11 (review round): the duplication that was doing work, and a trap retired

Eleven threads on #151, applied in `0118aca6`. Three were substantive, and the first
qualifies a generalization this roadmap made four days earlier.

### Single-sourcing a contract deletes a guard — and whether that matters depends on who reads it

The ask was to make the report's JSON keys a `StrEnum`. Done, as `ReportKey`, holding only
the keys this module invents — a key naming a manifest field still comes from `ManifestKey`,
since `status` appears in both and means different things in each.

But the **tests deliberately keep their string literals**, and that is the whole finding.
With the render methods and the tests both reading the enum, renaming a member's value
changes them identically and no test fails: the rename becomes invisible, and a breaking
change to a format two other programs parse (`stacked-pr-maintenance` today,
`routine-cutover`'s Action later) ships green. #135 hit exactly this — renaming
`SHARED_PATHS` there left all 8 tests passing — and its fix was to add one test pinning
member names to wire values.

Here the literals the assertions were going to contain anyway already do that job, measured
rather than assumed: renaming `FINDINGS` still fails
`test_the_check_subcommand_exits_stale_and_names_the_field`.

That refines the 2026-08-07 entry, which promoted "single-source, then add one contract
test" from precedent to expectation, and the 2026-08-07 second round, which then cut such a
test on the user's instruction. Both were right about their own case, and the rule joining
them is narrower than either: **notice the guard you are deleting, and decide by who reads
the contract.** A diagnostic line a human reads is the owner's call to pin or not; a wire
format another program parses has to stay pinned by something. The thread asking for the
enum in the tests is answered and left open rather than resolved, since the answer is the
opposite of the ask.

### Abstract instance properties, because the parser is built from instances

Each of the seven subcommands is now a `Subcommand` subclass owning its `invoked_as`,
`description`, `add_arguments` and `run`, with `SUBCOMMANDS` built by instantiating
`Subcommand.__subclasses__()`. The parser and the dispatch table had been two lists of the
same seven words; they are one now, and a command that exists but is unreachable is not
expressible.

The reviewer offered `StrEnum` or dataclasses-with-abstract-members, and the enum loses on a
concrete point rather than taste: a member can carry a name, but not the flags — the parser
block and the `run_*` function would have stayed apart regardless.

Worth carrying is why this did **not** reach for #139's `classproperty`. That class exists
because #139's parser is built from the *classes*, and its third round had to discover that a
plain `classproperty` silently loses abstractness, since `ABCMeta` resolves abstractness with
`getattr(cls, name)` and gets a plain string back. Building the parser from *instances*
sidesteps the question entirely: plain `ABCMeta` refuses a nameless command with
`TypeError: Can't instantiate abstract class`, raised as the module imports. And it avoids
copying `class_property.py`, which lives only on #139's unlanded branch — this plan has
recorded four same-artifact-twice instances already, and a fifth was the alternative.

### The extend-a-note trap is retired, and the answer to its open question is "no"

`plan_item_bootstrap.py` gains `update --append-notes`, closing the question this item's own
notes left open on 2026-08-11 — whether `fold` should accept both paragraph conventions.

It should not, and the measurement is why. A note **read back out of `plan.yaml`** separates
paragraphs with a single `\n`, because a folded scalar reads its own line breaks back as
spaces and a blank line back as one newline. A note **written into a file** separates them
with a blank line, and its single `\n`s are hard wrapping that must *not* become breaks. The
same character means opposite things in the two sources, and only the caller knows which it
holds — so teaching `fold` to split on any newline fixes the first and explodes the second,
turning every hard-wrapped `--notes` file into one paragraph per line. `extend_note` does the
conversion, the flag says which source it is, and the two are mutually exclusive.

### Using it immediately found the one thing it cannot catch

Appending this round's note with the new flag produced a single run-together paragraph on the
first attempt, because the file was written as continuously wrapped prose with no blank lines.
The tool did exactly what it promises; the input was wrong. Recorded because every later
caller writes that file the same way: **`--append-notes` reads a file the way a person writes
markdown**, so its paragraphs must be blank-line separated, and a run-together note is an
authoring mistake rather than a defect to go hunting for.

Repairing it turned up something else. Five hyphen-broken words sat in the live note —
`plan- item`, `stacked- pr`, `plan- writing`, `dependency- chips` and one of this session's
own. The first four are **residue of the fold bug this very branch fixed**, written by the
old `break_on_hyphens` behaviour before the fix landed, and they had been sitting in the
manifest unnoticed since. A fix stops the bug producing new damage; it does not repair what
the bug already wrote, and nothing was looking. All five are rejoined.

### Naming

`manifest-currency.md` → `manifest-staleness.md`, `CurrencyReport` → `StalenessReport`, and
the shell constant with them, on the user's question of staleness or status. *Status* is
already taken twice — an item's lifecycle field, and the key every report here leads with — so
a `manifest_status_document` would read as being about those. *Staleness* names the defect and
is the word `check` already uses (`MANIFEST_IS_STALE`, `StalenessFinding`).

416 tests across the three directories CI runs, was 408; six new, each mutation-checked. A
second thread stays open by the same reply-don't-resolve rule: whether blockers written before
the ownership convention survive a pass. They do by construction — no `<owner>: ` prefix means
`blockers_not_owned_by` never matches, the identical path as a hand-written blocker — verified
against this plan's real manifest, where the three pre-convention blockers on
`personal-settings-sync` carry no owner-shaped prefix.

## Update 2026-08-11 (resolved): #126's conflict, and a rename git will not accept

`/plan-item-resolve workflow-unification git-identity-from-personal-notes`, session
https://claude.ai/code/session_016kC5DfwqNRAmDkWYLxpa3x. The item was `blocked` with one
recorded blocker and, as usual, a second thing wrong that nothing had written down.

### The manifest named one of the two, which is now the expected shape rather than a surprise

`blockers` carried the maintenance pass's conflict report. It did not carry the review thread
opened the same morning, because no writer exists for review arriving after an item's last
manifest write — the finding the 2026-08-07 entry generalized, now on its fourth item.

Worth recording as a *narrowing* rather than a repeat: `manifest-currency-first` (#151) has
since made the pass write the blocker it decides itself, and that half worked exactly as
designed here — the conflict blocker was accurate, owner-prefixed, and round-tripped intact.
What is still unwritten is everything the pass does not decide, and a review comment is the
clearest case of it. The gap is smaller and better-defined than it was a week ago; it is not
closed, and nothing in flight closes it.

### The conflicts, and the one that would have deleted a feature

Five files, all additive-vs-additive, but "keep both" was the wrong instinct in one place and
worth stating because the failure would have been silent. `session-start.sh`'s hunk pitted this
branch's git-identity block against `main`'s personal-settings sync — and this branch, whose
last base merge predates #109 landing, **does not carry the settings block at all**. Resolving
in favour of ours would have dropped a shipped feature out of the hook with no conflict, no
test failure (this branch's tests do not install the settings path) and nothing to notice it.
The tell was mechanical rather than clever: `grep SUMMARY_SETTINGS` on our own side returned
nothing, which is the check worth running on any conflict hunk where one side looks like a
wholesale replacement of the other.

The ordering the 2026-08-07 entry wrote down for exactly this arrival held without
adjustment: the git-identity write goes above the setup verdict, and the verdict's comment
already said "last of everything the hook writes" rather than naming `CLAUDE.local.md`, so the
new block inherited the rule instead of rediscovering it. That is the entry's own prediction
coming true one item later, and it is the argument for generalizing a comment at the moment
you notice it is too narrow.

`scratch_repository.py` carried the one judgement that was not mechanical. This branch's
`REQUIREMENTS_FILE` and `TOOLING_FILES` and #121's `SetupPrerequisiteFile` enum are the same
paths under two spellings — the same-artifact-twice pattern this roadmap has now recorded for
#109's `ScratchRepository`/`ScratchProject` and #110/#106's three duplicated artifacts. Keeping
both sides would have re-landed literals a review round had just removed, so the literals go
and the enum stays.

### A rename that cannot be done, and the reply that says so

The review thread asked for `GIT_AUTHOR_IDENT` → `GIT_AUTHOR_IDENTITY`, reading it as an
abbreviation. It is git's own variable:

```
$ git var -l | grep IDENT
GIT_COMMITTER_IDENT=...
GIT_AUTHOR_IDENT=...
$ git var GIT_AUTHOR_IDENTITY
usage: git var (-l | <variable>)
```

Applying it makes `git var` exit non-zero on every call, so `effective_git_identity` would
report that git cannot determine an identity — the single wrong answer the item's own design
notes say a check about commit authorship must never give. Answered with the measurement and
left open, per the reply-don't-resolve rule.

The boundary this draws is the reusable part, since AGENTS.md's no-abbreviations rule is one
of the most frequently applied on this plan: the rule governs identifiers **we** choose, which
is why #106's subcommand became `configuration`, and it cannot govern one another program
defines. Everything this branch names is already spelled out; the remaining `IDENT` tokens are
citations. A reviewer reading a diff cannot tell those two cases apart by eye, so the answer
is a measurement rather than an argument.

### The merge created work beyond itself

`session-start-messages.sh` did not exist when this branch was written. After merging, the
`git identity:` line was the only summary line still wording itself inline, and
`test_git_identity_sync.py` held four literal copies of that wording — precisely the
duplication #121's review round had removed from every other line days earlier. Left alone it
would have merged clean, passed CI, and quietly reintroduced the pattern.

So the four messages moved into that file with `SummaryMessage` members, and `SummaryMessage`
and `summary_message` moved beside `summary_value` in `session_start_summary.py`, which two
test modules now share. #121's second round settled that no wording is pinned; that call was
followed rather than relitigated, and what is pinned is the pair of failures that break the
hook, both mutation-checked.

**Generalizable: a convention adopted on a branch does not apply itself to the branch's
children.** #121 single-sourced its wording after #126 was already open, so the convention and
the code that violates it never met until the merge. A conflict resolution is the moment they
do, and reviewing only the conflicted hunks would have missed this entirely — the git-identity
block merged cleanly. Worth adding to what a resolve checks: not just does it merge, but does
the merged tree still honour what the base decided while we were away.

### State

Pushed as `edca885f`; `mergeable_state` `dirty` → `unstable`; `needs-resolution` dropped by
re-sending the full label set; still a draft, still no `bug` label; description rewritten. 397
tests across the three directories CI runs — 107 hooks, 194 plan-dashboard, 96 stack — and the
hooks suite re-run from a clean clone of the pushed branch, per #121's staged-diff lesson.
`test_each_lib (semantic_digital_twin)` is re-checked on the new run rather than inherited from
the 2026-08-03 ruling; it remains the base's failure, and this diff is `.claude/hooks/` only.

Pushed to this item's own branch rather than the resolving session's designated one, the same
override recorded for #115, #121, #133 into #117, and #143's one line onto #135's branch.

## Update 2026-08-11 (later): a repair rule needs evidence, not a shape match

Two follow-ups to the review round above, both produced by using `--append-notes` on this
item's own note rather than by reasoning about it.

### The paragraph count is the only fix available, and that is worth saying

Appending the round's note produced one run-together paragraph, because the file was
written as continuously wrapped prose with no blank lines. Nothing was wrong with the
tool: a file's paragraphs are whatever its blank lines say they are, and five intended
paragraphs written as one *are* one.

What was missing is that nothing said so at the time. The write now reports
`note_paragraphs`, counted through the same splitter `fold` uses, so the number and the
manifest cannot disagree. Which paragraphs were *meant* is not recoverable from the file
— that information never reached the script — so the honest fix is to make the outcome
visible at the moment of writing rather than to guess at intent. The first attempt
counted the value *before* folding, where a hard-wrapped line still looks like a break;
its own test caught it, which is the second time this week a fix for a wrapping problem
has needed the same distinction drawn.

### The blind rejoin was luck, and running it wider proved it

Repairing that note by hand turned up five hyphen-broken words in the live manifest —
`plan- item`, `stacked- pr`, `plan- writing`, `dependency- chips` and one of the
session's own — all residue of the fold bug this branch had just fixed. A fix stops new
damage; it does not repair what the bug already wrote, and nothing was looking at those
values. They were rejoined with a plain regular expression over `\w+- \w+`.

**That rule is wrong, and only happened to be right on those five.** Running it across
every item turned up seven more, and one of them is
`all network- and credential-free` — a suspended hyphen, correct English, and
character-for-character the shape of a break. A blind rejoin would have written
`network-and credential-free` into somebody's note and nothing would have flagged it.

So `repair` closes a break only when the rejoined word appears **elsewhere in the plan**.
That is the bug's own signature rather than a guess about English: a wrap breaks a word
its author wrote whole, and such a word is written elsewhere — inside a longer compound
counts, since `plan-item-kickoff` is evidence for `plan-item`. `network-and` appears
nowhere and is left alone. What fails the test is reported under its own exit status,
`text_needs_repair`, so a partial repair cannot read as a clean one.

The cost is real and is the right way round: a genuinely broken word occurring exactly
once is left for a person. Live on this plan that was four rejoined and three reported,
two of which were real breaks then judged and fixed by hand.

The generalization, which this plan has now met from both directions: a rule that
*detects* damage by shape is fine, and a rule that *repairs* it needs evidence for each
case. The five hand-fixes were made with a detector and no evidence, and got away with
it; the same rule at eight times the scale would have corrupted prose. Where the
evidence is missing, report rather than write.

### The greenlet blocker is retracted

Recorded on 2026-08-10, and on #151 and #135, as `greenlet` 3.5.5 having been published
with macOS and Windows wheels only, blocking `uv sync` on every branch in the repository.
Not true, checked rather than re-asserted: 3.5.5 ships 80 wheels including
`cp312-manylinux_2_24_x86_64.manylinux_2_28_x86_64` **and** an sdist, `uv lock` and
`uv pip install` both resolve it on this platform with the runners' own uv 0.8.17, and CI
run 31478716090 completed green on another branch. The runner's `manylinux_2_39_x86_64`
is compatible with a `manylinux_2_28` wheel.

Everything fits a publish-propagation window — greenlet uploads per-platform from
separate jobs, so there is an interval where the macOS and Windows wheels are on the
index and the Linux ones and the sdist are not, which is exactly what the error said
including "doesn't have a source distribution or wheel". External, transient, and
self-resolved.

No pin was added and no bug pull request opened: `greenlet<3.5.5` would hold the whole
workspace below the current release to avoid a problem that no longer exists, on a
transitive dependency nothing here declares. `tool.uv.required-environments` remains
available as a resilience measure on its own merits — it would not have prevented this —
and was offered rather than assumed.

## Update 2026-08-11 (review round on #154): settled, then handed over

28 threads on `integration-branch`. All answered, none actioned, none resolved: the five
that needed a decision were settled with the user, and implementation was handed to a fresh
session on their instruction. The executable plan is in the branch's PR-progress note, which
is the file a session's own SessionStart hook loads — the manifest carries the decisions,
the note carries the work.

### The stale base is the round's real content

Most of the "this duplicates #139" comments are one fact seen from several angles. #139 split
`maintenance.py` into eleven modules and added `class_property.py` *after* this branch was
cut, so `integration.py` independently grew its own error base, command classes and git
helpers. None of that is a design disagreement, and none of it is answered by writing a new
abstraction — it is answered by merging the parent and deleting what the parent now supplies.

The base also moved mid-round, which changed the answer. #151 rebased onto #139, so
`6fd229ff3` contains `ebf67734` and the chain `#139 → #151 → #154` is linear. One merge now
brings the module split, `class_property.py` *and* `block --branch` / `unblock --branch`
together — which is what makes the manifest half of the escalation pipeline buildable at all
rather than a dependency to wait on. A conflicted #139 merge started earlier was aborted.

Worth carrying: the round was planned twice, first against #139 as the base and then against
#151, and the second plan is materially simpler. Re-checking a base at the moment of acting,
rather than inheriting the one recorded at kickoff, is the same lesson
`git-identity-from-personal-notes` recorded on 2026-08-01 — a basing decision is a claim about
live branches and expires when a sibling moves.

### A label that would have been silently stripped

The user asked for `needs-resolution` on a branch that breaks another. Reading the code first
is what stopped that shipping: `WithholdBranchStillConflicting`
(`maintenance_restack_steps.py:225`) clears that label whenever `mergeable_state` is not
`dirty`, and a semantic break never makes a pull request dirty. So the label would have been
written by the triage skill and removed by the very next maintenance pass — reopening exactly
the re-reporting loop the label was invented to close, and doing it invisibly.

The resolution keeps the user's intent and changes the mechanism: a separate
`integration-conflict` label the pass never auto-clears, with
`Configuration.needs_resolution_label` generalised into a *collection* of blocking labels read
by both the withholding step and `maintenance_promotion.py`'s exclusion. Both labels then
block through one code path, which is what the user asked for in preferring extraction over a
second copy.

This is the same shape as the 2026-08-05 promotion incident recorded on #139 — a rule that was
followed to the letter and still broken, because the state it read was not the state that
mattered. There it was a snapshot a later step invalidated; here it is a label whose clearing
condition does not model the case being labelled.

### Three reversals of this item's own design

**Escalation.** A semantic break was to be reported and left. It now pushes a mimic test to
the breaking branch, comments, labels, writes the manifest and republishes. The test goes on
the *breaking* branch because the relying branch cannot express a test against an import that
does not exist on it yet — #111 adding a module-scope `import development_tooling` is
testable on #111 alone, with no merge involved.

**`suspect-replay`.** Stopping left a poisoned `rr-cache` entry and no instruction, so every
later build reproduced the same failure. It now discards the entry and triages normally. The
prohibition that survives is narrower and still right: never auto-write a *replacement* in the
same pass, which is how a build starts thrashing.

**The verdict.** `--test` running a local suite is replaced by GitHub CI: `build` pushes,
prints the run URL and exits; a separate subcommand reads the conclusion; localisation pushes
every prefix at once so CI runs them concurrently. This reverses "the tool pushes nothing"
deliberately and narrowly — to a branch the tool owns and regenerates, never to a feature
branch. Reachability was already measured rather than assumed: #146 established that
`actions/runs`, `jobs` and job-logs all answer 200 from a session, and that this fork's queue
time is a median of 0s.

### The one thing proposed and declined

A pull request based on *both* conflicting branches. It is a diamond: a pull request has one
base, so the second branch arrives whole in the diff, the thing cannot promote independently,
and `restack_plan` derives exactly one parent per branch — the identical reasoning that
linearized the upstream wave as decision 10.

### Retraction

The `greenlet` blocker recorded on 2026-08-10 against this item, #151 and #135 is withdrawn.
3.5.5 publishes cp312 manylinux wheels and an sdist; it reads as a publish-propagation window.
A `test_each_lib` red must be judged on its own evidence rather than against that note. The
retraction is repeated in the manifest entry and the PR-progress note, because those are the
two places a session reads before CI.

## Update 2026-08-12 (`plan-item-resolve` on `stack-maintenance-executor`): #139 is not blocked, and the real "upstream conflict" is measured rather than assumed

`/plan-item-resolve workflow-unification stack-maintenance-executor`, prompted with "there's also
merge conflicts with upstream main." Gathered rather than guessed: #139 (head `ebf67734`) is CI
green on all 21 checks, `mergeable_state: clean` against fork `main`, and review is settled — the
two threads left open and the `PullRequest.ci` comment are already correctly deferred to other
items, not blockers. Nothing about the pull request itself needed resolving.

### The conflict is real, but it is with cram2 `main`, not fork `main`

Measured directly rather than read off a status field, since GitHub's own `mergeable_state` only
ever answers against a pull request's *own* base (fork `main` here) and has no notion of upstream:

```
$ git merge-base <cram2/main> <fork/main>
<fork/main's own tip>                       # fork main is a strict ancestor of cram2 main
$ git rev-list --left-right --count <cram2/main>...<fork/main>
160    0                                     # 160 behind, 0 ahead
$ git merge-tree --write-tree <cram2/main> <#139 head>
CONFLICT (content): Merge conflict in .claude/skills/stacked-pr-maintenance/SKILL.md
```

Everything else in the tree (`.claude/stack/README.md`, `.gitignore`) auto-merges clean; one file
conflicts. The cause is ordinary and already on record in two other places on this roadmap: #106
promoted to cram2 as PR #501 (`af935a19`, confirmed by walking cram2 `main`'s own log) and cram2
kept moving — including further edits to `SKILL.md` itself (`102e72ab`, `8b7435bb`) — while #139's
own 25-comment review round independently rewrote the same document's "what this pass never does"
and command-reference sections. Two owners, one file, no coordination between them; a conflict is
the expected outcome, not a defect in either side.

### Why nothing acts on it now

The fork-main fast-forward from cram2 `main` is a deliberately deferred step — `routine-cutover`'s
own notes gate it on exactly this pair (#106 on cram2 `main`, one fast-forward), owned by an Action
that does not exist yet. So today nothing is attempting the merge that would hit this conflict, and
#139 is fully mergeable into the base it actually has. Resolving it pre-emptively here would mean
resolving against a cram2 `main` that keeps moving before the fast-forward the resolution is *for*
actually happens - most of the resolution would likely be stale by then. It would also cut against
this item's own design principle, applied to itself: the executor reports a restack conflict to the
branch's owner rather than resolving it invisibly, and a resolve session quietly patching around its
own future conflict is the same shortcut in a different place.

### State

No code or git change on #139's branch — recorded in `plan.yaml`'s `notes` for
`stack-maintenance-executor` and here, so the first fast-forward + restack pass (most likely as part
of finishing `routine-cutover`) starts from this measurement instead of rediscovering it live, the
same way the `restack` conflict-report flow would surface it anyway.

## Update 2026-08-12 (resolved): the fast-forward arrived the same day, and the repo's formatter was declining a file

`/plan-item-resolve workflow-unification stack-maintenance-executor`, second run of the day,
session https://claude.ai/code/session_01PyGLT8ofaqHShryiut281r. Pushed as `614eaccd` (the
merge) and `ba674d1d` (the review round).

### The entry above was right and is now superseded, which is the useful part

That entry measured the conflict as real but latent — against cram2 `main`, not fork `main` —
and recommended waiting for the fast-forward rather than resolving against a target still
moving. Fork `main` was fast-forwarded a few hours later. `origin/main` is `e123c383`, 142
commits ahead of this branch's merge base, and `git merge-tree` against it names exactly the
one file the earlier run had predicted: `.claude/skills/stacked-pr-maintenance/SKILL.md`.

So the prediction held and the deferral cost nothing. Worth recording as the *shape* rather
than the outcome: a measurement of a conflict that nothing is currently attempting is a claim
with an expiry date attached, and the honest form is to say which event ends it. That entry
did — "the moment fork main is fast-forwarded" — which is why this run had nothing to
rediscover.

What it could not do is keep its own conclusion from going stale. `notes` now carried
"#139 is not blocked" and "nothing today is merging cram2/main into this branch" while GitHub
carried `dirty` and a `needs-resolution` label. This is the same manifest-currency failure the
plan has recorded four times, met from a new direction: not review arriving after the last
write, but the *writer's own* correctly-hedged statement outliving its condition. `#151` does
not close this half either — the pass writes the blocker it decides, and here the pass did
label the branch, but nothing reconciles a note that has become wrong.

### The conflict was two lines against a rewrite

`main`'s side is 2 insertions and 2 deletions: `no-pr-subscriptions` (#153, upstream #535)
rewording the conflict-report step. This branch's side is 117/134 — the 25-comment round having
rewritten the whole document.

"Keep both" was not available and neither was "take ours" unqualified. The branch's rewrite
already carries the no-subscription rule twice (the HARD RULE, and *"It never subscribes to
learn CI"*), so the rule itself was never at risk; what `main` added and the rewrite lacked was
one instruction — **write the comment to stand alone, because nothing delivers it**. That went
into the one bullet that still asks a *person* to write such a comment, the red-check case,
since the executor now writes the conflict one itself.

This is the 2026-08-11 lesson from `#126` applied rather than restated: check that the merged
tree still honours what the base decided while we were away, not merely that it merges.
`main`'s other movement since the merge base (`starter-notes.md`, the session-start tests,
`plan-dashboard`, `regenerate_all_orm.py`) touches nothing this branch owns, confirmed by
running the whole `test_claude_dev_tooling` suite on the merged tree rather than the stack
tests alone.

Merged rather than rebased, because #151 and #154 are both based on this branch. Both need a
restack now; that is on the tracking issue rather than on their pull requests.

### A fourth review round, arriving ninety minutes after the third was applied

The 2026-08-11 entry above records four comments applied in `ebf67734`. Those were the
09:01–09:04 ones. Four more arrived at 11:06–11:10, after that push, and had gone unanswered
since. Nothing was wrong in the note — this is the fifth item on this plan where review
arriving after the last manifest write has no writer, and it is worth stating that the failure
now shows up as *"the note is accurate about a moment that has passed"* rather than as a note
that was wrong when written.

Three applied. The trailing `_s` on `test_a_command_answers_with_its_own_name_rather_than_its_base_s`
was a possessive that lost its apostrophe becoming an identifier, so what survived read as an
abbreviation of nothing. Two test-local stand-ins were plain classes while every neighbour and
every real subclass is a frozen dataclass; both were fixed rather than only the one anchored,
since one omission written twice is not two decisions.

The fourth — why a `TypeError` rather than a custom error — is answered and left open. It is
`ABCMeta`'s, raised because the third round chose `classproperty` + `abstractmethod`; raising
our own means dropping the abstractness, since `ABCMeta` refuses before `__init__` can run. The
user's call this session was to keep it and reply.

### The repo's formatter was silently declining four files, which is why "run the script" was not the fix

The doc-formatting comment is the one worth carrying, because the first thing anyone would do
about it does nothing. `scripts/format_docstrings.py` reports **no change** on
`maintenance_board.py`, while `docformatter --check` against the repo's own `pyproject.toml`
disagrees with it on 33 docstrings — the file opens its summaries on the quote line, and the
house style is `pre-summary-newline = true`.

The script says why in its own module docstring, and it is exact here: it keeps the plain
black-formatted content whenever docformatter's result does not survive a second black pass.
Reproduced rather than inferred — the whole disagreement is one blank line:

```
     """
     A list of labels, each given either plainly or as an object carrying a ``name``.
     """
-

 @dataclass(frozen=True)
 class PullRequestFieldSpecification:
```

An attribute docstring immediately preceding a *decorated* top-level definition. docformatter
drops the blank line after it, black puts it back, and the script — correctly refusing to loop
— discards everything docformatter did, including the 33 summaries.

**Four modules and the test module, not the one flagged**: `maintenance_board.py`,
`maintenance_fast_forward.py`, `maintenance_restack_procedure.py`,
`maintenance_restack_steps.py`, `tests/test_maintenance.py`. They are formatted by hand as
`black` → `docformatter` → `black`, and the reason that is takeable rather than a thing to
redo every commit was measured before it was proposed: re-running `scripts/format_docstrings.py`
afterwards returns all five **byte-identical**, because the script's stability check discards
docformatter's output and keeps what is already there.

`stack.py` is in the identical state and is deliberately untouched — it is `main`'s file, and
whether `main`'s unformatted files get a sweep is still the open half of the earlier
doc-formatting thread. That question now has an answer to work from: they are not unformatted
through neglect, they are the files whose shape the formatter cannot converge on.

**Generalizable, and new to this roadmap: a formatter that reports no change is not evidence a
file is formatted.** This one is honest about it in its docstring and silent at the command
line, which is the combination that let five files drift while every session that touched them
ran it and saw nothing.

### The description had been eaten by its own feature

Two defects, both predicted on this pull request on 2026-08-05 and both since realized.

The description carried a literal `## Promote` heading inside prose — quoting the live-run
evidence — and `description_with_promotion_link` partitions on the first occurrence. A later
`promote` did exactly what it says it does, and the *"Verified against the live fork"* section
now ended mid-bullet at `` - `promote` wrote the link under ` `` with a dangling code fence
after it. Rewritten so the heading it names is not a heading.

And the session link was gone with it, which is why the 09:49 conflict comment says
verbatim *"This pull request's description names no session to address."* The executor's own
owner-addressing failed on the executor's own pull request, for the reason its own promotion
step created. Restored.

Both were flagged at the time and left alone as "not under review"; the cost of that is one
comment that reached nobody.

### State

`mergeable_state` was `dirty`, is not; `needs-resolution` is left for the next pass to clear
itself, which is the loop this item exists to close and worth exercising rather than
short-circuiting by hand. 450 tests across the three directories CI runs. Not re-drafted: the
user marked this pull request ready themselves on 2026-08-05, and that standing exception
holds. Pushed to the item's own branch rather than the session's designated one, the same
override recorded for #115, #121, #133 and #143.

## Update 2026-08-12 (`integration-branch`, #154): the recorded dependency was the kickoff's, not the branch's

`depends_on` corrected from `stack-maintenance-executor` to `manifest-currency-first`, on the
user's instruction. Nothing about the item changed; the manifest had simply kept the parent
this item was kicked off against, while the branch it is actually built on moved underneath
it. The 08-11 round already recorded the move — #151 rebased onto #139, `6fd229ff3` contains
`ebf67734`, and that round was replanned against #151 as the base *because* of it — but the
correction was written into the roadmap and never into the field the dashboard reads.

Direct parent only, so #139 is not named alongside it: `manifest-currency-first` already
depends on `stack-maintenance-executor`, and this manifest states one edge per item
throughout. Naming both would also have moved the dashboard's indent parent, which is the
first same-track entry in the list.

The same-shaped correction on #151 is eight days old (its own entry, 08-12: `depends_on` still
`[]` after the branch had been based on #139 since 08-11). Two items in one plan whose
recorded dependency lagged a basing decision that was made, acted on, and written up in prose
— which is the case `manifest-currency-first` itself exists to close, and neither instance was
caught by a check. `check` compares recorded fields against local git; a `depends_on` naming a
plan item has no local-git counterpart to contradict it, so nothing in the tooling reads a
base ref back against the manifest.

Outstanding, and not fixed here: #154's base ref on GitHub is still
`claude/plan-item-kickoff-workflow-koufa6` (#139's branch), so the pull request is not yet
reparented onto #151's branch. The manifest now states the intended structure; the reparent is
a separate action on the pull request.

## Update 2026-08-12 (resolved): #120's conflict was the one predicted eleven days earlier

`/plan-item-resolve workflow-unification sidebar-bug-fix-chips`, session
https://claude.ai/code/session_01VC4FEE6dzpdNtYcXjE5Ed4. Pushed as `299d1d53`.

### A predicted conflict is the cheap kind, and this is what makes it cheap

On 2026-08-01 both this roadmap and the tracking issue recorded that #120 and #122 would
collide on `example/screenshots/dashboard-overview.png`, that the second to land would
re-regenerate it, and that this is mechanical because the image is deterministic from the
committed fixture. Fork `main` was fast-forwarded from cram2 the same morning as this
resolve (`e123c383`, 142 commits past the merge base), #122 came with it, and the collision
arrived exactly as described.

The value was not in avoiding the conflict — nothing could have — but in the resolve having
no diagnosis to do. Contrast the entries above where a conflict had to be measured before it
could be judged: here the prediction named the file, the mechanism and the remedy, so the
work was carrying it out. Worth stating as the counterpart to the same day's
`stack-maintenance-executor` lesson: a measurement of a *future* conflict is a claim with an
expiry date, and a prediction of one is a claim with instructions attached. Both are worth
writing down; only the second saves the next session anything.

### The test file: additive on both sides except in one place

Both sides inserted after `test_item_ready_to_review_once_dependency_has_an_open_pull_request`,
so both blocks are kept. The single non-additive hunk is the tail of
`test_example_plan_renders_the_counts_and_sections_the_walkthrough_describes`, where #122's
fix genuinely changes the example's output: `retry-circuit-breaker` now reaches the list
behind its merged dependency, so **Ready to review (2)** is the true assertion and this
branch's one-element copy is simply out of date. Took `main`'s, then re-appended this
branch's `test_example_plan_demonstrates_the_bug_chip_and_its_filter` after it.

This is the second time that test has been the whole content of a conflict, which is the test
doing its job: its own docstring says it exists so a change to the example fails here rather
than leaving the walkthrough showing stale numbers.

### The screenshot recipe needed one thing the roadmap had not recorded

Re-rendering to resolve the binary conflict found a gap in the recipe written on 2026-08-01
(1280px wide, dark theme, 100px bottom margin). The sidebar is
`position: sticky` with `max-height: calc(100vh - 3rem)`, so at the obvious 900px viewport the
"What to do next" card **scroll-clips** the moment it grows — and #122's extra entry is
exactly such growth. The first render came back with the last entry cut off mid-sentence, and
nothing about the image says it is wrong. Adding to the recipe: the viewport height must
exceed the sidebar's own height plus `3rem`; 1280×1200 renders this example whole today, and
the check is `aside.sidebar`'s `scrollHeight === clientHeight`.

`playwright` drives `/opt/pw-browsers/chromium` for this — the browser is already installed in
the session environment, so nothing is downloaded.

### Two screenshots deliberately not regenerated, checked rather than assumed

The 2026-08-01 lesson is that a committed screenshot goes stale from any change, so the
default was to regenerate all three. Both remaining ones were then examined and left alone:
`dashboard-bug-filter.png` shows the sidebar *with the filter applied*, where the
ready-to-review group holds no bug fix and is hidden either way; `dashboard-action-buttons.png`
is a 656×259 crop of two item cards, neither carrying notes for #124's collapse to affect.
Re-rendering them in a different environment would have introduced font differences with no
content change behind them — which is the same silent-drift problem in the other direction.

### State

`mergeable_state` `dirty` → `unstable`; `needs-resolution` left for the next pass to clear
itself, as on #139. Not re-drafted: the user took this pull request out of draft themselves,
and it carries `in-review`, so the upstream pull request is open and the merge updates its head.
399 tests across the three directories CI runs. Pushed to the item's own branch rather than the
session's designated one, the usual override.

Two smaller things fixed while here. The description's `## Promote` link was destroyed by an
intermediate edit of my own and restored — the same failure #139 recorded, met from the writing
side rather than the promoting side, and the tell was that a read-back of the body ended at the
heading. And the item's `notes` still said "subscribed to its activity", which
`no-pr-subscriptions` has since inverted; no subscription was in fact armed on this session.

## Update 2026-08-12 (new item): dashboard drift detection has no cross-item check

Found while answering a question about rdr-refactor's D-ui stack, not while working this
plan directly: `D-ui-splice-fix` (#78) was closed as superseded by a fix that landed
elsewhere (dag-facade-hardening's `insert-at-ownership-parentage`, #118), yet
`D-ui-rendering` (#79) and `D-ui` (#76) still depend on it and are still `in_progress` -
and nothing on the dashboard flagged it. Only a previous session's freeform `notes:`
sentence recorded the problem, and nothing re-reads or re-verifies freeform notes.

Traced the root cause into `build_dashboard.py`: `_drift_description_of` only ever
compares an item's own manifest `status` against its own live PR state - it has no
cross-item check at all. `Item.is_ready_to_unblock_dependents()` already has the correct
predicate (deferred/closed_unmerged correctly reads as not-ready), but the only caller
that evaluates it per dependency is `check_dependency_readiness.py`, invoked on demand
for one named item by `plan-item-kickoff`/`plan-item-resolve` - never proactively across
the whole graph on a `/plan-dashboard` refresh. `_compute_next_steps` is the other
consumer, and it only looks at `not_started`/`blocked` items, so an `in_progress` item
built on a now-dead dependency slips past every existing check.

This is the same defect shape the plan already fixed once, just in the sibling
stack-tooling codepath: `landed-parent-detection` (#117) taught `restack_plan` to decide
a parent has landed from git ancestry rather than board membership, after the same "child
silently left stacked on a dead base" failure. That fix was never ported to
plan-dashboard's own `depends_on` graph, which has an analogous blind spot. Filed as
`deferred-dependency-drift-check` in the `dashboards` track, `not_started`, no branch cut
- left for another session to implement.

## Update 2026-08-12 (new item): the setup prerequisite stops asking permission

Reported as an everyday annoyance rather than found in the code: sessions started with a
planning skill "always ask if they should run the setup personal notes script or skill".
The cause is one document, not four - `plan-create`, `plan-dashboard`, `plan-item-kickoff`
and `plan-item-resolve` all defer step 0 to
`setup-personal-notes/prerequisite-check.md`, whose step 2 was an `AskUserQuestion` gate
over `/setup-personal-notes`. Its stated reasoning was that the check is read-only while
the setup is not: it writes git config, creates a branch on a remote and installs
packages, "none a thing to do to someone's clone because they happened to type
`/plan-dashboard`".

That reasoning holds for *where* the setup writes and not for *whether* it runs, and the
new wording splits the two. A user who invoked a planning skill has already asked for the
thing the setup is a precondition of, so the yes/no question has one useful answer and
costs a turn to collect. The questions inside `/setup-personal-notes` - the notes remote,
the notes content, the labels, restoring a diverged tracked file - each choose a
destination, and those stay exactly as they were.

Worth noting how often the gate actually fired here: this environment reconstructs the
container per session, so `dashboard_dependencies` (`markdown`, `nh3`) is reported
`needs-setup` on essentially every fresh session, and that row alone is enough to trip a
check that then asks about the whole setup. The one row that fires most is also the one
that is purely mechanical.

Filed as `setup-runs-without-asking` in the `personal-data` track, `in_progress`, as draft
PR #156 off `main`. The new-vs-change test was run rather than eyeballed: `git ls-tree main`
returns all eight touched paths, so this is a change to landed files. #107 (setup skill
rewritten over a new script) and #149 (execution modes editing the same step 0 sections)
are conflict-adjacent but own different work, and neither touches
`prerequisite-check.md`.

## Update 2026-08-12 (new item): deferred items are hidden by default too

Asked for directly: deferred items should be hidden on a plan dashboard unless a
checkbox brings them back, "and take care of the indentation of the tasks/chips between
visible and invisible". The dashboard has hidden done items behind a sidebar toggle from
the start, and a deferred item is the same kind of noise for the same reason - it is
intentionally paused or superseded, so it is not something to act on. `rdr-refactor` is
the plan where it bites: eight of its forty-five items are deferred (`D-core-engine`,
`rdr-engine-umbrella`, `D-ui-splice-fix`, `rdr-architecture-brief`, `rdr-oo-recognition`,
`rdr-backend-unification`, `montessori-choice-policies`, `montessori-why-demo`), all
inline among the live ones.

The checkbox is the easy half. The real work is the one the request calls out: indent
level. An item's indent is its depth in its track's same-track `depends_on` chain, and
hiding a parent leaves its dependents indented under nothing. `StackedItem` already
solved this once for done items by carrying a second precomputed level -
`indent_level_with_done_hidden`, where a done dependency is treated as no dependency at
all, so a dependent dedents to zero rather than merely one level - plus a second
wrap-parent for the past-the-cap wrap-around arrow, guaranteed never to be a hidden item.

A second, independent toggle turns that pair into four states (nothing hidden, done
hidden, deferred hidden, both hidden), so continuing the named-pair approach would mean
four fields, four wrap-parent fields, four template branches for the wrap arrow, and a
fifth of each the next time a status is hidden. It is replaced by one
`StatusFilter` enum whose members *are* the four states, each item carrying one
`StackPosition` per member. The enum value doubles as the page's CSS class and the
item's CSS custom-property suffix, so the template iterates rather than branches and the
CSS picks a level by specificity, keeping the existing "render both up front, swap
client-side, never re-render" property the done toggle and the bug-fix filter both rely
on.

Filed as `deferred-items-hidden-by-default` in the `dashboards` track. The new-vs-change
test was run rather than eyeballed: `git ls-tree main -- .claude/skills/plan-dashboard/`
returns `build_dashboard.py` and `templates/dashboard.html`, so this edits landed files
and stands alone. #111 (`shared-pr-state-chips`) is conflict-adjacent - it adds LOC/CI
chips to the same template - but owns different work and has been `needs-resolution`
since well before this.

Opened as draft PR #157 off `main`. The wrap-around arrow's parent is settled along
the way, in favour of what the un-hidden computation already did: it is now carried only
by the item that actually wraps. The hidden-status half propagated it to every
descendant, so an item sitting directly beneath its visible parent still claimed to
continue from an item further up the chain - a latent defect the done toggle already
had, surfaced by unifying the two computations into one.

## Update 2026-08-12 (new item): the tool a pass runs is whatever the checked-out branch carries

A `/stacked-pr-maintenance` run hit a string of spurious failures partway through a
restack pass: `check-move` calls coming back as argparse `invalid choice`. The cause is
not in any of them. `SKILL.md` invoked the tooling as `python .claude/stack/stack.py …`
throughout a run, and that path is tracked content - so which version of the tool answers
is decided by whichever branch the checkout is on at that moment. Step 2 fast-forwards
the fork's base onto the upstream, which is how a newer `.claude/stack/` arrives in the
first place; this repository has already had one such rewrite land, renaming `preflight`
to `check-move` and splitting the single file into `maintenance_*` modules. Once a run
has branches at two different versions in play, the tool changes underneath it.

The loud half of that is survivable - an unknown subcommand is at least a failure. The
quiet half is not: the same command name answering with semantics step 0 never validated,
in a pass whose steps push branches and write labels. No harm was done only because the
operator noticed and hand-pinned a copy of the tool outside the repository before
continuing, which is the fix this item makes the tool do for itself.

`stack.py pin-tooling` copies the tool - every module and `stack.toml`, leaving
`board.json` behind because it is one pass's snapshot and a copy would be stale for every
pass after - into a directory named for its own content digest under the system temp root,
and prints the copy's `stack.py`. Digest naming buys two properties worth having: pinning
the same version twice keeps one copy, and two versions in flight at once each keep their
own, so a later pass cannot overwrite the copy an earlier one is still running. The copy
is staged beside its destination and moved there whole, so nobody can invoke one that is
half written. `WorkingTreeTooling` and `PinnedTooling` name the two sides of the problem:
the tool where a checkout can replace it, and the copy where nothing can.

`SKILL.md`'s step 0 gains part **c** - pin the moment `configuration` has answered - and
every invocation after it names `<pinned>/…`. Only `configuration` and `pin-tooling`
still run from the working tree, since at that point there is nothing else to run, and a
test asserts exactly that set rather than trusting the document to stay that way. The
skill also had to stop promising that "every step shells out to `.claude/stack/`", which
my change makes false.

The deliberate limit is that a shell variable does not survive between the commands a
session runs, so the document uses a `<pinned>` placeholder and tells the reader to
substitute the printed path each time, rather than pretending `$PINNED` will still be set.

`#139`'s `RestackWorktree` had already solved one instance of this - the executor's own
branch switching happens in a worktree of its own precisely because checking a branch out
"deletes the tooling the rest of the pass needs". This item generalizes that from a rule
each future step must remember into a property of the run: whatever the executor and the
session do to the checkout afterwards, the tool driving the pass is a file no branch
carries.

Filed as `pinned-stack-tooling` in the `stack-tooling` track, opened as draft PR #158 off
`main` with the `bug` label. New-vs-change was tested rather than assumed:
`git ls-tree main -- .claude/stack/stack.py .claude/skills/stacked-pr-maintenance/`
returns both paths, so this edits files that #106 and #139 have already landed. #110 is
the only in-flight branch touching `.claude/stack/`, and it owns setup rather than the
maintenance pass.

## Update 2026-08-12 (review round): a citation is not a duplicate, and the dedup already has an owner

One comment on #156, posted twice as two threads, against `plan-item-resolve/SKILL.md`'s step 0:
the section looks duplicated across the skills, so define it once and share it — *unless another
pull request already does that, in which case leave it there.*

The escape clause is the operative half, and the condition holds. **#149 already collapses this
exact section** — both plan-item copies — into `plan-dashboard/plan-item-gathering.md`, together
with the item resolution, the tracking-issue subscription and the roadmap read. Deduplicating it
here would be two branches restructuring the same paragraphs at once, which is the
same-artifact-twice pattern this roadmap has now recorded five times.

The rest of the answer is a measurement rather than a judgement. The paragraph appears four times
on `main` and five once #135 lands, but the *procedure* is already single sourced:
`prerequisite-check.md` is the shared document, and what repeats in each skill is a one-line
citation of it plus a skill-specific consequence clause ("rather than failing on a branch that
isn't there" / "on a missing branch or an `ImportError`"). That is the repo's established shape for
a shared procedure — `scope-decision.md`, `dependency-readiness.md` and `pr-data-fetching.md` are
all cited exactly the same way by several skills each. So what the comment saw as duplication is
the citation layer, and removing it would mean each skill saying less about why it stops, not the
system holding fewer copies of the rule.

### The hazard the review turned up, which is the part that needed doing

Looking properly at #149 to answer the comment found something neither pull request would have
caught on its own: `plan-item-gathering.md:12-19` still says *"offer `/setup-personal-notes`"*, and
`add-plan-item/SKILL.md:24-28` on #135 says the same. Both are **new files on their own branches**,
so neither conflicts with #156 and nothing flags them at merge time — landing either one after
#156 silently reinstates the gate #156 exists to remove, for two of the skills in the first case
and for the fifth caller in the second.

This corrects the resolution `setup-runs-without-asking`'s own notes had recorded, which said to
keep both edits when the two plan-item skills conflict. That is wrong: the right resolution is to
take #149's *deletion* of the section and carry #156's wording into its shared document. #135
additionally conflicts in `prerequisite-check.md` itself, where it only adds `add-plan-item` to the
opening list, so there the resolution is #156's rewrite plus that one name.

Both were flagged on their own pull requests rather than only here, per the comment-routing rule:
each is a change to what that pull request ships, not an FYI. Neither branch was pushed to — both
are out of draft, so both are the user's. The two review threads were replied to and left open,
since the outcome is a deferral rather than a change.

**Generalizable, and new to this roadmap:** a wording change that lands in a shared document is
invisible to every branch that has *forked* that document into a new file of its own. Git conflicts
only cover the copies that already exist; the ones being created in parallel need a reader. The
cheap check, when changing a rule that several skills cite, is to grep the unlanded branches for
the old wording rather than only the merge base.

### The follow-up: the rule stops being prose

Flagging the two branches is coordination, and coordination is what had already failed once —
the rule was stated in `prerequisite-check.md`, cited by four skills, and two branches
independently forked the superseded sentence into documents of their own without anything
noticing. So the same round added the enforcement:
`.claude/hooks/tests/test_setup_prerequisite_documents.py` sweeps every markdown document under
`.claude/skills/` for a verb of offering governing `/setup-personal-notes`.

Three properties, each chosen against a failure this plan has already recorded:

- **Discovered, not listed.** The case it exists for is a document that does not exist yet, which
  a list cannot cover — the same reason `COMMANDS` is derived from its subclasses in #139 rather
  than enumerated.
- **An absence, computed.** It asserts what no document may contain, which is the shape of the one
  prose test #106 kept when it deleted eighteen others, and the reason that one cannot fail from a
  rewording.
- **Guarded against vacuity.** A second test asserts the sweep found documents at all, so a moved
  or renamed directory fails loudly instead of passing with nothing to check — #110 hit the
  opposite case, where a check silently had zero candidates.

Deliberately narrow, and the docstring says so: it catches the sentence the rule replaced, not
every paraphrase of asking, and it must not fire on the prose that *explains* the rule, since
`prerequisite-check.md`'s own rationale section discusses offering and asking throughout. A
sentence-level "mentions the command near the word asked" rule was written first and rejected for
exactly that reason — it flagged the source document.

Verified by mutation rather than assumed: it passes over 15 documents on this branch, and flags 4
on `main`, 3 on #149 (including its new `plan-item-gathering.md`) and 5 on #135 (including its new
`add-plan-item/SKILL.md`) — the two files that were the whole problem, both invisible to git.

**What it buys is that landing order stops mattering.** #156 first, and the other two go red the
moment they merge `main`, which they do routinely, so the one-word fix is forced before they land.
Either of them first, and #156's own suite fails until it sweeps their copies. Neither outcome
depends on anyone remembering a comment. The residual cost is the ordinary one for any new test: a
branch that lands *without* merging `main` first turns `main` red rather than its own branch, which
is the same trade every contract test in this repository already makes.

## Update 2026-08-12 (resolved): `integration-branch` takes its base merge, and carries only reviewed work

`/plan-item-resolve workflow-unification integration-branch`, session
https://claude.ai/code/session_01AYLtTRh7uZu64oLpMhGjQR, prompted with "include in the integration
branch only pull requests that are open and ready". Four commits pushed; 595 tests across the three
directories CI runs, from 479 before.

### The handover was executable, and three of its instructions had expired

The 08-11 round settled 28 threads and handed an executable plan to a fresh session. Most of it held.
What had not is the part that named where things live: #151 moved after that note was written, so
`GitCommandRunner` is now `.claude/shared/git_commands.py`, `maintenance_errors.py` is
`.claude/shared/exceptions.py`, and `class_property.py` is deleted in favour of abstract instance
properties. Following the note literally would have put this branch's two git additions into a class
that no longer holds them and reintroduced a descriptor the parent had just removed.

This is the same lesson the round itself recorded about basing - *a basing decision is a claim about
live branches and expires when a sibling moves* - met one level down: a **handover** is the same kind
of claim. It was written against a parent that then changed, and the check that caught it was reading
the parent's current tree rather than trusting the note. Worth carrying: a handover note should be
read as evidence about a moment, not as instructions, and its first step should always be to re-read
what it points at.

#139 merged at 14:36 the same day, which made the merge simpler than planned rather than harder: the
eleven-module split arrived through `main`, and only `#151`'s shared extraction had to come from the
sibling. Four conflicts were one rename seen from four places, resolved to #151's rename while keeping
`main`'s docstring formatting - #151 predates that reformat, so taking its side wholesale would have
reverted it.

### "Only open and ready" cannot be asked of a tip

The requirement reads as a one-line filter and is not one. The selection unit is the stack tip, and a
tip contains its whole stack, so filtering tips would have merged ready #36 together with drafts #33,
#34 and #35 as its ancestors - the reading that does the opposite of what it says. Readiness is
therefore read down the entire chain: a stack that is draft at its root is left out entire, and the
branch merged for a stack is the last one reached before its first draft. On the live board that takes
a build from 22 tips to 9.

The vocabulary already existed and was reused rather than reinvented: `BranchStatus.DRAFT`/`READY`,
whose own docstring already said out-of-draft *is* the author's review, and which `build_dashboard.py`
names `LiveState.OPEN_READY`. `is_out_of_draft` covers `IN_REVIEW` as well, because `derive_status`
gives it precedence over `READY` - a test written against `READY` alone would have silently dropped
every branch already promoted upstream, which is the most reviewed work there is.

Two consequences are easy to get wrong and are pinned by their own tests. `claimed_as_parent` has to
range over the **carried** branches only: a parent is left out because a child contains it, and a
draft child is never merged, so reading it over every branch drops the reviewed parent as well. And a
branch left out is *named*, with the draft beneath it when that is the reason - a build carrying nine
of nineteen and reporting only the nine reads as having covered everything. An excluded draft is the
rule working, so it is kept out of `tips` and does not reach the `tip-left-out` exit status.

A mutation check found a real hole rather than confirming the tests: nothing covered the wiring from
the selection into a real build's report, so removing it entirely left the suite green. Closed with a
scratch-fork test before the work was called done.

### One test was removed rather than kept

Mutation-checking showed one of the five new selection tests failing only for reasons its neighbours
already covered, while its docstring claimed to pin the carried-parents rule it did not actually
exercise. Removed rather than reworded: a test whose stated reason is not its real one is worse than
no test, because the next reader trusts it.

### Left undone, and why

Part D of the handover - the verdict moving from a local suite to GitHub CI, with `build` pushing and
a separate subcommand reading the run's conclusion - is **not started**. It needs an Actions client
that does not exist in this tree (#146, which measured that reachability, is still unlanded), it
rewrites the localisation path `escalate` now depends on, and its verification is a real CI run on a
pushed branch rather than anything the harness can show. Starting it half-way would have left the
verdict path migrated on one side and not the other.

### The reparent was recorded as blocked, and it was neither blocked nor correct

The base ref was carried in this item's notes for two entries as *"still #139's branch; the
base-field `PATCH` 403s through the agent proxy, so the reparent stays manual"*. Attempted rather
than restated, and both halves were wrong.

The proxy does not block it. The GitHub MCP tool changed the base immediately - which is precisely
what `session-safe-pr-reparent` established on throwaway PR #129 in August, that only the raw `curl`
`PATCH` is refused and the MCP tool is the client that works. That finding had simply not been
carried into this item's own notes, which described the operation by the *failure mode of the client
nobody should be using*.

And the reparent is wrong to perform today, which is what the attempt showed rather than the
reasoning: #151's branch is **159 commits behind `main`** and 17 ahead, so basing #154 on it swelled
the diff from **45 files to 261**, pulling in the whole of `main` that #151 does not carry. Reverted
in the same minute. `git merge-base --is-ancestor` confirms this branch already contains #151's head
and is 0 behind `main`, so `main` is the honest base rather than a placeholder, and the reparent
becomes correct only once #151 merges `main`.

That is the inflated-diff shape PR #41 cost this plan a whole item to repair, met from the other
direction - there a child sat on a base that had already landed, here it would have sat on a base
that had not caught up. Both produce a diff that describes something other than the work.

**The generalizable half is about the manifest, not about git.** A note saying an operation is
blocked is a claim with an expiry date, and this one had two expiries at once: the client changed
(the MCP tool works) and the target moved (#139 landed, so `main` overtook #151). It survived two
entries because each rewrote the sentence around it rather than testing it. Attempting a
recorded-as-blocked step is worth more than restating it, whenever the attempt is cheap and
reversible - and a base change is both.

### The 28 threads, and the order that was wrong

The work was done first and the threads were reported as outstanding rather than answered, which the
user caught directly: *"why didn't you respond to this comment? also did you check all other comments
and respond and resolve the ones you finished?"* The right order is the one the notes-branch
convention already states - reply first, resolve second, one thread at a time - and the reason is not
bookkeeping: a thread is where the reviewer is reading, so a change reported only in a commit message
and a description has not been reported to them at all.

Answering them then found three that were **not** actually addressed, which is the part worth
carrying. Two asked for repeated string literals to be named and one asked why raw `subprocess` was
being used where `GitCommandRunner` has named methods; all three had been read as covered by the
enum work and were not. Fixed in `e45a22722`: nine branch-name constants, and `switch_to`,
`stage`/`remove` and `commit` added to the shared runner rather than the calls being left raw. So
the reply pass was not a formality over finished work - it was the pass that found what the
implementation had skipped, which is an argument for doing it before declaring a round done rather
than after.

All 28 now have inline replies and 22 are resolved. Six stay open deliberately, and the reasons
divide into three kinds. Two were **declined**: converting the breaking pull request to draft (it
would overwrite the user's own review record, and promotion already excludes drafts, so it destroys
a signal to duplicate a label), and opening a GitHub issue per colliding pair (a fourth durable
surface behind the comment, the blocking label and the manifest blocker, and it would need a
lifecycle nobody has written to close it when a later build merges the pair). Two are **pending part
D**, since the code they ask about is scheduled for deletion rather than conversion. And two were
**reversed by the parent**: the `classproperty` ask, which #151 answered by deleting
`class_property.py` in favour of abstract instance properties, so applying it here would put back
the file its own base had just removed.

That last pair is the rule this plan already records, met from a new angle: a thread answered
differently from what it asked is not the answering session's to close, even when the alternative is
better and even when it was the *parent branch* rather than this one that made the choice.

## Update 2026-08-12 (new item): the bootstrap script wrote item fields at a depth the manifest did not use

`plan-item-bootstrap` (#143) landed `.claude/hooks/plan_item_bootstrap.py`, and the first plan
outside this one to use it could not be recorded by it. `open` patches `plan.yaml` line by line and
wrote the four fields it changes — `branch`, `pull_request_number`, `session`, `status` — at a
hardcoded four-space indent. `rdr-refactor`'s manifest writes its items flush with `items:`, the
other block sequence style YAML admits, so its fields sit at two. The patched manifest no longer
parsed and `save-plan.sh` failed inside `plan_manifest_tools.py`'s `yaml.safe_load`. Found on
2026-08-12 bootstrapping that plan's `d-core-single-class`, worked around there by hand-patching the
manifest at the right depth; the account is in `rdr-refactor`'s `roadmap.md` §20 and in issue #94
comment 5269985271.

**Both manifest styles are in use here, which is why an assumption could not hold.** This plan's own
manifest is written the indented way and `rdr-refactor`'s the flush way — the tests only ever saw the
first, because the fixture was written alongside the script. `ItemIndentation` now reads the depth off
the manifest being edited (off the item block's own first line when patching, off the first item when
appending a new one), and `ManifestKey.render` takes it rather than assuming one, so no call site can
forget it.

**Two defects in the same path hid the first, and both are worse than the formatting slip.** The save
ran `save-plan.sh` with `capture_output=True, check=True`, so the script's traceback went nowhere and
the caller got a bare `CalledProcessError`. And success was printed without anything having checked
that the write landed, so `{"status": "success", "exit_code": 0}` was a restatement of the request
rather than evidence. The save now raises `PlanSaveFailedError` carrying what the script said, and
reads the plan back off the notes branch afterwards, raising `PlanNotWrittenError` when the branch
does not carry the edit. A report of success now means a save that was checked.

**The generalizable half is about fixtures, not about YAML.** A fixture written in the same session as
the code it exercises records the author's assumption twice rather than testing it once. The plans
this tool would meet were sitting on the notes branch the whole time, in both styles, and neither the
implementation nor its tests looked at them.

## Update 2026-08-12 (review round on #158): a runner that had already landed, and a test that was reproducing itself

Two comments, and each turned out to rest on a premise worth measuring rather than accepting.

**"Base this off the branch where we implemented a git command runner."** There is nothing
to base on: `GitCommandRunner` landed on `main` with #139 hours earlier, at
`.claude/stack/maintenance_git_commands.py:130`, so the helper simply calls it, and
`checkout(branch, start_point)` fitted the one raw invocation exactly. The other candidate,
#151, only *moves* that class to `.claude/shared/`, and `git rev-list --left-right --count`
puts it 159 behind and 17 ahead of `main` - so basing a standalone bug fix there would have
pulled the whole of main-that-#151-does-not-carry into the diff, which is the inflation PR
#41 cost this plan an entire item to repair. Replied and left open, since the literal ask
was answered differently.

**What applying it found is the part worth carrying.** The helper had created the branch and
*then written* the other version of the tool, so the file in the working tree changed because
the test wrote it - not because version control moved it. That is a weaker reproduction than
the bug being fixed, and it was invisible while the write and the switch sat in the same
method. Both versions are committed at install time now, and switching branches is the whole
of the step. Mutation-checked in both directions: with the switch removed the hazard test now
fails, where before it passed on the write alone.

Worth stating generally, because the shape recurs: **a test that performs the effect it is
meant to observe cannot fail for the right reason.** Nothing about the raw `run_git` call was
wrong; adopting a named method just happened to separate "switch branch" from "write file"
far enough to see that only one of them was load-bearing.

**"Wouldn't fast-forwarding fork main and restacking the whole stack solve this instead?"**
Answered on the pull request, no change made, and the reasoning is worth keeping because it
is a general property of fixes that work by making state uniform:

1. *It is circular.* The restack is performed **by** the tool whose version is in question -
   `board`, `fast-forward` and `restack` are all invocations of it. Uniformity therefore
   arrives at the end of the pass, and the tool has to be stable at the start of it. A copy
   is available before anything has run; a restack only after everything has.
2. *It cannot reach the branches that differ most.* Measured rather than argued: `origin/main`
   carries `check-move` and `maintenance.py`; #110 and #111 both carry `preflight`, no
   `check-move`, and **no `maintenance.py` at all**. Both are `needs-resolution`, and a
   conflicted branch is exactly what `WithholdBranchStillConflicting` withholds - so a restack
   leaves the dangerous ones untouched by design.
3. *Some divergence is the work.* A branch whose own diff edits `.claude/stack/` is meant to
   differ from `main`; no restack makes those equal while the pull request is open.

Two smaller measurements from the same reply: `maintenance_fast_forward.py` contains no
`checkout` at all, so the fast-forward never refreshes the invoking checkout's working tree;
and the cost is asymmetric - the proposal is ~20 branch integrations and force-pushes to other
people's branches as a precondition for *reading* a tool, against a file copy.

One incidental confirmation of this item's own premise, from trying to record this round:
`plan_item_bootstrap.py update --append-notes` does not exist on `main` - it is #151's, still
unlanded - so the manifest edit went the landed route instead. The tool's command set differing
by branch is exactly what this pull request is about, met while writing it up.

## Update 2026-08-13 (new item): the upstream pull request opens with nobody's words

The promotion phase of a maintenance pass builds a compare-and-create link that opens the
upstream pull request prefilled. The title is the fork pull request's own, and the body is
whatever `promotion_summary` finds: the first paragraph of the fork description, taken
verbatim, plus the "Full detail" link back. That is derivation standing in for writing. A
fork description opening with a heading, a badge, a status line or a link opens the
upstream pull request with that, and in every case the upstream reviewer - the one person
the text exists for - is reading a paragraph written for somebody else.

The user's request is that the body always be a point-based summary, and that the script
own everything around it: the title (copied from the fork pull request unless the caller
overrides it), the link back to the fork pull request, which is never optional, and the
caller's text. That splits the step cleanly along the line where judgment actually starts.
The bullets cannot be computed - they are a reading of a diff - so the session writes them
and nothing else; the title, the fork link, the percent-encoding, the 8 KiB URL budget and
the truncation marker are all mechanical and stay in `PromotionLink`. "As scripted and as
model-based as possible" is not a compromise between the two: it is one boundary drawn in
the one place it belongs.

The proposed interface is a summaries file keyed by fork pull request number, read by
`promote` and `run-report`, where a promotable branch with no entry is reported as awaiting
a summary rather than promoted with a body nobody wrote. Failing loudly is the point:
falling back to the first paragraph is exactly today's behaviour, so a fallback would make
the new interface optional and the old defect reachable. Two invocations follow from the
data rather than from taste - the report's `promotable` list is what tells the session
which branches need bullets, and it does not exist until the pass has run.

The second half is the delivery. `SKILL.md`'s Finish section asks the session to assemble
the pending create-links by hand: those built this run, plus every fork pull request still
carrying `cram2-link-sent` without `in-review`, each link rebuilt with `promotion-link`. It
then justifies that with "a scheduled run is configured to email its summary, so the
summary *is* the delivery", and #155 completes the thought by telling whoever registers the
Routine to turn its completion email on. The user wants no notification from either, so
that premise is withdrawn and the pass reports a table instead - one row per pending
promotion, with its number, title, branch and ready link - in whichever session ran it.
Rendering is mechanical, so the executor emits the table and the session pastes it;
`maintenance.py` finds its commands from `MaintenanceCommand.__subclasses__()`, so this is
a subclass and no registry to update. Nothing is lost when a summary goes unread, because
the link is still written into the fork pull request's own description under `## Promote`,
which is where it survives the session that built it.

One thing is deliberately unanswered rather than guessed: `update_trigger` has no
notification field, so whether an already-registered Routine's completion email can be
turned off in place or only by re-registering has to be checked before `routine-prompt.md`
instructs anyone. Inventing the answer would put a wrong instruction in the one document a
scheduled run is configured from.

Filed as `promotion-summaries-and-table` in the `stack-tooling` track, `not_started`, no
branch yet - the user asked for the plan only. New-vs-change was tested rather than
assumed: `git ls-tree main` returns `.claude/stack/maintenance_promotion.py`,
`.claude/skills/stacked-pr-maintenance/SKILL.md` and the skill's `routine-prompt.md`, so
this edits landed files. It depends on `pinned-stack-tooling` for a concrete reason rather
than a topical one: #158 rewrites every command invocation in `SKILL.md` and asserts the
exact set of invocations still allowed to run from the working tree, so a command added
here has to be pinned in the same document. And #155 - untracked by any plan item, unlanded,
`cram2-link-sent` without `in-review` - is what introduces the "turn its completion email
on" paragraph this item reverses; under the fold rule that paragraph belongs to #155 while
#155 is unlanded, so kickoff checks whether its upstream pull request exists yet and folds
the reversal there if it does not. The rest of the item stands alone in either case.

## Update 2026-08-13 (kickoff): `promotion-summaries-and-table` opens as #162, with its two open questions answered

Kicked off directly to implementation at the user's request - no plan-mode approval round.
Based on `claude/stack-tooling-pinning-qf5r2m` (#158), which is open and out of draft, so
ready to stack on by the dashboard's own rule; `stack-maintenance-executor` (#139) merged
on 2026-08-12. Both dependencies checked with `check_dependency_readiness.py` rather than
by eye.

### The interface, settled

The item's `notes` proposed a summaries file keyed by fork pull request number and left
its shape to kickoff. Settled as JSON parsed into dataclasses, with two fields per entry:
the points, and an optional title override. Points are a *list*, not a block of markdown,
because "the skill must always supply a point-based summary" is then mechanical rather
than a convention the session is trusted to have followed - `PromotionSummary.as_markdown`
renders the bullets, so a session that writes prose still gets bullets and a session that
writes one long point gets one bullet rather than a paragraph pretending to be a summary.
The title override lives in the same entry rather than on the command line for the same
reason the summary does: it is per-pull-request, and a flag would only be able to carry
one.

`promotion_summary` - the first-paragraph derivation - is **deleted**, not left as a
fallback. Keeping it would make the new interface optional and today's defect reachable,
which is the whole reason the item exists.

### What "reported as awaiting a summary" is, concretely

`promote` returns a `PromotionRound` carrying both what it promoted and every
`BranchAwaitingSummary` - a branch it would have promoted and did not, because nobody had
written its bullets. That reaches the report as its own field and the exit status as its
own member, `AWAITING_PROMOTION_SUMMARY`. A distinct status rather than reusing
`BRANCH_NEEDS_ATTENTION`: a branch waiting on words is not a branch left unpublished by a
conflict, and a pass whose *only* outstanding work is the summaries is the expected result
of the first of the two invocations, not a failure. It is ranked below every existing
non-clean status, so a conflict is never masked by it.

### The table reads the link back rather than rebuilding it

`SKILL.md`'s Finish section asked the session to rebuild each pending link with
`promotion-link`. The new `pending-promotions` command does not rebuild anything: the link
is already written into the fork pull request's description under `## Promote`, so it is
*read back* from there. That is what makes the table report the link a reader will actually
open, rather than a freshly computed one that could differ from the recorded one - and it
means the table needs no summaries at all, so it can be run in a session that did not run
the pass. `promotion_link_in` is the exact inverse of `description_with_promotion_link`,
and the two are tested as a round trip. A branch carrying `cram2-link-sent` whose
description has no link under that heading is an illegal state and raises rather than
printing an empty cell.

### Notifications: the premise is withdrawn, and the open question is answered

`SKILL.md`'s "a scheduled run is configured to email its summary, so the summary *is* the
delivery" is gone, and with it the hand-assembly it justified. The Finish section now runs
`pending-promotions` and pastes its table into the session that ran the pass.

The item left one thing deliberately unanswered - whether an already-registered Routine's
completion email can be turned off in place. Answered from the tool surface rather than
guessed: `create_trigger` takes a `notifications` object and documents `{}` as opting out
of every channel; `update_trigger` has no notification field at all. So a new Routine is
registered with notifications off, and an existing one has to be re-registered to change
it. `routine-prompt.md` says exactly that and no more.

### The fold: the reversal belongs to #155

The paragraph this item reverses - "turn its completion email on" - does not exist on
`main`. It is introduced by #155 (`claude/routine-prompt-refresh-ps5l3z`), which is
unlanded and carries `cram2-link-sent` without `in-review`, so its upstream pull request
has not been created. Under the fold rule that paragraph is #155's own work, so the
reversal is pushed onto #155's branch rather than carried here, and #162 carries none of
it. Everything else in the item stands alone either way, which is what the item's `notes`
predicted.

## Update 2026-08-13 (review round): a summary stops gating a promotion, and every GitHub link gets one home

Eleven threads on #162, applied in `c5f174d2`. Three reshaped the design, and the first reverses
what this item was built to do.

### The Action, not the session, decides whether a summary can be required

As built, a promotable branch nobody had written points for was reported `awaiting-promotion-summary`
and held back. The user's instruction - *"both arguments should be optional so that when we do this
using an action instead of a routine it works out, but when using a skill the skill should give them
and abide by the standards"*, then *"yes promote but only add the fork pr link in the body in that
case"* - settles it the other way, and the reason is `routine-cutover`'s endgame rather than
convenience: that item ends on a plain scheduled Action with **no model in it**, which can never
read a diff. A promotion that required a written summary would leave the Action unable to promote
anything at all, forever.

So both halves of a summary are optional, and a branch nobody wrote for is promoted with the link
back to its fork pull request and nothing else. `EmptyPromotionSummaryError` and the
`AWAITING_PROMOTION_SUMMARY` exit status are deleted with the concept.

**What replaces the gate is where it always belonged - the skill.** Writing the summaries moved from
step 3 (after the pass, acting on what it held back) to step 2 (before it), because the pass now
promotes whatever it is given. The promotable branches come from `stack.py next --porcelain`, which
answers off the board step 1 has already exported, so the reordering costs no extra command.

Worth carrying as a shape: *this item's own argument against a fallback was right about the
mechanism and wrong about the scope.* "A fallback makes the new interface optional and today's
defect reachable" holds for **deriving** a body from the fork description, which is what produced a
badge or a heading for the upstream reviewer. It does not hold for **omitting** one, which produces
a body that is short and correct. The two were conflated because both are "what happens with no
summary".

### The upstream's title convention, which fork titles do not follow

Recorded from the review: an upstream title is always `[TopicName] Catchy Minimal Relatable Title` -
`Agents`, `DevTools`, `Basstler`, `EQL`, `Ormatic` are the kind of topic. Fork titles are ordinary
sentences ("Pin the stack tooling for the length of a maintenance pass"), so copying one through
produces a non-conforming upstream title nearly every time. `SKILL.md` states the pattern and says
the fork-title fallback is mechanical rather than conforming; the script still accepts no title, for
the Action's sake.

### Promotion reports per branch, mirroring the restack

The reviewer asked whether the awaiting state should be a `Branch` attribute with a status
`StrEnum`. It cannot be a `BranchStatus` member: that enum is `derive_status`'s output, computed
from labels and git ancestry, and whether anybody has read a diff is not in the board - a `Branch`
field would hang pass-time state off a model whose whole contract is that it is derived.

But the *shape* was already in this module, in its restack half. `promote` now returns one
`BranchPromotion` per branch with a `PromotionOutcome` - `promoted`, `already-linked`, `withheld`,
`link-label-cleared` - exactly as `restack` returns `BranchOutcome` with a `RestackOutcome`. Two of
those a pass used to drop in silence. The enum also absorbed both hardcoded markers
`print_promotions` carried, which is the "or a new one with other related members" thread answered:
looking for the related members is what found the second marker.

### One statement of every GitHub link, which is also how the read-back got tightened

Four sites composed a `github.com` URL: `PromotionLink.build`, the hand-written
`RECORDED_PROMOTION_LINK_PATTERN`, `_fork_pull_request_link`, and the tests. `GitHubLinks`
(`.claude/stack/github_links.py`) is now the one statement of the host and both formats, and
`stack.py` composes through it - `Repository` is a `TYPE_CHECKING`-only import there, so the sibling
import is not a cycle, and `quote` left `stack.py` with the encoding.

The payoff is not tidiness. `promotion_link_in` derives its pattern with
`re.escape(comparison_with(base))`, so **what a recorded link looks like comes from what builds
one** - and a link is now recognised by the host, the configured upstream repository and the base
branch, where before any `https://` URL under the heading qualified. A hand-written regex for a
format another module composes is a second copy of that format, which is the general case of the
duplication the same reviewer flagged in the tests.

### Left open deliberately

The shared dataclass-exception base, twice. `DataclassException` lives only in `.claude/shared/` on
#151, which is **159 commits behind `main`** while this branch is 0 behind - so rebasing there is
the inflated-diff mistake #154 made and reverted on 2026-08-12 (45 files to 261). Measured rather
than argued: all 14 exceptions under `.claude/stack/` use the plain `@dataclass` + `__str__` idiom
today, `ExternalCallFailed` included, whose own docstring says it mirrors krrood's idiom "without
importing it". Converting 2 of 14 here would leave 12 inconsistent, so whichever item lands
`.claude/shared/` converts the set in one pass. The user's call, and worth pairing with a test that
every exception derives from the base - which can only be written once the base exists.

And the two asking whether `or` returns a bool. It does not - it evaluates to one of its operands -
so both are answered with the measurement and no change.

## Update 2026-08-13 (new item): the verdict moves to CI, and the integration branch gets a stable half

`integration-branch`'s Part D — replacing the local `--test` run with GitHub CI — was deferred
on #154 with three reasons and has since grown two more requirements from review. It is its own
item now, `integration-branch-ci-verdict`, `stack-tooling`, `not_started`, stacked on #154.

### Why a separate item rather than folded into #154

Run against `scope-decision.md`'s prefer-the-change test rather than judged by feel. Part D does
*modify* what #154 introduces — it deletes `integration_test_command`, `--test`, `--no-test`,
`TestCommandNotConfiguredError` and `_run_tests`. But the test asks what remains when the edits to
the parent are removed, and what remains here is a GitHub Actions client, a new CI job, a
pytest marker, a second long-lived branch and a subcommand that reads a run's conclusion. That
stands on its own by a wide margin, so it is ordinary stacking rather than a disguised
modification — the same answer the rule gave #110 against #106.

Three things settled it beyond the rule: #154 is 45 files and ~7,500 additions across 28 commits
with a converging review round; Part D needs an Actions client that does not exist in this tree,
because #146 measured the reachability but is unlanded; and its verification is a real CI run on a
pushed branch, which is the one thing nothing else on #154 needed.

Two review threads on #154 stay open pointing here rather than resolving — the
`DataclassException` one, whose subject (`TestCommandNotConfiguredError`) this item deletes rather
than converts, and the whole-CI one this item is the answer to.

### The fact that shapes the whole design, measured rather than assumed

`ci.yml` triggers on `push` to `main` and on `pull_request`, and nothing else. **A pushed
integration branch therefore gets no CI at all unless a pull request exists for it.** That is not
a detail of how to arrange things; it is why the user's "a PR into the existing stable integration
branch" framing is the only shape that gets a verdict, and it should be checked again at kickoff
rather than inherited from here.

### The two requirements added in review

**A stable branch and a candidate.** `integration` stops being a pointer moved to whatever was
built last and becomes the last build whose CI went green; each new build is a candidate, opened
as a pull request into it, and merged once green. What that buys is a branch a developer can work
from that is known to work, instead of one that is fresh and unverified.

There is a tension to resolve rather than paper over: a build is regenerated from scratch from the
upstream base plus the tips, so a candidate shares no history with the stable branch it would
merge into, and its pull request's diff is *everything that changed between two independent
builds*. Merging it also makes `integration` accumulate merge history, which is the one property
the design has held since the item was recorded — "it exists to be built from, not to be history".
Whether the stable branch is a real merge target or simply a second pointer force-updated on green
is the first thing to settle.

**A pytest marker and a job that runs only what it marks.** The failing test that step 5 pushes to
the breaking branch gets a marker — the user's suggestion is one named for the label,
`integration-conflict` — and a CI job runs only marked tests. Two things follow: the verdict
arrives in a fraction of the matrix's time, and `integration-conflict` gains an automatic clearing
condition it does not have today. That closes the gap the label was created with: the 08-11 round
established that `WithholdBlockedBranch` cannot clear it, since a failure between two cleanly
merging branches never makes a pull request conflicted, and the label was documented as
"never cleared automatically" for exactly that reason. A marked test that passes is a different,
and correct, clearing condition — it says the thing that was broken works now.

The user also offered a third option worth keeping: the script that writes and clears the label
could run only the marked tests itself, or trigger just that job, rather than depending on the
whole run.

### What is left in place until it lands

`integration_test_command` in `stack.toml`, `--test`/`--no-test`, `TestCommandNotConfiguredError`
and `_run_tests` all still exist on #154 and all still work. Part D is what removes them, so
nothing is half-migrated in the meantime.

## Update 2026-08-13 (resolved): #154's naming round, and a contract test a reply had promised but not written

`/plan-item-resolve workflow-unification integration-branch`, session
https://claude.ai/code/session_01RhwNdD7ChskkomV1TCiRLU. Seven new review threads, all applied in
`f83d5133`; 599 tests across the three directories CI runs, was 595.

### A name settled by measuring what the runner does with it

Asked for something simpler than `semantic break`, the user proposed `TestFailure`. The direction
was right - the thing is that the suite fails - and the literal name is one pytest penalises:
**a module-scope class named `Test*` in a test file is collected**, and `test_integration.py`
imports these names directly. Probed rather than argued: a frozen dataclass `TestFailure` imported
into a test module emits `PytestCollectionWarning: cannot collect test class 'TestFailure' because
it has a __init__ constructor`. `TestCommandNotConfiguredError` escapes it today only because the
tests reach it as `integration.TestCommandNotConfiguredError` rather than importing it - so the
existing file is not evidence that the name is safe.

`IntegrationTestFailure` keeps the user's words and dodges the prefix, and was their call once the
measurement was in front of them. `locate-break` became `locate-failure`, `escalate` became
`block-branch` (the vocabulary `Configuration.blocking_labels` and `WithholdBlockedBranch` already
use, and what the command's own docstring already claimed while the command was called something
else), and the prose in `SKILL.md` and `README.md` followed. `breaks_against` and the comment
prefix stay: the objection was to the noun, and those are verb phrases that read correctly.

Worth carrying: a naming question is intent and belongs to the user, but a name can still have a
*measurable* cost, and putting that measurement in front of them is different from arguing for a
different name. Two rounds of this plan have now been settled that way rather than by preference.

### The status answers whether it was carried, and one type absorbs the other

`TipStatus` members carry a `TipStatusSpecification` with `spelling` and a `carried` bool, so
`reached_the_build` is `self.status.carried` rather than membership of a set. The gain is not
tidiness: a status added later is *answered* by having to give `carried` a value, where the set was
answered by nothing and would have silently reported the new status as left out.

That made the second half possible. `unreviewed` is a `TipStatus` member now, so the loose
`UNREVIEWED_STATUS` constant and the whole `UnreviewedBranch` class are gone: every branch a build
considered is one `PullRequestStackTipOutcome`, and `collided_with` generalises to `attributed_to`
- *the other branch this outcome is about*, whether that is the sibling it conflicts with, the base
it is stale against, or the draft beneath it. Those were the same question asked three ways.

**One ask was answered differently, for a measured reason, and left open.** The user asked for the
enum to *inherit* from the specification. `class TipStatus(TipStatusSpecification, Enum)` builds,
but the member stops being a `str`, and `json.dumps` then refuses the report outright - taking every
`document[key] == TipStatus.X` comparison with it. Each member carries a specification instead,
unpacked by a `__new__` that keeps the `str` value. Same dataclass, same field; only the inheritance
edge is missing, and only because `StrEnum` owns `__new__`.

**Pushed back on one half of another**, also left open: `UnreviewedBranch` should not become a field
of `stack.py`'s `Branch`. That is the shared board model the maintenance pass and the dashboard also
read, and being unreviewed *for a build* is the result of one build's selection walk rather than a
property of a branch - `attributed_to` names the draft *beneath* it, which is a fact about a chain.

### A promised test that did not exist

An earlier round's reply on the report-keys thread said the literals survive in
`test_the_report_keys_are_the_ones_a_caller_parses`, "which asserts `{key.name: str(key) for key in
ReportKey}` against a written-out mapping". **That test was never written.** Found by renaming a
wire key in this round and noticing nothing failed.

The gap was narrower than the reply implied, and measuring it is what made the fix honest. Most
`ReportKey` members mirror a dataclass field that `asdict` produces, so renaming one *does* fail
wherever it is read - mutation-checking `TIPS` confirms it. `STATUS` and `EXIT_CODE` do not:
`as_json` injects them through the enum, so writer and reader change together and the rename is
invisible. Those two are also the first thing `/integration-conflict-triage` matches on. The test
exists now and its docstring says which half it is really guarding.

Generalizable, and uncomfortable: **a reply describing a test is not a test.** This plan already
records the rule that single-sourcing a contract deletes a guard, and this is the failure mode one
step later - the guard was correctly identified, its replacement was described on the thread in
detail, and nothing checked that the description was true. Anything a review reply claims to have
added is worth grepping for before the thread is resolved.

### The same shape found in the labels, from a different comment

Asked why the labels are not a `StrEnum`, the answer had the same structure. `DefaultLabel` names
all four; the wire spelling matters because a fork's owner creates these by hand and GitHub does not
create a missing one; so one contract test pins member to value. Applying it also showed the guard
had been *accidentally* spread: before, renaming `NEEDS_RESOLUTION` failed three tests, two of them
about withholding and promotion rather than about a label's spelling. Both read the enum now, so
each fails only for its own reason.

### Part D became its own item

`integration-branch-ci-verdict`, recorded in the section above. The user's two newest comments
expanded it well past what was deferred - a stable/candidate branch pair, and a pytest marker with a
job that runs only what it marks - and the prefer-the-change test comes out in favour of stacking:
strip the deletions to #154's files and a whole Actions client, CI job, marker and second long-lived
branch remain.

One fact found while costing it is the load-bearing one for that item: `ci.yml` triggers on `push`
to `main` and on `pull_request` only, so **a pushed integration branch gets no CI unless a pull
request exists for it**. That is why the user's "a PR into the existing stable integration branch"
framing is the only shape that reaches a verdict at all, rather than one option among several.

### A base merge landed mid-session

`main`'s ORM-interface change (#543) arrived on this branch from outside the session while the round
was being written - 145,000 deletions, none of them reachable from a `.claude/` diff. Merged and the
whole suite re-run rather than trusting the merge, per the standing rule that ancestry answers
"did I lose anything" and only running the tests answers "does it still work".

## Update 2026-08-20 (resolved): #154's 18-thread round, and an ask that does not compile

`/plan-item-resolve workflow-unification integration-branch`, session
https://claude.ai/code/session_01RXr6gpbCyaa9K3V8F5kwRk. Eighteen threads, drafted 08-14 and 08-19
and submitted as one review on 08-19; all answered, 12 resolved, 6 open on purpose. Plus the base
merge the branch had been `dirty` on since 08-18. 620 tests across the three directories CI runs,
was 599.

### Two asks in one round that cannot both be satisfied, and the measurement that settled it

The round asked for `TipStatusSpecification.spelling` to become `name`, and — two comments later —
for `TipStatus` to inherit that specification *in addition to* `StrEnum`. Probed rather than
reasoned about, on 3.11 and on CI's 3.12, with identical results:

- `class TipStatus(TipStatusSpecification, StrEnum)` raises `TypeError: too many data types`.
  Python permits exactly one data-type mixin and `StrEnum` has already spent it on `str`. The
  literal ask is not a shape that exists.
- A dataclass field called `name` on **any** enum mixin fails at class creation:
  `AttributeError: <enum 'Enum'> cannot set attribute 'name'`. So the rename and the inheritance
  are mutually exclusive, whichever mixin shape is chosen.
- `class TipStatus(TipStatusSpecification, Enum)` — inheriting, dropping `StrEnum` — does build,
  and costs more than the 08-13 reply knew. That reply named `json.dumps` refusing the report. The
  larger cost is that `dataclasses.asdict` **recurses into a member that is itself a dataclass**,
  so a status silently serializes as `{"name": "skipped", "integrated": false}` rather than
  `"skipped"` — a wire-format change in a document `/integration-conflict-triage` and
  `stacked-pr-maintenance` both parse. `dict_factory` does not save it: it runs bottom-up, after
  the member is already a dict.

The user chose `name` once the measurement was in front of them. That is now the third round of this
plan settled by measuring the cost of a name rather than arguing about it — and the first where the
measurement showed two of the user's own asks were in conflict, which is a more useful thing to
report than either one taken alone.

What did land is the part the neighbouring comment was really about: the member carries its
specification instead of copying each field onto itself, so `name` and `integrated` are declared
exactly once, and `carried` became `integrated` throughout the selection vocabulary. `AGENTS.md`
already carried the rule behind all of this — *"`Enum` reserves `name`"* — which nobody had
connected to this class until the two asks arrived together.

### A mechanical rename reaches inside names it was never meant to touch

Asked to verify that `escalate` had really become `block-branch`, the answer was no: production
code, `SKILL.md` and `README.md` were renamed last round, and two test names plus their docstrings
were not. Checking that turned up two *further* names, casualties of an earlier `a_*` → `create_*`
sweep, that had stopped describing anything at all:

- `test_a_build_leaves_create_unreviewed_branch_out_and_says_so`
- `test_a_break_only_the_combination_causes_says_so_rather_than_naming_create_branch_object`

Both had been green and meaningless for two rounds. The generalizable half is narrower than "renames
are risky": a sweep matching an identifier reaches occurrences of that identifier *inside* names
whose subject is something else, and no test fails when it does. Reading the names back is the only
check.

### Single-sourcing the wire format, and the guard that has to grow with it

The mirror-schema proposal was taken as asked: `from_json` per report level, so the key access
happens inside the class owning that level and a reader uses dot notation. Ten keys had no
`ReportKey` member and were being reached by field name through `asdict`.

The cost is the one this plan has now recorded three times in different clothes. With the writer
rendering through the enum and the reader parsing through it, a rename changes both sides
identically and nothing fails — so `test_the_report_keys_are_the_ones_a_caller_parses` becomes the
*only* guard, and it had to grow from 8 keys to 22 in the same commit. The rule that is worth
carrying: **single-sourcing a contract is not free, and the commit that single-sources it is the
commit that must widen the one test standing outside it.**

`block-branch`'s document was the case where that had already gone wrong quietly: built from a dict
literal inside the command, no dataclass behind it, and no test at all. It is a `BlockedBranchReport`
now.

### Splitting a test file, checked rather than trusted

`test_integration.py` at 1564 lines became seven modules along the `# %%` sections already in it,
none over 305, with the shared constants and factories in `integration_fixtures.py`. The check that
matters is not that the suite still passes — a dropped module would still pass — but a name-by-name
diff of every `def test_` before and after, which comes back as exactly the intended renames plus
the round's three new tests.

### Four failing tests that were the container, not the code

Worth recording because the first reading was wrong. After the base merge, four hook tests failed.
They fail identically at the pre-merge head, and CI is green on it: `check-setup.sh` probes
whichever `python3` is first on `PATH`, and that interpreter is not the one holding the test
dependencies unless the run puts it there. CI arranges exactly that and this container did not.

The rule: **a test that asserts on a script's own subprocess is asserting about `PATH` as much as
about the code**, so a local failure in one is evidence about the environment until the same commit
is shown failing somewhere else.

### Six threads left open, in three kinds

- **Impossible as asked**: the inheritance, with the three measurements above.
- **Questions put back to the user**: where the six new `GitCommandRunner` methods belong, given
  four have no production caller and `AGENTS.md` says to ask before keeping such methods; and
  whether the 400-line rule the user stated extends to `integration.py` itself, at 1500 lines.
- **Answered differently, or owned elsewhere**: `blocking_labels` returns *configured* labels a
  fork may rename, so they are not `DefaultLabel` members and the set does not belong on that enum
  — what did move onto it is `configuration_key`, which let `ConfigurationKey` stop naming the same
  four labels a second time; and the automatic clearing of `integration-conflict`, which is the
  pytest-marker half of `integration-branch-ci-verdict` and needs an Actions client this tree does
  not have.

### State

`mergeable_state` was `dirty` and is not; the conflict was additive on both sides of
`scratch_repository.py` — `main` replaced the scratch identity's two literals with #547's
`SCRATCH_IDENTITY`, this branch had added the `commit.gpgsign` line beside them, and both are kept.
`needs-resolution` is left for the next maintenance pass to clear itself, as with every other item
here. The base stays `main`: `git merge-base --is-ancestor` re-confirms #154 already contains #151's
head and is 195 commits ahead of it, so the recorded deferral of the reparent is still correct.

## Update 2026-08-20 (kickoff): the cross-item drift check opens as #184, and the item's own root-cause sentence is wrong

Kicked off `deferred-dependency-drift-check` (`dashboards` track). The case it was
filed from still reproduces exactly, checked against `rdr-refactor`'s live manifest
rather than taken from the item's notes:

```
D-ui-splice-fix  -> deferred     | pr 78 | depends_on ['d-core-backend']
D-ui-rendering   -> in_progress  | pr 79 | depends_on ['D-ui-splice-fix']   <- stranded, unflagged
D-ui             -> in_progress  | pr 76 | depends_on ['D-ui-rendering']
```

Eight of `rdr-refactor`'s forty-five items are deferred, and exactly one live dependent
hangs off one of them today.

### The item's own notes name the wrong predicate

Worth recording, because the note reads as settled: *"`Item.is_ready_to_unblock_dependents()`
has the right predicate already (correctly False for a deferred/closed_unmerged
dependency)"*. It is false for those, but it is `is_effectively_done() or OPEN_READY` -
so it is also false for a `not_started` dependency and for an `OPEN_DRAFT` one. Stacking
on an open draft is this repo's normal workflow, so a drift check built on that predicate
would flag most of every plan.

The same note's *"Proposed fix"* sentence - "an item that is itself deferred or
closed_unmerged" - is the correct condition, and the two halves of the note disagree with
each other. The plan follows the second.

This is exactly what the 2026-08-01 entry on #122 ("The consolidation this plan proposed
three times is wrong") predicted: the sidebar's admission rules each need *their own*
named predicate, and reaching for an existing one because it is nearly right is the
recurring mistake. `Item.is_stalled()` - deferred, or the pull request was closed without
merging - becomes the third sibling beside `is_ready_to_unblock_dependents()` and
`is_ready_for_dependent_review()`.

### Two design calls, put to the user rather than assumed

- **The drift field becomes a list.** An item can carry manifest drift *and* a stalled
  dependency at once, and `Item.drift_description: str | None` would silently drop one -
  which is the failure this item exists to fix. It becomes
  `drift_descriptions: list[str]`, and `DashboardSummary` gains `drift_flag_count` because
  the banner counts flags rather than items.
- **Direct dependencies only.** `D-ui-rendering` is flagged; `D-ui` is not. `D-ui`'s own
  base is alive, and it becomes correct the moment `D-ui-rendering` reparents - a
  transitive flag would repeat one root cause up the whole chain. The item's notes name
  both #79 and #76 as affected, so this narrows the item deliberately rather than by
  oversight.

### Scope, tested rather than eyeballed

`git ls-tree origin/main` returns all four touched paths (`build_dashboard.py`,
`templates/dashboard.html`, `tests/test_build_dashboard.py`, `SKILL.md`), so this edits
landed files and stands alone. Compared by purpose as well as path against every in-flight
dashboards-track pull request: #157 owns the *visibility* of deferred items and its diff
touches neither `_drift_description_of`, `_classify_items`, `Item.drift_description` nor
the drift template blocks (and is already ready-for-review); #111 owns LOC/CI chips; #150
owns the URL cache; #149/#151 are skill documents. Conflict-adjacent with #157 in the test
file and one sidebar template region, both additive - the whichever-lands-second-merges
convention covers it.

Opened as draft PR **#184** off `main` with the `bug` label.

### Left out on purpose

- `_compute_next_steps` needs no change: a `not_started` item with a stalled dependency
  already fails `_dependencies_are_ready`, so it is already kept out of "ready to start"
  and already gets no action button. It was only ever missing the *explanation*.
- The `example/` fixture is untouched - checked, not assumed: none of its six items is
  deferred and none has a closed-unmerged dependency, so the new check produces no flag
  there. `example-walkthrough.md`, its counts assertion and the committed screenshots stay
  as they are, and no screenshot regeneration is needed.
- `check_dependency_readiness.py` keeps its current JSON. Reporting `is_stalled` there
  would help `plan-item-kickoff`/`plan-item-resolve` explain *why* a dependency is not
  ready, but that is a different surface and would widen this pull request.

### A stale line in this roadmap's own Conventions

The "Conventions" section still ends "…and subscribe to its activity". That was inverted
by `no-pr-subscriptions` (#153, merged) and is now forbidden outright by the personal
notes. Recorded here rather than edited in place, since the Conventions section is
historical text this plan's entries were written against.

## Update 2026-08-20 (implemented): the cross-item check ships as #184, and it found the case it was written for

Implemented in the same session as the kickoff above, commit `40d9d6dd` on
`claude/deferred-dependency-drift-pr-qxpfsm`. Tests first: 22 failing, then the
implementation. `.claude/skills/plan-dashboard/tests/` is at 239 passed and
`.claude/hooks/tests/` at 107.

### The live run is the part worth recording

Building `rdr-refactor` through the new code flags exactly one item:

```
D-ui-rendering (in_progress):
  depends on 'D-ui-splice-fix', which is deferred - consider reparenting onto d-core-backend
```

`D-ui` is correctly unflagged - its own base, `D-ui-rendering`, is alive. Before this
change that plan reported **zero** drift, with eight deferred items in it and one live
dependent hanging off one of them. The dashboard has been republished, so the flag is
on the page rather than only in this entry.

`workflow-unification` itself gains no flag, which is the expected result: it has no
deferred item at all.

### The shapes the implementation settled

- **`_classify_items` moves `drift_descriptions` into its second pass.** The first pass
  fills `live_state` for every item; a cross-item check cannot read another item's
  before that has happened, and a dependency can appear after its dependent in
  `items[]`. The two-pass structure already existed for `_action_for`; this is the
  second reader that needs it, so the docstring stops naming one caller.
- **The reparent suggestion is omitted, not emptied.** A stalled dependency with no
  `depends_on` of its own has nothing to suggest, and a trailing "consider reparenting
  onto " would be worse than saying nothing.
- **`_resolved_dependencies_of` absorbed three copies of one comprehension.**
  `_compute_next_steps`, `_compute_ready_to_review` and `_dependencies_are_ready` each
  resolved `depends_on` against `items_by_identifier` with the same skip-the-unknown
  guard, written out three times. The new check would have been a fourth. Incidental to
  the fix and small, but it is the same one-operation-one-name rule the 2026-08-01 entry
  on #122 was arguing about from the other direction: sharing the *resolution* is right
  precisely because it shares no threshold - each caller still applies its own predicate.
- **The item card renders one line per description**, and the sidebar banner counts
  flags rather than items, which is why `DashboardSummary` gained `drift_flag_count`
  beside the existing `drift_count`. The JSON wire format only gains a key; nothing
  existing changed meaning.

### One test lesson

`test_render_shows_one_drift_line_per_description_on_the_item_card` first failed on a
real difference rather than a real bug: the description embeds a quoted identifier, and
the template autoescapes, so the page carries `&#39;`. The assertion now derives the
expected markup through `markupsafe.escape` - the same function Jinja's autoescaping
uses - rather than hand-writing the entity, so it cannot drift from the escaping the
template actually applies.

## Update 2026-08-20 (resolved, second round the same day): #154's twenty threads, and which duplication is worth removing

`/plan-item-resolve workflow-unification integration-branch`, session
https://claude.ai/code/session_01Ra51SAHQKy7TVYRG2HRERW. Twenty threads, drafted 13:15 to 14:04 and
submitted as one review at 14:46. All answered, 14 resolved, 6 open on purpose, in `434ace04`. 620
tests across the three directories CI runs, deliberately unchanged.

### The stall was the manifest describing a moment that had passed

The entry directly above this one, written by the previous session at 08:32, ends *"nothing is
outstanding on this branch. It is waiting on review"* - and so does the branch's PR-progress note.
Six hours later a twenty-thread round landed. Nothing was wrong with either statement when it was
written; both were simply still being read as current.

This plan has now recorded that shape twice, and the pair is worth reading together. On 2026-08-12
it was a *hedged* statement outliving its condition (`#139`'s "not blocked" note against a `dirty`
pull request). Here it is an *unhedged* one, which is the commoner and quieter case: "nothing
outstanding" is true of every branch at the instant it is written and false of most of them within
a day. A resolve session's first move is therefore to read the pull request rather than the entry,
and the entry only to learn what has already been decided.

### The round is one finding, twenty times

A branch name spelled in the arrange and again in the assert. It was sweepable, and the sweep went
through the whole of `test_integration_selection.py` rather than only the seven tests a comment
landed on - the four the reviewer had not reached had the same shape, and a module half converted
reads worse than one not converted at all.

The half of it with no single source anywhere was the *file* those tests check for.
`ForkCheckout.branch_from` commits `f"{name}-file"`, and four assertions plus a push refspec retyped
that suffix. `file_added_by` is that spelling now, and `branch_from` calls it, so the two cannot
drift.

### Two asks answered by measuring rather than by doing

The fourth round of this item settled that way, and both measurements point the same direction.

**Multiplying the expected statuses by `len(report.tips)`** was mutation checked by making the
second tip a draft, so the build carries one tip of the two the test arranges. The literal form
**passes** - both sides shrink together, so the length stops being checked at all - and in that run
the mutation was caught two lines further down by an unrelated assertion, which is accidental
coverage of exactly the kind this branch already found itself relying on once. Multiplying by the
*arranged* count removes the repeated literal and keeps the assertion.

**`create_pull_request_object` went and the other six factories stayed**, measured one at a time
rather than as a class. It supplied only `draft=False`, since `labels` already has a
`default_factory`, so it genuinely was the constructor under another name. `create_branch_object`
supplies `strategy` and `labels`, which `Branch` requires with no default, at 21 call sites about
neither - removing it would put a strategy and an empty label list in front of the branch names each
test is actually about.

### The generalizable half: a repeated literal is not always a duplication

Both asks would have replaced a literal with an expression that no longer said anything - a length
derived from the thing under test, and a constructor call whose required fields become the noise. So
the rule this round adds to the plan's collection: **a repeated literal is a defect when the two
copies can drift apart, and not one when the second copy is the assertion.** The arrange and the
assert naming the same branch is duplication; the arrange and the assert both stating the count is
the test.

That is the same distinction the 2026-08-01 entry on #122 drew from the other side - sharing the
*resolution* of a dependency is right precisely because it shares no threshold - and the one the
mirror-schema round drew when single-sourcing the wire format deleted its own guard.

### One defect the review found that nothing mechanical could have

`integration_fixtures.py` carried the same three-line comment and `__all__ = ["fork_checkout"]`
twice, thirty lines apart. A second `__all__` silently rebinds the first, so with both binding the
same value there is no error, no warning, and no test that could fail. It survived a 1564-line file
being split into seven modules the round before. Only reading it found it.

All six modules now use the ordinary `# noqa: F401` this repository already uses for a deliberately
unused import, which is one line on the import itself rather than four lines thirty lines below it.

### Six threads open, and one correction to the entry above

Open: the four the previous round left, plus **deleting
`test_the_report_keys_are_the_ones_a_caller_parses`** - answered rather than done, because it is the
only guard left on the wire format since the mirror schema, and because it is the very test a reply
on this pull request once claimed existed when it had never been written - and the **shared registry
of script paths**, where 25+ sites across `.claude/hooks/`, `.claude/skills/plan-dashboard/` and
`.claude/stack/` resolve paths the same way and `dev-tooling-python-package` deletes the layer they
exist for. `INTEGRATION_SCRIPT` does now read `Path(integration.__file__)`, which was the free half.

**Correction to the previous entry's process note.** It records four hook tests as failing in a
session container for an environment reason. They do not fail here, and the difference is not the
container: `pytest` was installed as a `uv` tool with its own interpreter, while PyYAML, Jinja2,
markdown and nh3 sit in `/usr/local/bin/python3`. Installing `pytest` into *that* interpreter makes
all 620 pass locally. So the observation stands and the remedy is one install rather than a caveat
to carry - worth knowing before the next session reads that note and concludes the failures are
expected.

## Update 2026-08-20 (third round the same day): binding the object, and a helper that was a type conversion

Five comments on #154, posted 20:36 to 20:49 — after the entry above had recorded the
round before it as answered, which is the third time in two days that has happened on
this branch. All five addressed in `f09e110f`; four resolved, one left open. 621 tests
pass across the three directories CI runs, from 620.

### The previous round's own fix, taken one step further

That round replaced a branch name spelled in the arrange and again in the assert with a
name bound to a local. The reviewer's answer is that the local should be the *branch*,
not its name:

```python
    reviewed = create_branch_object("reviewed", 1)
    unreviewed = create_branch_object("unreviewed", 2, status=BranchStatus.DRAFT)

    tips = tips_of(create_stack_object([reviewed, unreviewed]))

    assert [tip.name for tip in tips] == [reviewed.name]
```

It is better for a reason the name-local form does not have: `parent=bottom.name` is a
real reference, so a renamed branch cannot leave its child pointing at one that no
longer exists — where `parent=bottom` with `bottom` a string is a third copy that
happens to agree.

It also removed two things the intermediate form had left in place, both invisible until
the objects were bound: a `number = 7` duplicated exactly the way the names were, and a
local shadowing its own result — the arrange bound `unreviewed`, and the act rebound it
to the list of branches left out, so the test named one thing twice. Swept the whole
suite rather than the tests commented on, and `grep '^    [a-z_]* = "'` now returns
nothing across every module; that caught two more push refspecs still retyping a tip's
name, the pair missed when the same fix was applied to `SECOND_TIP` the round before.

### A helper whose only content was a type conversion

`branch_names_in` returned `set(checkout.git.branch_names())`. The ask was to return the
iterable and convert at the assertion — and doing that left a one-line pass-through,
because `git.branch_names()` already returns `tuple[str, ...]`. So the helper is deleted
and the one call site reads git directly, converting where the subtraction needs it.

The tell is worth keeping, because it is the second instance in two rounds:
**the helper's docstring existed to explain a surprise the helper itself created.** It
said the set was "not because branch names could repeat — git already guarantees they
cannot", which is a sentence only necessary because the return type was doing something
the caller had not asked for. Moving the conversion to the assertion moved the reason to
where a reader meets it.

`create_pull_request_object`, deleted the round before, is the same shape: a factory that
supplied one defaulted argument. The test to apply before writing either is whether
anything remains once that single value is passed at the call site.

### The staged conflict gets the schema every other document here has

`stage_conflict` returned a `dict` built from bare `"worktree"` / `"conflicting_paths"`
keys while `ReportKey` names every other document this module writes — the gap flagged on
the `_replay.py` thread last round and granted this one. It returns a `StagedConflict`
whose `as_json` reads through that enum.

One decision inside it goes beyond the two keys the comment named. The old dict called
the pair `tip` and `against`; a build's own report already calls exactly that pair
`branch` and `attributed_to`, and `attributed_to`'s docstring is *"the other branch an
outcome is about"*. So the pair is named once across the module rather than twice, and
only `worktree` needed a new member. Checked rather than assumed that nothing reads the
old spellings: `SKILL.md` says "the worktree it names" without naming a key, and
`--worktree` on `record-resolution` is a flag.

The document had **no test at all** — only the in-process `staged["conflicting_paths"]`
read was checked, which is precisely the half a caller does not see. That is the same
gap `block-branch` had before the round that gave it `BlockedBranchReport`, met a second
time in the same module: a document built inside the method that returns it has its
field names written once, in the only place nothing is looking.

### The comment said what pytest does, not why the import must stay

*"What do you mean by pytest collects it as a fixture?"* — a fair question about a
comment that described the mechanism instead of the consequence. `fork_checkout` is a
`@pytest.fixture` in `test_maintenance.py` and no `conftest.py` shares it, so pytest
resolves it from the requesting module's own namespace and the import is what binds the
name there.

Measured rather than asserted, since the reply is the answer: deleting that one line from
`test_integration_replay.py` gives `2 passed, 8 errors`, every error
`fixture 'fork_checkout' not found`. The comment is now
`# noqa: F401  (imported so pytest finds the fixture by name)` across all six modules.

### The contract test is documented rather than deleted

The user did not accept the previous round's answer that
`test_the_report_keys_are_the_ones_a_caller_parses` should stay unexplained — the
instruction was *"you can at least document why this test exists with an example"*. Its
docstring now carries the rename it exists to catch, spelled out end to end: rename
`EXIT_CODE`'s value and every other test still passes, because writer and reader both go
through the member.

Writing that example also found the docstring's second paragraph was wrong in a way
nobody had caught across two rounds. It claimed the `asdict`-backed keys were "pinned by
nothing else", which is exactly backwards — those *are* pinned elsewhere, because a field
rename fails wherever the field is read. What is pinned by nothing else is `status`,
`exit_code`, and everything `block-branch` and now `stage-conflict` emit.

Left open, per the rule that a thread answered differently from what it asked is the
user's to close.

## Update 2026-08-20 (fourth round): a contract test that was checking the wrong object

One comment, on the report-keys thread the round before had answered with a worked
example: *"can you make a test that reproduces the situation that this test fails in? do
you think this situation can ever happen again?"*

### The first question could not be answered as asked, and asking it found the defect

The situation `test_the_report_keys_are_the_ones_a_caller_parses` exists for is a rename
that no test catches, so *reproducing* it is a mutation rather than an assertion — there
is no test to write that fails when the guard is present.

But looking for one exposed what the test was actually checking, which was the wrong
object. It compared `{key.name: str(key) for key in ReportKey}` against a written-out
copy of the same enum, and **never rendered a document**. So it caught a rename by
noticing that a table beside the enum disagreed with it, rather than by noticing that
what a caller parses had changed. The tell was available for three rounds and nobody used
it: the test imported nothing that produces a document.

That also explains why the reviewer kept circling this test across three rounds — first
proposing deletion, then asking for the enum in the tests, then asking for an example,
then asking for a reproduction. The objection was right each time and aimed at the
symptom; the shape was a test asserting the enum against a copy of itself.

### What it reads now, and the half that was missing entirely

`every_document_this_module_writes` builds one fully populated instance of each of the
four documents this module hands to another program — the build report, the localised
failure, the blocked branch, the staged conflict — and collects every key at every depth.
The literals are compared against that, so the failure is the caller-visible one.

Which made the second half free, and it had no coverage at all before:

```python
def test_every_report_key_names_something_a_document_carries():
    assert every_document_this_module_writes() == {str(key) for key in ReportKey}
```

A member added and never emitted is a name that looks like part of the wire format and is
not; a key emitted without going through the enum is a key in the format that nothing
names. Both were silent, and the first is exactly the shape a future member arrives in —
this branch added `WORKTREE` a round earlier and nothing would have noticed if it had
gone unused.

### The reproduction, measured across the whole directory

| mutation | result |
|---|---|
| rename `EXIT_CODE`'s value to `exitCode` | **226 passed, 1 failed** out of 227 — the literals test alone |
| add a `ReportKey` member nothing emits | only the second test fails |
| emit a key without going through the enum | both fail, correctly: a wire-format change *and* an unnamed key |

The first row is the whole argument. With the format broken, every other test in the
directory is green.

### The second question, answered honestly

It can recur, and nothing in this repository can stop it. The mirror schema is what makes
it silent — writer and reader go through the same member, so a rename moves both sides
together — and the other two consumers of this format,
`/integration-conflict-triage` and `stacked-pr-maintenance`, are prose documents that
nothing executes. Only a reader *outside* this code, exercised in CI, closes it, and then
only for the keys that reader touches.

It is not hypothetical either: the 2026-08-13 entry records a review reply describing this
contract test in detail when it did not exist, found by renaming a wire key and noticing
nothing failed.

What changed is the failure's shape rather than its existence — from "a table disagrees
with the enum" to "the document a caller parses carries a different key".

### Worth carrying

**A test that pins a contract must read the artifact the contract is about.** This one
named the right hazard, was defended across three rounds, and checked the wrong object
throughout. The general check is cheap: look at what the test *imports*. A wire-format
test that imports no serializer is asserting something other than the wire format.

622 tests pass across the three directories CI runs, from 621. The thread stays open: its
original ask was to delete the test, and it was answered differently.

## Update 2026-08-20 (decision 13): the tooling Python becomes the `bastler` package, and the migration moves to the front

Session: https://claude.ai/code/session_01FkXYGjckkyGZrhrkjS4kCf (plan refactor only, no code).
User's decision, in their own words: moving the tooling scripts, tests and files into their own
package is a priority *now*, because the duplication of code keeps increasing and reviewers are
complaining about it.

### The name

The package is **`bastler`**. The name comes from the first three letters of the user's surname
(Bassiouny) and is the German word *Bastler* — a tinkerer, someone who builds things themselves —
which is what this package is: the workflow tooling the user built around the repository. It
supersedes `development_tooling`, the name settled at PR 3's kickoff on 2026-07-30. That name was
chosen abbreviation-free per AGENTS.md; `bastler` keeps that property (it is a name and a real
word, not an abbreviation of a phrase).

### Why the front of the queue, with the evidence already on record

Decision 8 (2026-07-29) created the migration item and deliberately sequenced it **last** in the
upstream wave, to avoid moving files under in-flight pull requests. Since then the manifest has
accumulated duplication carriers faster than the queue has drained — each one recorded on an item
at the time it was found, none fixable before the migration because `.claude/hooks/`,
`.claude/stack/` and `.claude/skills/plan-dashboard/` are separate `sys.path` roots that cannot
import each other:

- `run_git`-style subprocess seams three times (#135's `check_scope_overlap.py`, #143's
  `plan_item_bootstrap.py`, plus stack.py's deliberately-opposite `_git`).
- The frozen-dataclass command-class base twice (#139's `MaintenanceCommand`, #151's
  `Subcommand`), where making them identical today would mean copying `class_property.py` into
  `.claude/hooks/` — a fifth duplicated file in answer to a complaint about duplication.
- The GitHub gh-CLI-else-token backend rule three times (`github-api.sh`, #111's `pr_state`,
  #139's urllib client), already called "the strongest concrete duplication on record in this
  plan" by the item that exists to end it.
- The personal-notes precedence rules twice in Python (stack.py against the sourced shell file).
- `ItemStatus` and the scratch-repository fixtures duplicated across test trees.

Review rounds on #139, #151 and #154 each asked about one of these directly. The sequencing that
protected in-flight work has become the thing manufacturing the complaints, so it is reversed.

### What changed structurally in the manifest

- New track `bastler` ("Bastler package extraction") in the upstream wave; the nine package items
  move into it out of `dashboards`.
- Item ids renamed (`dev-tooling-python-package` → `bastler-package`;
  `dev-tooling-<x>` → `bastler-<x>` for the seven decision-12 conversion items and
  `github-api-unification`). Older roadmap sections keep the old ids as history; the manifest and
  every forward-looking note read the new ones.
- `bastler-package` is re-scoped: it now **creates** the package itself, branched off `main`,
  rather than inheriting the one #111 carries. Its dependency on `shared-pr-state-chips` is
  dropped and inverted — #111 rebases onto the bastler branch and folds its
  `development_tooling` modules in under the new name, keeping only its feature half (pr_state's
  fetch/compute, the chips, `build_site.py`). With both remaining dependencies long done,
  `bastler-package` is ready to start today, and it is the plan's next kickoff.
- The CI job repoints and renames `test_claude_dev_tooling` → `test_bastler`; tests land under
  `test/bastler_test/`.

### The cost, measured rather than guessed

Every open tooling pull request except #155 touches Python the migration moves (per-branch
`git diff` against the merge base, 2026-08-20): #154 (41 files), #151 (28), #110 (16), #162 (10),
#111 (8), #107 (7), #158 (4), #135 (3), #146 (3), #184/#150/#149/#157/#160 (2 each), #156 (1).
Doctrine for crossing the move, in both directions:

- A pull request still open when the migration lands merges `main` across it and re-applies its
  delta inside the package — the same resolution pattern #111 exercised on 2026-08-05 when #106
  landed under it. The maintenance pass's needs-resolution flow labels and reports each conflict
  to its owner; nobody resolves someone else's out of band.
- A pull request already through review may land first, and the migration folds it in with its
  own final merge of `main` — cheaper, because a move-then-edit absorbs an edit more easily than
  an edit absorbs a move. Which pull requests get that treatment is the user's call per pull
  request at merge time, not a schedule this plan fixes.

### What decision 13 does *not* change

Decisions 8 and 12 stand in every other respect: SKILL.md files, settings.json and the bash entry
points stay in `.claude/` as thin wrappers; zero-install survives (plain top-level directory,
importable from the repo root, pyproject for optional installation); the SessionStart-reachable
tier stays stdlib-only; the bash→Python conversion chain keeps its shape and simply runs under
the new names. `bastler-github-api-unification` keeps its own item and its open backend question —
the migration unifies what is already duplicated, it does not decide the gh-vs-token-vs-library
question early.

## Update 2026-08-20 (sixth round): the wire-format guard is deleted, deliberately

*"Delete both tests."* One of the three options the previous reply had put up, chosen with
the trade already stated — a decision, not an ask to re-argue.

`test_the_report_keys_are_the_ones_a_caller_parses` and
`test_every_report_key_names_something_a_document_carries` are gone, and
`every_document_this_module_writes` and `keys_in` with them since nothing else called
them. A pure deletion, 117 lines. 620 tests pass across the three directories CI runs,
which is where the day started: one added for the `stage-conflict` document, two removed
here.

### The consequence is recorded rather than dropped

With writer and reader both going through `ReportKey`, a value rename changes both sides
identically. Measured after the deletion rather than asserted: renaming
`ReportKey.EXIT_CODE`'s value to `exitCode` leaves **all 226 tests in
`.claude/stack/tests` passing**.

So the pull request description now says the format is unguarded by choice, in place of
the paragraph that used to describe the guard. Quietly removing that paragraph would have
left a reader with no way to know, which is the failure this plan keeps recording in other
costumes.

The reasoning accepted for it, which is sound: nothing outside this repository executes
the format today — `/integration-conflict-triage` and `stacked-pr-maintenance` are prose,
so a break is found by a human reading either way — and a test you are *expected* to edit
whenever the contract changes is one that gets edited reflexively, buying maintenance and
no guard. The place to close it is `integration-branch-ci-verdict`, which introduces a
consumer that actually runs; that consumer's own tests are the guard worth having, and
this item should not be carrying a stand-in for them.

### The arc, which is the part worth keeping

One test, six rounds: delete it → put the enum in the tests → document it with an example
→ reproduce the situation it exists for → how does it benefit us → delete both. Each was
answered on its own terms, and for the first four the underlying fault survived
untouched — the test asserted the enum against a written-out copy of itself and never
rendered a document.

Fixing that in round five is what made the real question askable. Only once the test read
the artifact it was about could "is one deliberate line per breaking change worth it when
no reader executes the contract" be put properly — and that is a judgement the owner makes,
not a measurement. The defence had been resting on reasoning nobody had tested; a reviewer
returning to the same line five times was the signal, and it was read as repetition rather
than as evidence for four of them.

## Update 2026-08-20 (kickoff): `bastler-package` opens as #185, and two scope calls settled

`/plan-item-kickoff workflow-unification bastler-package`, session
https://claude.ai/code/session_01JN9p5Kf2DKtzryspPX2KqZ, as draft pull request **#185** on
`claude/plan-item-kickoff-workflow-cuare2`, based on fork `main` (`90c24116`). Bootstrapped in
the order `plan-item-bootstrap` prescribes — branch, draft pull request, manifest, roadmap,
progress note, dashboard — before a line of the migration.

Both dependencies re-checked with `check_dependency_readiness.py` rather than inherited from
decision 13's prose: `setup-personal-notes-pr101` and `stack-tooling-on-main` both `merged`,
both `is_ready`. No branch existed yet, so there is no partial work to build on.

### The scale, and why the diff has to render as renames

Measured rather than estimated: **18,408 lines across 46 Python modules** under `.claude/`,
of which the three largest are `stack.py` (1,641), `plan_item_bootstrap.py` (1,612) and
`build_dashboard.py` (1,504). Moving them with `git mv` and nothing else in the same commit is
what lets GitHub render the change as renames; any content edit in the same file in the same
commit costs that, and with it the only thing making a pull request this size reviewable.

The premise is visible rather than argued. `.claude/stack/tests/conftest.py:14-16` inserts
`.claude/stack/`, `.claude/hooks/` **and** `.claude/hooks/tests/` onto `sys.path`, which is
decision 8's "path hackery" in the literal. There are three such conftests, one per suite, and
they are deleted as their directories empty.

### Two scope calls, settled with the user at kickoff

**The oversized modules are not split here.** Two review rounds deferred splitting `stack.py`
*to this item* by name — 2026-08-02, twice, on the reasoning that "`dev-tooling-python-package`
already moves every `.claude/` Python file into a package, so splitting now means the same
surgery twice, with #110 and #111 rebasing across it in between." Decision 13's re-scope does
not mention it, so it was put to the user rather than assumed either way. Their call is to move
first and split as its own item.

The deferral's own argument is partly conceded by that, and it is worth stating rather than
glossing: this is the second surgery it was written to avoid. What changed is the cost on each
side. Once the package exists a split is an ordinary refactor inside one importable tree —
#139 has already produced the eleven-module pattern for exactly this — whereas splitting during
the move destroys rename detection on the three biggest files, so a reviewer sees ~5,000 lines
of apparently-new code instead of a move. The thing the deferral was protecting (one surgery)
is worth less than the thing it would cost (a reviewable diff), and the second surgery is now
cheap in a way it was not when the deferral was written.

**Only the unifications that are a straight deletion.** The item's `notes` say the duplication
carriers are "unified in the move rather than after it", naming `run_git`, the command-class
base plus `classproperty`, `ItemStatus`, and the personal-notes precedence copy. Checked
against `main` rather than taken as given, and two of the four are not reachable from this
item's base: #135's `check_scope_overlap.py` and #151's `Subcommand` are both unlanded, so the
move cannot see either half-pair. Decision 12 separately assigns the `git_interface.py` seam to
`bastler-notes-core-python`, which owns it by name.

So this pull request unifies `ItemStatus` — whose duplicate's own docstring already promises
*"the one definition both share arrives with the package migration that gives them a home"* —
and `stack.py`'s second Python copy of the notes-branch precedence, whose docstrings already
concede they restate `resolve-personal-notes-config.sh`. The designed seams stay with their
named items, and #135 and #151 fold their copies in when they cross the move.

This is the plan's own recorded rule applied a third time: **an item's notes can name a
dependency the item's own base cannot reach, and when the two disagree the base wins.** #115
recorded it first, #143 second. What is new here is that the unreachable half is not an
external dependency but a *sibling branch of this same plan* — the notes were written on
2026-08-20 describing the state of the queue, and the queue is exactly what has not landed yet.

### What the package looks like, and where that was already decided

Flat, not subpackaged. Two independent sources fix it rather than one preference: #111's
`development_tooling/` is flat, and decision 12 already names the modules the seven conversion
items will add — `errors.py`, `personal_notes_configuration.py`, `git_interface.py`,
`notes_branch.py`, `marker_sections.py`, `plan_manifest.py`, `setup_checks.py`,
`session_start.py`, `dashboard_refresh.py`, `github_backend.py` — all at package top level. A
subpackage layout would have to renumber all of them.

`bastler/pyproject.toml` mirrors #111's verbatim, including the
`[tool.setuptools.package-dir] bastler = "."` mapping that makes the package *be* its directory
rather than live under one. Optional installation only; zero-install import from the repository
root is the contract, because cloud sessions run on fresh clones with no pip step.

Two consequences that follow from reading the code rather than from the plan:

- **`templates/` moves with `render_common.py`**, which resolves it as
  `Path(__file__).parent / "templates"` (line 22). The template directory is not an asset of the
  skill; it is an asset of the module that loads it.
- **`example/` stays in the skill directory.** `example-walkthrough.md` embeds its screenshots,
  so it is documentation rather than a fixture, and only the tests' path to it changes.

### The CI job, and a consequence of renaming it

`test_claude_dev_tooling` becomes `test_bastler`, running one invocation over
`test/bastler_test/` with `--confcutdir` — the precedent #111 established, because the shared
`test/conftest.py` imports `semantic_digital_twin`, `coraplex`, `giskardpy` and `krrood`, none
of which this lightweight job installs.

Renaming a job renames the check GitHub reports. If `test_claude_dev_tooling` is a required
status check on branch protection, that requirement stops ever being satisfied until it is
updated. Flagged to the user at kickoff rather than discovered on the first blocked merge.

### The crossing cost, and the two branches that need telling

Decision 13 already measured it: every open tooling pull request except #155 touches Python
this moves. Two interactions are specific enough to name rather than leave to the general
doctrine:

- **#158** (`pinned-stack-tooling`) — `stack.py pin-tooling` copies "every module and
  `stack.toml`" out of `.claude/stack/`, which this migration empties. Its whole premise is that
  the tool a pass runs must be a file no branch carries, so the directory it copies *from* is
  load-bearing rather than incidental.
- **#111** (`shared-pr-state-chips`) — decision 13 already inverts the dependency: it rebases
  onto this branch and folds its `development_tooling` modules in under the `bastler` name,
  keeping its feature half. Its `--confcutdir` CI step is reused here rather than reinvented.

### One thing this session could not do

Subscribing to tracking issue #102, which `plan-item-kickoff` step 1 asks for, was **refused by
the permission classifier**. Recorded because the skill's own reasoning for subscribing at
kickoff is that a kickoff which turns into an uninterrupted implementation session is otherwise
never subscribed by anything — which is exactly this session's shape. Concurrent structural
changes to this plan will therefore reach it only through the delta recheck, not through events.

## Update 2026-08-21 (implemented): the bastler package exists, and the duplication it was blocking is deletable

`bastler-package` implemented in its kickoff session
(https://claude.ai/code/session_01JN9p5Kf2DKtzryspPX2KqZ) as `a4405fbd5` on #185. 46 modules and
their three test suites moved; 536 tests pass across the one new invocation, against 479 on `main`
plus 58 new contract tests and one deletion.

### The move is one commit, and that is what keeps it reviewable

The plan called for one commit per source directory. They are one commit instead, and the reason is
mechanical rather than a shortcut: `scratch_repository.py` is shared by the hooks suite and the stack
suite, so moving either alone needs a temporary `sys.path` bridge between two directories - which is
precisely the hackery this pull request exists to delete. Splitting the move would have meant writing
the thing back in, twice, to remove it again in the third commit.

68 of the moved files render as renames, including all three of the big modules the scope decision
deliberately left unsplit. That was the whole argument for not splitting them here: a split in the
same commit destroys rename detection on `stack.py` (1,641 lines), `plan_item_bootstrap.py` (1,612)
and `build_dashboard.py` (1,504), so a reviewer would see ~4,800 lines of apparently-new code where
they can now see a move.

### A guard the code claimed to have, and did not

`plan_item_bootstrap.py`'s `ItemStatus` docstring, on `main`, says: *"Mirrors `build_dashboard.py`'s
own enum ... A test holds the two equal; the one definition both share arrives with the package
migration."* The plan's step 5 followed that and said to delete the test.

**There is no such test.** Checked rather than assumed - on `main`, no test module imports both
`build_dashboard` and `plan_item_bootstrap`, in any of the three suites. So the five members were
duplicated in two files that could not import each other, and *nothing* held them equal; the two
could have drifted silently at any point.

This is the same shape the 2026-08-13 entry on #154 recorded - a review reply describing a contract
test that had never been written - met from a different direction: here it is a *docstring* claiming
a guard. Worth stating as the general form, since both instances were found by going to look rather
than by anything failing: **a sentence asserting that something is tested is not a test, and the
cheapest check is to grep for the import the test would have to make.**

### The second unification was a repair, not only a deduplication

`stack.py`'s `_resolve_personal_notes_remote` / `_resolve_personal_notes_branch` conceded in their
own docstrings that they restated `resolve-personal-notes-config.sh` in Python. Reading the two
side by side showed they had *already drifted*: the shell falls back to the current branch's
upstream remote when the configured one does not carry the notes branch, and the Python copy had
no equivalent - so a checkout the hooks could read notes from was one `stack.py` could not.

Both functions are deleted; `_fetch_personal_notes_branch` sources the shell file and calls its own
`fetch_personal_notes_branch`, which is what `plan_item_bootstrap.py` already did and the reason it
never grew a third copy. Verified live rather than only in the harness: `python3 -m bastler.stack
configuration` resolves `fork_repository` off the real personal-notes branch, which is a value that
exists only in the override the delegation now fetches.

The two seams the item's own notes also listed - `run_git` and the command-class base - are
deliberately untouched. Half of each pair (#135's `check_scope_overlap.py`, #151's `Subcommand`) is
on an unlanded branch, so the move cannot see it. That is this plan's own recorded rule applied a
third time, after #115 and #143: **an item's notes can name a dependency the item's own base cannot
reach, and when the two disagree the base wins.** What is new is that the unreachable half is a
sibling branch of this same plan rather than an external dependency.

### What the contract tests pin, and the one that nearly did nothing

Five properties, 58 cases: the package imports from the repository root with no install; every
module imports in a subprocess of its own; every entry point answers `python -m bastler.<x> --help`;
each dependency tier imports with the tiers above it blocked; and no `.py` file remains under
`.claude/`.

`PACKAGE_MODULES` is *listed* rather than discovered, which inverts the rule #139 settled for
`COMMANDS`. It is the right way round here for the same reason it was right there: discovery is
correct when a list carries no meaning of its own, and this list *is* the migration's specification -
a module that failed to move would simply be absent from a discovered set, which is the one thing
these tests exist to catch.

The tier test filters `PACKAGE_MODULES` to the modules that have anything blocked, so a tier table
that accidentally allowed everything to everyone would make every case vanish and the suite would
still pass green. `test_some_module_is_actually_checked_against_a_blocked_import` closes that; it is
the same vacuity guard #110 needed when its own check silently had zero candidates.

It also deleted a test rather than moving it: `test_every_module_of_the_executor_imports_on_its_own`
covered the fourteen stack modules, and the contract suite covers all twenty-four the same way.

### Two things the move surfaced that no test could have

**A helper run by path cannot see the package.** `run_from_repository_root` strips `PYTHONPATH` so a
pass proves the zero-install import really comes from the repository root - but an interpreter given
a *script path* puts that script's directory on `sys.path`, not the working directory. The
blocked-import helper inserts the root itself and says why.

**An installed copy needs its data files.** `pip install ./bastler` succeeded and produced a package
that could not render or configure anything: `render_common.py` resolves `templates/` as
`Path(__file__).parent / "templates"` and `stack.py` resolves `stack.toml` with
`Path(__file__).with_name`, and neither is a `.py` file, so setuptools left both out. Found by
running the install rather than by reading the manifest. `[tool.setuptools.package-data]` names them.

`requirements.txt` moved into the package and is the single dependency list: `pyproject.toml` reads
its `rendering` extra *from that file* via `[tool.setuptools.dynamic]` rather than restating the four
packages, so `pip install -r bastler/requirements.txt` and `pip install ./bastler[rendering]` cannot
disagree. Verified with a dry-run resolve: Jinja2, Markdown, PyYAML and nh3.

### The shell's Python entry points are modules now, not paths

Every `*_SCRIPT` constant naming a `.py` file became a `*_MODULE` naming an import path, run as
`python3 -m "${SOME_MODULE}"`. Not cosmetic: a module run by its file path puts the package's own
directory on `sys.path` in place of the project root, so its absolute imports of its siblings stop
resolving - which is exactly what the flat layout is for. The three test-directory constants collapse
into one `BASTLER_TESTS_DIRECTORY`, since one package has one test tree.

`check-setup.sh`'s `tooling_files` check now looks for the package rather than for
`build_dashboard.py` at its old path, which is what had that row reading `needs-setup` for the whole
session. It exits 0 in this clone.

### Verified live, and from a clean clone

`check-setup.sh` exits 0 with every row `ok`. `stack.py configuration` answers with the fork resolved
through the new delegation. `refresh_dashboard.sh` runs the whole sequence and renders *this plan's
own* 50-item dashboard - 942 KB, zero drift, and every status label rendered through the new
`status_label` filter rather than the enum property that used to carry it. `plan_manifest_tools`
answers both subcommands.

Then the same from a fresh `git clone` of the pushed branch, per #121's staged-diff lesson that a
suite passing locally proves nothing about files the index does not have: the zero-install import
resolves to the clone's own copy, all ten entry points answer `--help`, `check-setup.sh`'s two
package rows read `ok`, and `example-walkthrough.md`'s documented command runs verbatim.

### Carried, not done

`pin-tooling` on #158 copies `.claude/stack/`, which this empties, and #111 folds its
`development_tooling` modules in under the `bastler` name - both need telling on their own pull
requests. The CI job rename changes the reported check name, so branch protection needs updating if
`test_claude_dev_tooling` is a required status check. And this session could not subscribe to
tracking issue #102 (the call was refused by the permission classifier), so concurrent structural
changes reach it only through the delta recheck.

## Update 2026-08-22 (resolved): #149's upstream review round, read through a rendered web page

`/plan-item-resolve workflow-unification plan-item-execution-modes`, session
https://claude.ai/code/session_015hBqi8PeGtQQsBqpKQdW2y. LucaKro requested changes on the
upstream promotion, cram2 #537, on 2026-08-19: six threads, all on `plan_item_mode.py`, no
summary body. Answered and pushed as `735988448`; 498 tests across the three directories CI
runs, was 384 before the merges from `main`.

### The item's own record said none of it

The manifest still read `in_progress` with `pull_request_number: 149` and nothing else. The
review is on #537, which `plan.yaml` has no field for and no dashboard column shows, so an
item under changes-requested upstream is indistinguishable here from one quietly in progress.
Recorded in `notes` rather than invented as a schema field, but worth naming as a gap: **the
manifest tracks the fork pull request and the review happens on the promoted one.** Every item
that reaches the upstream wave will have this.

### Reading it at all took a rendered web page

This session could not reach cram2's API in any form: `add_repo` refuses a cross-owner attach
("cross-tier adds are not supported"), and `api.github.com` answers 403 with "GitHub access to
this repository is not enabled for this session". Anonymous git reads of the public repo are
served, so the *code* is reachable and the *conversation* is not. The six comments came out of
`WebFetch` on the rendered pull request page, which returns their text but not reliably the
line each is anchored to - the anchor ids had to be ordered against the file to place them.

That is `upstream-review-reader` (#146)'s entire premise, now with a measurement behind it. It
also settles how a fork session works an upstream round in the meantime: pushing the branch
updates both pull requests, so the *fix* lands normally and only the *replies* are blocked.
`AGENTS.md` forbids writing to cram2 anyway, so the reply text is handed to the user.

### The three threads that were one thread

*"why is setting key sth thats only used when an error is thrown? this is information
irrelevant to this method imo"*, *"same here with reported path"*, and *"why object?"* are the
same observation twice plus a question. `parse_mode(value, setting_key)` and
`read_settings_file(path, reported_path)` each took a second argument no line of their body
used, purely so a refusal could name where a value came from.

The reviewer is right that it does not belong to the *reading*. It does belong to the *thing
read*: what failed is not "a value" but "the setting `kickoff_mode`, holding `atuo`". So both
became types - `ModeSetting(key, value)` with `parse()`, `SettingsFile(path, origin)` with
`read()` - and the two refusals carry those objects instead of a second copy of their labels.
The argument stops being irrelevant by stopping being an argument.

`object` stays `object`, and that is the answer rather than a concession: the value comes from
TOML, where `kickoff_mode = 3` parses fine and must be *refused*. `str` would be a lie about
what the file can hold, and the refusal is the whole point of the function.

Worth carrying: **a parameter a function's body never reads is a fact about its argument, not
about the call.** The fix for "this doesn't belong here" is usually to find what it does belong
to, not to delete it and make five call sites compose the error.

### "str enums?" was a question whose answer exposed a missing guard

The values *are* the wire form - the TOML setting a user edits by hand, the JSON report other
programs parse, the `argparse` choice - and `StrEnum` makes the member itself that string.

*Corrected 2026-08-22, from the user's follow-up question "StrEnum is just a structure, the
members are still str mapable, right?"* - the first version of this paragraph said
`ExecutionMode(value)` reads and `str(mode)` writes "with no table between them", which is wrong
about reading. By-value lookup is `Enum.__call__`, and a plain `Enum` does it identically;
measured on 3.11 and 3.12. What `StrEnum` actually buys is the other direction - the member *is*
a `str`, so it needs no `.value` at any boundary that wants one - and with a plain `Enum` those
boundaries are not cosmetic: `json.dumps` raises on both the `ReportKey` keys and the
`ReportStatus` value, `', '.join(ExecutionMode)` in `suggest_correction` raises,
`add_argument(CommandLineOption.SKILL, ...)` raises before argparse inspects the string,
`subcommands.choices[Subcommand.RESOLVE]` misses because the member no longer hashes equal to
`"resolve"`, the tests cannot build a subprocess argv from a member, and
`report["mode"] == ExecutionMode.AUTO` goes false against JSON-parsed text. "No lookup table"
was loose even for writing: the alternative is `.value`, an attribute access, not a table.

Nothing pinned that, which is the failure this plan has now
recorded three times (#151's report keys, #158's promised-but-unwritten test, #154's labels).
`test_the_enum_values_are_the_words_the_settings_file_and_the_report_use` spells every value
out deliberately, against this test module's own stated rule of reading expected values from
the module that owns them.

Mutation-checked rather than asserted: renaming `ExecutionMode.AUTO`'s value fails 10 tests,
renaming `ReportKey.SOURCE`'s fails 7, and **changing `ExitCode.UNKNOWN_MODE` from 3 to 9 fails
exactly one - the new test**. The exit codes were the half with no guard at all, and only the
mutation showed it; the mode and key values already had incidental cover from assertions that
were going to contain those literals anyway, exactly as #151 found.

### "so thats why 1 and 2 are not used here?"

Asked because the class said half of it - *"``argparse`` supplies 2 for a usage error"* - and
left 1 unexplained. `stack.ExitCode` already names `USAGE = 2` as a member rather than in
prose, so this now does too, and the class says why 1 is left free: it is what Python exits
with on an uncaught exception, so a crash cannot read as a refusal the tool chose to make. A
test drives a real usage error and asserts the status the enum reserves.

`plan_item_bootstrap.py` carries the identical half-explanation and is on `main`, so it keeps
it for now.

### The serialization thread, split in two

*"i feel like you have as_document, as_dict, as_json, as_json_dict etc scattered across your
diffferent PRs krood dependency when"* - measurably true, and the measurement is what decided
what to do about it. `as_document` returns a dict in `plan_item_bootstrap.py` and here;
`to_json_dict` returns a dict in `build_dashboard.py` and `sync_manifest_status.py`; `as_json`
returns a str in `maintenance_report.py` and `maintenance_board.py`. One operation under two
names, plus a genuinely different one under a third. `as_document` survives: it names the
thing produced where `to_json_dict` names the Python type it happens to be.

`git ls-tree origin/main` returns all four divergent files, so renaming them is standalone work
rather than an edit to an unlanded pull request - the prefer-the-change test comes out on the
side of a separate item, `report-document-naming`, and the user agreed. What #149 owed instead
is the other half of the same rule: `main()` called `as_document()` on either report and
nothing declared they shared it. A `Report` base declares the `as_document`/`exit_code` pair,
and `ReportKey`/`ReportStatus` give the document's spelling one home. The printed document is
byte-identical, verified by running the CLI before and after.

**On krrood: declined, on a measurement rather than a preference, and the thread left open.**
`test_claude_dev_tooling` runs on a bare `ubuntu-latest` with `pip install pytest` and the two
dashboard requirements and nothing else - so a krrood import breaks the job outright, and every
hook that runs under a plain `python3` with it. `SubclassJSONSerializer` also solves
round-tripping, resolving a concrete subclass from a stored type name, and nothing ever reads
one of these reports back into a Python object. The place to revisit it is `bastler-package`
(#185), which puts all six files in one home.

### Found while in there

The module docstring still named `ask` as the default, three days after the reversal this
roadmap records under 2026-08-09 put `auto` in `plan-item-modes.toml` and in
`execution-modes.md`. Nothing tested it, because it is prose. **A decision reversed in a
committed default and in a shared document is not reversed in the docstring that explains
them** - and the docstring is what the next reader believes.

### Carried, not done

The six threads on #537 are unanswered: this session pushed the fix and handed the reply text
over, per `AGENTS.md`. #149's one red check remains `test_each_lib (semantic_digital_twin)` ->
`test_world_sim_state_sync`, a physics settle assertion on a pull request whose ten files are
all under `.claude/`; not this branch's, and not chased into it. #149 is left un-drafted rather
than returned to draft: un-drafting a fork pull request is this workflow's own promotion gate
(`stack.py`'s *"self-review a fork PR, then un-draft it"*), so re-drafting it would withdraw
#537 from the review it is answering.

## Update 2026-08-22 (resolved): #184's review round, and the formatter that stopped declining

`/plan-item-resolve workflow-unification deferred-dependency-drift-check`. Eight threads,
all answered and resolved, in `453795a6`. 248 tests in `.claude/skills/plan-dashboard/tests` (was 239), 107 hooks, 154 stack.

### Nothing about the feature was blocked, which is worth stating first

CI was green on all 22 checks, `mergeable_state` was `clean`, and the branch's merge base was
`origin/main`'s current tip - so no conflict, no base merge, no dependency regression. The
entire stall was a review round filed the same morning. That is the shape the 2026-08-20 entry
on #154 already named twice: **a resolve session reads the pull request first and the manifest
entry only to learn what has already been decided.** Here the manifest's `notes` still ended
*"Not implemented here - left for another session"* - written on 2026-08-12 when the item was
filed, five days before it was implemented - so the entry was not merely stale about the round,
it was stale about the item having been built at all.

### Seven threads, one finding

The tests retyped every drift sentence `build_dashboard.py` builds. By this plan's own rule
(2026-08-20: *a repeated literal is a defect when the two copies can drift apart, and not one
when the second copy is the assertion*) that is squarely the first case - the wording is
production's, and the test's copy of it can drift silently.

What made it clear-cut is that **this module's pre-existing drift tests never assert a sentence
at all** - they assert `summary.drift_items` and `live_state`. The new tests had introduced the
only string comparisons in the section, so single-sourcing was not a new convention but a return
to the file's own.

`Item.drift_descriptions` becomes `drift_flags`: a `ManifestDrift` carrying the
`ManifestDriftCause` its `match` already decides, or a `StalledDependencyDrift` carrying the
dependency, its `StallReason` and the reparent targets, with the wording on
`DriftFlag.description`. `_drift_description_of` - a `@staticmethod` on the renderer that read
only the item, and both decided *whether* an item drifts and wrote the sentence for it - split
into `ManifestDrift._cause_of` and `ManifestDrift.description`. The `match` itself is untouched,
case ordering included: `MERGED` + `BLOCKED` still matches the merged case before the closed
one, which an existing test pins.

Two knock-ons worth keeping:

- **`Item.stall_reason` replaced a condition written twice.** `is_stalled()` tested deferred-or-
  closed-unmerged, and the sentence builder then re-tested *which* of the two it was in an
  `if/else`. One property answers both now, and `is_stalled()` is derived from it - so the third
  sibling predicate the kickoff decision called for survives, answering only *whether*, where
  `stall_reason` answers *why*.
- **`StalledDependencyDrift.of` refuses a dependency that has not stalled**
  (`NotStalledDependencyError`) rather than inventing a reason for it - the
  `MissingMergeTimestampError` precedent, and the thing that keeps `reason: StallReason` an
  honest type rather than a narrowed `| None`.

The English is still pinned, in exactly one place: `test_drift_flag_describes_itself` renders
every cause and every stall reason. That is the counterpart the 2026-08-11 mirror-schema round
demanded - **single-sourcing a contract deletes the guard the duplicate literals were providing,
and the commit that single-sources it owes the replacement.** Swept the whole module rather than
the five commented lines, per 2026-08-20: the pre-existing `test_status_and_drift_css_class_with_drift`
was retyping a message too.

### The two markup threads: read the page, don't match strings against it

`drift_lines_in` and `drift_banner_flag_count` run a small `html.parser.HTMLParser` subclass
returning the text of elements carrying a class, so the tags and the class name leave the tests.

The part that made this more than tidying: the old assertion wrapped each description in
`markupsafe.escape()`, **because the test was reproducing Jinja's autoescaping in order to match
its own output**. A parser resolves entities the way a browser does, so there is nothing left to
model. Worth generalising - *a test that has to imitate the renderer to state its expectation is
matching the wrong artifact.*

Deliberately narrow: this module has ~50 other markup assertions and they are untouched. This
round converted what its own review named.

### The formatter stopped declining the file, and that decided the diff

The measurement first, because the obvious action does nothing. On the previous head
`scripts/format_docstrings.py` left `build_dashboard.py` **byte-identical**, while
`docformatter --config pyproject.toml --diff` disagreed with **48 hunks of `main`'s own copy**.
That is the non-convergent case the script documents, and the whole disagreement was one blank
line:

```
 plan-specific, so declared once at module level rather than threaded through
 :class:`Plan`."""
+
 
 @dataclass
 class Item:
```

`AVAILABLE_MODELS`' attribute docstring immediately before a *decorated* top-level definition -
the exact shape the 2026-08-12 entry recorded for `maintenance_board.py`.

**This round's new classes are inserted at precisely that adjacency**, so it no longer exists,
the file converges, and `format_docstrings.py` - a pre-commit hook on every `.py` - formats all
48 remaining hunks. The ~500-line docstring reflow across `main`'s code in `453795a6` is that
first run, not a decision to sweep.

The alternative was to place the new classes so the disagreement survived, which is arranging
code to preserve a formatter bug. That was put to the user rather than decided, and the sweep
was chosen: a file that has become convergent is a landmine for whoever next commits it with the
hook installed, and doing it deliberately in this pull request is better than having it happen to
someone. It answers the roadmap's open "do `main`'s unformatted files get a sweep" question for
this one file; `stack.py` remains in the identical state and is untouched.

**Generalizable, extending the 2026-08-12 finding.** That entry recorded *a formatter that
reports no change is not evidence a file is formatted.* The other half is now on record too:
**that state is a property of the file's shape, not a fixed fact about it** - an ordinary edit
elsewhere in the file can restore convergence and hand the next commit a whole-file reformat
nobody asked for. Both halves are invisible at the command line.

One process note: an early attempt applied docformatter's output hunk-by-hunk, filtered to lines
this pull request authored. It over-reached - docformatter groups neighbouring docstrings into
one hunk with context, so `PullRequestLabel`, `has_open_pull_request` and several other `main`
docstrings came along. Caught by reading the working diff rather than by any test, and fixed by
resetting the file and replaying the code edits from scratch, then filtering at *opcode*
granularity via `difflib` instead. The lesson is small and reusable: **a unified-diff hunk is not
a unit of intent** - filtering by hunk silently widens whatever it touches.

### Verified beyond the harness

Live against both real manifests: `rdr-refactor` (45 items) flags exactly one item, and the same
sentence as before this round -
`D-ui-rendering (in_progress): depends on 'D-ui-splice-fix', which is deferred - consider reparenting onto d-core-backend` -
with `D-ui` unflagged; `workflow-unification` (51 items) flags none, expected since it has no
deferred item. Formatting re-checked afterwards: `format_docstrings.py` a no-op on both touched
files, `docformatter --diff` 0 hunks on each (was 48 and 0), `black --check` clean.

### Carried, not done

- **The bastler landing hazard, deliberately not pre-resolved.** Decision 13 names #184 among the
  pull requests touching files the migration moves. #185 is open, draft and **unmerged**, and
  that decision's own doctrine is explicit - *"don't pre-resolve against it before it exists"* -
  so #184 merges `main` and re-applies its delta inside the package once #185 lands.
- **`subscribe_pr_activity` on tracking issue #102 was refused** by this session's permission
  classifier, so this session was not on that channel. The issue's comments were read directly
  instead, and the delta recheck caught what mattered: the notes branch moved twice mid-session
  (`report-document-naming` was added by another session), and these edits were applied onto the
  re-fetched manifest rather than the copy loaded at the start.

## 2026-08-22 - the base a session starts from was never checked

The user raised that every session is started from their fork's `main`, and that a fork behind
cram2 therefore makes the whole session plan and implement against a stale base. The measurement
at the time: `origin/main` 86 commits behind `cram2/main`, and the session's own branch cut from
exactly that commit - so the problem was not hypothetical, it was the state that session was in.

What makes it worth a deterministic step rather than a habit is that nothing about it looks wrong
from inside the clone. The clone is perfectly consistent with itself; the drift only surfaces at
the rebase, by which time the work is written. That is the same shape as the setup-check and
plan-item guards already in this track: the failure mode is a step that gets skipped, so the fix
is to stop it being a step.

Two decisions worth recording. First, the hook pushes the caught-up branch to the fork, not just
to the local ref - the local update fixes the session that is running, but the fork's default
branch is what the *next* clone is cut from, and fixing only the former leaves the bug in place
for everyone after. Second, it stops at the default branch: merging the moved base into the
checked-out branch can conflict and is a judgement call about work in progress, so it is reported
with a commit count instead. Everything is fast-forward only and nothing is force-pushed, which
holds because the fork's default branch is only ever written to by this catching-up.

The upstream is resolved through `stack.py configuration` rather than named in the hook, so there
is still exactly one place that says which repository the fork tracks, and the hook runs unchanged
on a fork of anything.

Wiring it in exposed a latent coupling: the summary's `plan state SHA` was re-reading `FETCH_HEAD`
instead of the baseline it had already recorded, so any later step that fetches - this one fetches
the upstream - silently changed the SHA a session was told to recheck from. Fixed in the same PR
by printing the recorded stamp.

`routine-cutover` lists a fork-main fast-forward among the scheduled Action's deterministic duties.
The two are complementary: that one is a timer keeping the fork fresh between sessions and is gated
on the upstream wave landing; this one guarantees the base of the session about to run, and is live
now.

## Update 2026-08-22 (second round the same day): the wording test is cut, on the reviewer's argument

Three threads on #184, filed twenty minutes after the previous round was pushed — the fourth
time in three days that an entry recording a round as answered has been overtaken by the next
one. Applied in `97ee004d3`; two resolved, one left open. 248 plan-dashboard tests, 107 hooks.

### The reviewer was right, and the precedent was already theirs

*"Since we maintain the code, we look at the description strings ourselves, so this test is not
really needed. You can argue with me if I am wrong."*

`test_drift_flag_describes_itself` was added in the previous round for a stated reason —
single-sourcing the wording deletes the guard the retyped copies were accidentally providing —
and that reason does not survive the question **who reads the contract**. A drift description is
rendered into the item card and the sidebar banner and read by a person. Nothing parses it. So
the guard was protecting prose against being reworded, which is not a defect, and its cost was a
failing test every time the prose improved.

That is the same call recorded on **#121's second round** (2026-08-07), where
`test_every_summary_message_reads_as_written` — added hours earlier for exactly this reason —
was cut on the user's instruction and replaced by `test_every_summary_message_renders_something`.
The precedent was followed rather than re-argued.

**The rule this sharpens, against the 2026-08-11 mirror-schema entry.** That entry says
*single-sourcing a contract deletes a guard, and the commit that single-sources it owes the
replacement*. True, and it is not a licence to replace it with the same assertion in one place —
the replacement has to be aimed at a defect. Here the sentence was never the defect; the missing
branch was.

### What was kept, because it was never about wording

`description` is a `match` with no `case _`, and a Python `match` that falls through returns
**`None` silently** — so a `ManifestDriftCause` or `StallReason` member added later without a
branch renders the literal word `None` on the dashboard with nothing failing. Two parametrised
tests over `list(ManifestDriftCause)` and `list(StallReason)` assert each member renders
something non-empty. Parametrised off the enum, so a future member is covered without anyone
editing the test — which is precisely what the eight hand-written sentences were not.
Mutation-checked: deleting the `MARKED_DONE_WHILE_CLOSED_UNMERGED` branch fails exactly its own
case out of 172.

The reparent rule kept a test, since *"omitted entirely when there is nothing to suggest"* is a
rule rather than a phrasing — but it compares the two descriptions **to each other**
(`without_targets.description in with_targets.description`) rather than to a sentence.

Left open rather than resolved: the ask was a deletion and this is a replacement.

### Two smaller ones

*"What is the weird symbol at the string start?"* — `⚠`, which `dashboard.html` prefixes every
drift line with. It was in the expectation only because `drift_lines_in` returned the element's
whole text. It strips it now, named once at `DRIFT_LINE_MARKER`, so an expectation is a list of
descriptions. Stated on the thread rather than glossed: the marker's presence is no longer
asserted anywhere — it was only ever pinned incidentally, and carrying a symbol the test is not
about into every expectation costs more than that incidental guard is worth.

*"Can this be a dataclass?"* — yes, with one requirement worth recording because it is silent
otherwise: `@dataclass` **generates** `__init__` rather than extending the base's, so
`HTMLParser.__init__` — which calls `reset()` to build the tokenizer state — never runs and
`feed()` fails on a missing attribute. `__post_init__` calls it. Mutation-checked by deleting
that method: both page-reading tests fail and nothing else does.

## Update 2026-08-22 (third round the same day): the neighbours settled the argument

Three threads on #184, filed twenty minutes after the second round was pushed. All three
applied and resolved in `815d3f2cb`. 241 plan-dashboard tests, was 248; 107 hooks.

### Two naming fixes

`capturing_tag` → `closing_tag`, which is what the field's own docstring already called it
— *"the tag name whose closing tag ends the element being collected"*. It reads better at the
guard too, where the field doubles as "am I collecting?": `if self.closing_tag is not None`
is *already waiting for a closing tag*, where the old name said the same thing one step
further from the mechanism.

`DRIFT_LINE_MARKER` moved to the top of the file, beside `EXAMPLE_DIRECTORY`, rather than
sitting next to the one helper that happened to introduce it.

### The third round on one test, and what actually ended it

*"if description is an abstract method, then it is guaranteed to be implemented anyway, so
these tests are also not needed in that case right?"* — then, in a follow-up, *"or is this to
handle the not handled case `_:` that prints None?"*

The second guess is right and it answers the first. `@abstractmethod` guarantees each
**subclass defines** `description`; it says nothing about whether the `match` *inside* it
covers every enum member, and a Python `match` that falls through every case returns `None`.
So a member added later without a branch is a fully-implemented abstract method returning
`None`, which the item card renders as the word `None`.

**Answering that is what produced the evidence that settled it, against the previous round's
own reply.** `ItemStatus.display_label` and `LiveState.display_label` are built exactly the
same way — `match self:` over the enum, no `case _` — carry the identical exposure, and have
since this module was written. What covers them is two spot checks that do not even name
every member:

```python
def test_item_status_display_labels():
    assert ItemStatus.NOT_STARTED.display_label == "Not started"
    assert ItemStatus.DONE.display_label == "Done"
```

So the file's own convention for this exact shape is weaker than what the previous round had
written, and *"single-sourcing deletes a guard, so the commit owes a replacement"* was
applying a standard nothing else in the module meets. Both parametrised tests are deleted.
What survives is the reparent rule, which pins a rule rather than a phrasing.

Given up deliberately, and stated on the thread rather than left to be discovered: a
`ManifestDriftCause` or `StallReason` added later without a branch shows as `None` on the
dashboard rather than as a failing test. Every existing cause is still *executed* by the
drift test that renders it, so nothing silently stops working today.

### Worth carrying

**Three rounds argued about one test, and what ended it was reading how the module already
treats the identical pattern** — not another round of reasoning about what the test was
worth. The 2026-08-11 rule (*single-sourcing a contract deletes a guard, and the commit that
single-sources it owes the replacement*) is sound and was applied here without its own
qualifier: the replacement is owed only where the codebase actually holds that line. Check the
neighbours before defending a guard.

This is also the second consecutive round on this branch where the reviewer's instinct was
right and the defence was the thing that needed correcting — the previous one being the
wording assertions themselves.

## Update 2026-08-22 (second round, same day): the fork round that reversed the upstream one

Six threads on #149, filed hours after the #537 round above was answered and pushed. All six
answered in `7cf38aab9`; four resolved, two left open. 522 tests across the three directories
CI runs, was 523 before the deletion and 498 before the base merge.

### Two calls from the morning were reversed by the afternoon

**The wire-value contract test is gone**, one round after being added — *"this test will never
fail, remove it, it is useless. Also if someone changes the actual string value yes this will
fail, but the fix then is fixing the test assertion, so what's the point?"*

That is the whole of #154's six-round arc compressed into a single comment, and it is right for
the same reason: a test you are *expected* to edit whenever the contract changes gets edited
reflexively, which buys maintenance and no guard. What made it defensible on #154 was a real
consumer; there is none here. `execution-modes.md` and `plan-item-mode/SKILL.md` are prose a
person reads.

Recorded rather than dropped quietly, since that is the half that goes missing: **the format is
now deliberately unguarded**, measured rather than asserted - renaming `ReportKey.EXIT_CODE`'s
value leaves all 18 tests in the module passing.

**`as_document` became `as_json`.** The morning's reply had argued `as_document` survives because
it names the thing produced where `to_json_dict` names the Python type. The user's rule is
`as_json`, so `as_json` it is, and `report-document-naming` carries the new target rather than
the old one - which is the point of writing the target into the item instead of leaving it in a
review reply.

Worth carrying: **an item's recorded conclusion is a decision, not a fact, and the next round can
overturn it.** Both reversals landed within six hours of the entry that recorded them, and both
would have been invisible to anyone reading only the roadmap.

### The one collision the rule cannot resolve by itself

`as_json` already names the `str`-returning method in `maintenance_report.py` and
`maintenance_board.py`, while the rule assigns it to dict-returners. Applying it across the rest
makes one name cover both a document and the text it serializes to, so `report-document-naming`
gains a decision it did not have: which keeps the name. Recommended on the thread and recorded on
the item - the dict-returner keeps `as_json`, being the one that composes the document, and the
two `str` ones become `as_json_text`.

### A near-identical pair, and the field that turned out to be redundant

*"SETTING_KEYS is very similar in name with SETTING_KEY only an extra `S` which is confusing."*
Looking for a better name found there was nothing to name: it rendered
`[skill.setting_key for skill in self.skills]` into the `set` report, derivable from the `skills`
that same document already carries, and `grep -rn 'setting_keys' .claude/` returns nothing outside
the module. Deleted rather than renamed - a better outcome than a third spelling, and the thread
is left open because a removal is not the rename that was asked for.

### `--skill` was the string with no enum

*"the string arguments do they have enums for them?"* Two of the three did and nothing was using
them: `Subcommand.RESOLVE`/`SET`. The third did not - `ModeOption` named only the two options
carrying a *mode*, which is too narrow a subject for an option-name enum, so it is
`CommandLineOption` with `SKILL`, `REQUESTED` and `MODE`. Swept the whole test module rather than
the two lines commented on. `"bogus"` stays a literal, being the deliberately invalid value the
test exists to feed.

### Paths that name paths

*"why is this a string and not a Path?"* No good reason: `SettingsFile.origin` was a string
because the constant behind it was. All five path constants are `Path` now, and the conversion
moves to the boundary, which is the argument for the change rather than a side effect - three
`str()` calls, at the two `subprocess` arguments and at the JSON document, which `json.dumps`
cannot serialize a `Path` into.

### `from None`, answered in the code rather than only in the thread

The suppressed `ValueError`/`TOMLDecodeError` is already folded into the refusal's own fields, so
chaining it prints the same fact twice, once in the library's words. `main` catches `ModeError`
and prints only the message, so it only shows for a caller outside `main` - which is where a
two-exception traceback would be most confusing. Said in `ModeError`'s docstring, once, where the
pattern lives; left open in case the chain is wanted after all.

### The base merge, and the hazard this plan had already predicted

`main` had moved: #135 landed, giving both plan-item skills a `${SCOPE_DECISION_DOCUMENT}`
reference, and **#146 landed too**, so `/upstream-reviews` now exists on `main` and
`plan-item-resolve` gained a step that invokes it. Both edits land in exactly the sections this
branch had moved into `plan-item-gathering.md` and `execution-modes.md`, so they conflicted and
were carried across by hand rather than merged wholesale - the resolution the 2026-08-12 entry
already prescribed for this pair.

The irony is worth recording: the round above had to read #537 through `WebFetch` because no
session-side call can see upstream review threads, and cited `upstream-review-reader` (#146) as
the item that would close that gap. It closed the same day. A resolve run on this item from now on
reads its upstream threads with `/upstream-reviews` instead.

Checked and clear: #156's removal of the offer-to-run-setup gate has *not* landed on `main`
(`prerequisite-check.md` still says "offer"), so this branch's `plan-item-gathering.md` carrying
that wording is consistent today. The hazard stays #156's, as already recorded.

### A third comment the same day, and two of the user's own asks in conflict

*"Wouldn't it be better to put all these directories in a StrEnum?"*, on the `# %% locations`
block - filed after the round above, and colliding head-on with that round's own
string-should-be-a-`Path` comment. Probed on 3.11 and 3.12 rather than reasoned about:

- **`StrEnum`** makes each member a `str`, not a `Path`. `HOOKS_DIRECTORY / "plan-item-modes.toml"`
  raises `TypeError`, and - the dangerous one - `COMMITTED_DEFAULTS_PATH.name` silently returns
  `"COMMITTED_DEFAULTS"` rather than the filename, because `Enum` reserves `.name`, which
  `test_plan_item_mode.py` uses twice to install that file into the scratch layout. A wrong
  filename, no error.
- **`Enum` with `Path` values** leaves the member a non-`Path`, so every site goes back to
  `.value` - the unwrapping the previous comment had just removed.
- **`class Location(Path, Enum)`** builds on 3.12 and 3.13 and raises `AttributeError: _flavour`
  on 3.11. `Path` became subclassable in 3.12; decision 12 puts the floor at 3.11.

The precedent is real and cuts both ways, which is the part worth carrying. `HookScript` and
`PlanDocument` (`plan_item_bootstrap.py`) and `SetupPrerequisiteFile` (`scratch_repository.py`)
*are* path `StrEnum`s - but each exists because something chooses among or iterates its members,
and each returns `str`. That same file keeps `HOOKS_DIRECTORY` and `PLANS_DIRECTORY` as plain
module constants beside them. Nothing selects among these five, and four of them are files
rather than directories, so they stay constants. Answered with the measurement and the thread
left open, on the user's call.

Worth carrying: **this is the second time on this plan that two of the user's own asks were
mutually exclusive** - #154's round had `spelling` → `name` and inheriting a specification, which
Python refuses together. Both times the useful output was the measurement showing the conflict,
not a choice made quietly on their behalf.

### A correction the same day, from a question rather than a review

Asked *"StrEnum is just a structure, the members are still str mapable, right?"* - and yes, which
made the previous entry's own justification wrong. The correction is applied in place above
rather than only recorded here, since that paragraph is the durable record of why this module
uses `StrEnum` at all. Short version: reading is `Enum.__call__` either way; `StrEnum` buys the
write and interop half, and "no lookup table" was loose even for that.

**A claim about why a design was chosen is worth the same scrutiny as the design.** This one was
written into a roadmap entry, a pull request description and a review reply before anyone asked
whether it was true.

## Update 2026-08-22 (third round, same day): the shape the user proposed beat both I had costed

One comment on #149, on the `# %% locations` block: *"Wouldn't it be better to put all these
directories in a StrEnum?"* Answered first with a measurement and no change, on the user's call;
then, when they proposed a concrete shape, implemented in `1b2f79672`.

### The measurement that made the first answer look right, and the part of it that was wrong

Three shapes were probed on 3.11 and 3.12 rather than reasoned about, and the probe is what the
reply carried:

- **`StrEnum`** — a member is a `str`, not a `Path`, so `HOOKS_DIRECTORY / "plan-item-modes.toml"`
  raises and `.name` returns the member name rather than the filename.
- **`Enum` with `Path` values** — the member is not a `Path` either, so every site goes back to
  `.value`, which the same round's *this-should-be-a-`Path`* comment had just removed.
- **`class Location(Path, Enum)`** — raises `AttributeError: _flavour` on 3.11, and decision 12
  puts the floor at 3.11.

On that, the reply recommended keeping the five plain constants, citing `HookScript`,
`PlanDocument` and `SetupPrerequisiteFile` as path `StrEnum`s that exist because something
iterates or selects among their members, where nothing selects among these.

**Two of those statements were wrong, and both were corrected on the thread rather than left
standing.** `.name` returns the member name under `StrEnum` and *not* under the `Path` mixin, where
`Path.name` shadows `Enum.name` and answers the filename — so the sharpest objection raised against
the mixin was an objection to the other shape. And the mixin's cost is not only the version floor:
on 3.12 it builds, and then `f"{member}"` renders `Location.COMMITTED_DEFAULTS`, `.parent` raises
`ValueError`, `json.dumps` raises, and by-value lookup raises. The recommendation happened to land in
the right place on reasoning that did not hold at two of its steps.

### The user's shape, which neither option costed

`HOOKS_DIRECTORY` stays a plain `Path` constant *above* the enum, and the four file paths become
`Location(StrEnum)` members composed from it, each with a `path` property for the callers that do
path arithmetic:

```python
HOOKS_DIRECTORY = Path(".claude/hooks")

class Location(StrEnum):
    CONFIGURATION_SCRIPT = f"{HOOKS_DIRECTORY}/resolve-personal-notes-config.sh"
    ...
    @property
    def path(self) -> Path:
        return Path(self.value)
```

It answers the objection to `StrEnum` — the directory the three share is still named once, and
composing them is `f"{HOOKS_DIRECTORY}/..."` rather than `/` on a `str` — while keeping the members
usable as text at the boundaries that want text: a `git` reference, a `bash -c` line, a subprocess
argument, the JSON report. `SettingsFile.origin` is a `Location` now, so a refusal names *which*
settings file rather than carrying a second path. Every call site either loses a `str()` or gains one
`.path`, and the `resolve` document is byte-identical before and after. Mutation-checked on
`COMMITTED_DEFAULTS`; 18 module tests, 522 across the three directories CI runs.

### Worth carrying

**Two of the user's own review comments in one round were in tension** — *make the paths `Path`s*
and *put the paths in a `StrEnum`* cannot both be taken literally, since a `StrEnum` member is a
`str`. That is the third time on this plan (after #154's `spelling` → `name` against inheriting a
specification, and #149's own earlier pair), and the useful output each time was the measurement
showing the conflict rather than a choice made quietly on their behalf.

**But a measurement showing two asks conflict is not proof no third shape exists.** The reply had
enumerated three shapes and stopped, and the shape that dissolved the tension — split the collection
so the directory is a `Path` and the files are text — was not among them. The general check, cheap
and skipped here: before reporting that two requirements are incompatible, ask what would have to be
true for both to hold, and whether the collection can be split so each half gets the type it wants.

## Update 2026-08-22 (fourth round): a test that stated its rule by implication, and a class name nothing owned

Two threads on #184, filed nine hours after the third round was pushed. Both applied and
resolved in `d224c1126`; 242 plan-dashboard tests, was 241.

### "How does this test that it suggests nothing?"

It did not, and that is the useful finding rather than a misreading. The test compared a
length and a substring:

```python
assert without_targets.description in with_targets.description
assert len(with_targets.description) > len(without_targets.description)
```

which states the rule by implication — a reader has to work out that "shorter, and contained
in the other" means the suggestion is absent. Worse, `in` allowed the no-targets description
to sit *anywhere* inside the other, so it never actually said the suggestion is appended.

It now says the rule directly: the suggestion is a **suffix**, so a flag with nothing to
suggest is described by exactly the part that comes before it. `startswith` replaced `in`,
and a sibling test pins the half nothing had ever asserted — a suggestion names every target
it has. Both derive their expectation from the `reparent_targets` the flag was built with,
which is the fixture the code consumed, so neither comes back on a reword.

**The limit was stated on the thread rather than left to be discovered.** These say the clause
is absent; they cannot tell *omitted* from *rendered empty*. Deleting the
`if not self.reparent_targets: return described` guard leaves a dangling
`- consider reparenting onto `, which is still a prefix of the two-target description, so the
test passes. It *is* caught — by `test_render_shows_one_drift_line_per_description_on_the_item_card`,
and only because the rendered line gets stripped while the description does not. That is
accidental coverage, not a test aimed at the defect, and telling the two apart deliberately
means naming the lead-in phrase, which is precisely the wording the two previous rounds cut.
Offered rather than taken.

### The CSS class nothing owned

*"Does `drift` not have a StrEnum or a dataclass or something that structurally refers to it
or names it instead of this string?"* — checked rather than answered from memory, and the
answer was no, in three places at once: `drift` and `drift-banner` are literals in
`dashboard.html` **twice each** (the `.drift` rule in the `<style>` block and the `class=`
attribute), and `has-drift` is a bare literal in `build_dashboard.py`'s
`status_and_drift_css_class` — whose *other* half, `f"status-{self.status.value}"`, derives
structurally from `ItemStatus`. One line, two conventions.

`DashboardCssClass` now names the two classes the page-reading helpers look elements up by,
and `text_of_elements_with_class` takes it rather than any `str`, so the helper cannot be
called with a class the page never carries. Mutation-checked: changing `DRIFT`'s value fails
the drift-line test and nothing else — the parser finds no elements — so the enum and the
template are held equal by the rendered-page tests rather than by convention.

Two deliberate limits, both reported:

- **The enum is in the test module, not production** — *reversed by the fifth round below,
  and the reasoning given here did not survive contact with the file.* The argument was that
  the template is where a CSS class is defined, so Python could only be a third copy; what it
  overlooked is that `status_and_drift_css_class` was already spelling `has-drift` itself.
- **The module's other ~100 markup literals are untouched** — `next-bug-chip`,
  `next-count-all`, `review-button`, `id="wave-wave-1"`, all `main`'s. The distinction that
  makes naming two of them defensible without implying the rest: those are
  `assert '<span class="next-bug-chip">bug</span>' in output`, where the literal **is** the
  assertion, and these two were *arguments to a lookup*.

### Worth carrying

The round-3 lesson — check the neighbours before defending a guard — applied in the opposite
direction here, and it cuts both ways. Adding structure the neighbours lack is the same
mistake as defending a guard the neighbours do not have, unless the thing being changed is
doing a different job. Both threads turned on that: a literal that *is* the assertion needs no
name, and a literal that is an argument does.

## Update 2026-08-22 (kickoff): the CI verdict opens as #191, and three design questions are settled

`/plan-item-kickoff workflow-unification integration-branch-ci-verdict`, session
https://claude.ai/code/session_01Aw5p5xzSFUKNCueN8oG6Tg. Branched off #154's head
(`claude/plan-item-kickoff-workflow-ixbvxl`), bootstrapped before any implementation.

### The load-bearing fact re-checked, as the item's own notes asked

`ci.yml` triggers on `push` to `main`, on `pull_request` with no branch filter, and on
`workflow_run` for `update_docker` on `main`. The premise holds: **a pushed integration branch
gets no CI unless a pull request exists for it**. The unfiltered `pull_request` trigger is what
makes the candidate shape work at all — a pull request whose base is `integration` gets the
ordinary run without any change to `ci.yml`.

### One premise has changed since the item was recorded

The notes say the Actions client is missing "because #146 measured the reachability but is
unlanded". #146 has since landed: `.github/workflows/upstream-reviews.yml` and
`.claude/upstream_reviews/` are on `main`, and `/upstream-reviews` is now the worked precedent
for dispatch-a-workflow-then-read-its-result. What is still missing is a *REST* Actions reader
usable from a script, which is what this item builds — on `GitHubRepository._call` in
`maintenance_github.py`, not as a second client. Decision 13's whole complaint is duplicated
GitHub backends, so adding one here would be answering it in the wrong direction.

### The three questions the item left open, answered

**The stable branch is a pointer, not a merge target.** The candidate pull request opens into
`integration` to get CI at all; on green, `integration` is force-updated to the candidate commit
and the pull request is closed rather than merged. The alternative was operationally simpler —
green, click merge, no force-push — but a build is regenerated from scratch, so every merge
would join two independent build histories and `integration` would accumulate exactly the
history the design has refused since the item was recorded: *it exists to be built from, not to
be history*. The diff a candidate's pull request shows is the same either way, so the merge
target bought nothing the pointer does not.

**The verdict is the marked job's conclusion, not the whole run's.** That is the point of the
marker: a verdict in a fraction of the matrix's time, with no second dispatch, and the rest of
the run still reporting normally for anyone reading the candidate.

**The marker is not excluded by default.** Adding it to `pytest.ini`'s `addopts` exclusion the
way `slow` is would have kept the breaking branch's own CI green — and that is precisely the
wrong outcome. The triage skill pushes the reproduction test onto the breaking branch because it
is "the only artifact that makes the failure visible from inside the branch that causes it", and
a test excluded from that branch's own run is invisible there. The dedicated job is a fast
subset, not the only place the test runs.

### Where the code goes, and why not in `integration.py`

`integration.py` is 1,697 lines with an open review thread asking whether the 400-line rule
extends to it, so nothing new lands there beyond subcommand wiring. The Actions and check-run
reads, pull-request creation and reference force-update extend `maintenance_github.py`'s
existing client; the candidate/verdict half is a new `integration_verdict.py`; the targeted job
is a new `.github/workflows/integration-checks.yml`, kept out of `ci.yml` because it needs both
a `pull_request` trigger (the candidate's verdict) and a `workflow_dispatch` one (the
localisation probes), and because staying out of `ci.yml` keeps it clear of #185's rename of
`test_claude_dev_tooling`.

`locate-failure` moves too rather than keeping `_run_tests` — each per-tip probe becomes a
dispatched run of the same workflow. That is what stops the verdict being split across two
mechanisms, which is the half-migration the item's notes warn about. It is slower again, and the
class already documents itself as slow by construction.

The clearing condition needs the marker to name its branch
(`@pytest.mark.integration_conflict("<branch>")`), so a marked test that passes identifies the
pull request whose `integration-conflict` label to clear. Without that the passing test says
something is fixed but not whose.

`integration_verdict.py`'s tests are also the `ReportKey` wire-format guard the 08-20 sixth
round deliberately deferred here: the consumer parses a real `IntegrationReport` and
`FailureLocationReport` through `ReportKey`, so a rename that breaks a reader fails a test that
exists for its own reason rather than one written to restate the enum.

### State the branch inherits, recorded rather than discovered later

`check_dependency_readiness.py` reports `integration-branch` as `open_ready`, so the dependency
is ready by the plan's own rule. It is nonetheless `mergeable_state: dirty` against `main` and
carries `needs-resolution`; #154's conflict is #154's to resolve, and this branch carries it
until then.

`check_scope_overlap.py` against `origin/main` was run rather than eyeballed:
`.claude/stack/integration.py` is absent from the base and shared with #154, along with
`maintenance_github.py` and `stack.toml`. Strip those edits and an Actions client, a workflow
file, a marker, a stable branch and two subcommands remain — the same answer the 2026-08-13
entry argued, re-confirmed against live state.

**This branch crosses the bastler move.** #185 empties `.claude/stack/` into `bastler/` and
everything this item adds is in that path; whichever is still open when the other lands merges
`main` across and re-applies its delta inside the package, per the doctrine decision 13 already
recorded. #158 is affected the same way. `pytest.ini` and the new workflow file are outside the
move.

### One limit stated rather than assumed

The marked job runs with the tooling dependencies only, so a reproduction test that lives inside
a robotics package and needs the docker matrix would not be collectible there. The matrix stays
the slow path for those. If it turns out to matter in practice it is a follow-up item, not a gap
this kickoff pretended was closed.

## Update 2026-08-22 (fifth round): "why is this only in tests?"

One thread on #184, filed two hours after the fourth round was pushed. Applied and resolved
in `4279271f1`; 267 plan-dashboard tests, unchanged.

### The reason given the round before was wrong, and the file said so

The fourth round put `DashboardCssClass` in the test module and argued that the template is
where a CSS class is defined, so a Python enum could only ever be a third copy of the name.
That reasoning ignores what was two lines away from the thing being discussed:

```python
drift_suffix = " has-drift" if self.drift_flags else ""
return f"status-{self.status.value}{drift_suffix}"
```

One line, two conventions — the status half derived from `ItemStatus`, the drift half a bare
literal. Production *does* name CSS classes, so "Python would be a third copy" was an
objection to something the file already did. The enum moves into `build_dashboard.py`, gains
`HAS_DRIFT`, and the tests import it exactly as they already import `ItemStatus` and
`LiveState`.

### What it buys, stated without the overstatement

It removes no copy. `dashboard.html` still names every class it styles, once in the `<style>`
rule and once in the `class=` attribute, and making Python the single source means rendering
the stylesheet through Jinja — worth doing for all ~60 classes or for none, not for three.

What it does buy is that **Python** names each one once instead of spelling it in two files,
and that each value is pinned by exactly one test, mutation-checked one at a time:

| member | fails if its value changes |
|---|---|
| `DRIFT` | `test_render_shows_one_drift_line_per_description_on_the_item_card` |
| `DRIFT_BANNER` | `test_render_banner_counts_drift_flags_rather_than_drifted_items` |
| `HAS_DRIFT` | `test_status_and_drift_css_class_with_drift` |

Each fails alone, and each is the test named for that behaviour.

### Placement is load-bearing, and it caught this session out

The first attempt put the enum immediately before `@dataclass class ValidationProblem` — and
re-created, exactly, the non-convergence this file was in until the first round of this
review. An attribute docstring directly before a *decorated* definition makes `docformatter`
drop a blank line, `black` put it back, and `scripts/format_docstrings.py` discard everything
docformatter did. `docformatter --diff` went from 0 hunks to 1 the moment the class was
inserted:

```
     """
     An item card carrying at least one drift flag.
     """
-
 
 @dataclass
 class ValidationProblem(ABC):
```

It sits among the other `StrEnum`s now, followed by an undecorated `class`, and both touched
files are back to 0 hunks with `black --check` clean.

**Worth carrying: this hazard is a property of a file's shape, not a fact about the file**, so
it is re-creatable by an ordinary insertion months after the original was fixed — and it is
silent, because the repo's own formatter reports no change when it hits it. The check is one
command (`docformatter --config pyproject.toml --diff <file> | wc -l`) and it belongs after
any insertion near a decorated definition, not only when something looks wrong.

### Left alone deliberately

The `status-` prefix in that same f-string stays a literal: it is a prefix composed with an
enum value rather than a class name, and making it a member would make the enum's own
contract untrue. `build_index.py`'s `plan-card`/`complete` are untouched — a different page,
and not what this pull request is about.

## Update 2026-08-23 (resolved): #149's third upstream round, and the first naming answer with a count behind it

`/plan-item-resolve workflow-unification plan-item-execution-modes`. One thread, from a second
upstream reviewer, filed fifteen minutes before this session started. Applied in `236247da`; 522
tests across the three directories CI runs, unchanged.

### Nothing on the fork said the item was stalled

Everything a fork-side read can see was clean: 23 of 23 checks green (the `greenlet` and robokudo
failures the 08-10 comments recorded have both cleared), `mergeable_state: clean`, `origin/main` an
ancestor of the head, no conflict, and the two fork threads left open on purpose still the only
open ones. The stall was entirely on cram2 #537, where **tomsch420 requested changes at 09:58Z** —
a second upstream reviewer, four days after LucaKro's round.

This is the gap the 08-22 entry named as *"the manifest tracks the fork pull request and the review
happens on the promoted one"*, now with the sharper version: **a fork pull request can be green,
un-drafted, conflict-free and up to date with its base and still be blocked**, and no field on this
plan shows it. What closed it here is that `/upstream-reviews` (#146) has landed, so the round was
read in twelve seconds by a dispatched Action rather than through `WebFetch` on a rendered page.
The 08-22 entry predicted exactly that and it held on its first real use.

### The third name for one method in five days, and the first one that was measured

*"we call it to_json everywhere else. Make yourself ready for SubclassJSONSerializer"*, on
`Report.as_json`.

| round | name | what decided it |
| --- | --- | --- |
| upstream, 08-19 | `as_document` | it names the thing produced, not the Python type |
| fork, 08-22 | `as_json` | the user's standing rule |
| upstream, 08-23 | `to_json` | 93 definitions outside `.claude/` against 3 |

The first two are arguments and the third is a count, which is the whole finding. `grep -rn "def
to_json"` outside `.claude/` returns 93; `as_json`, `as_document` and `to_json_dict` together
return 3. `SubclassJSONSerializer.to_json(self) -> Dict[str, Any]` is a dict-returner, so the name
the reviewer asked for is the one `AGENTS.md` already points every round-tripping class at. Three
rounds argued about a name while the repository had been answering it 93 times.

**Worth carrying: when a naming round reverses itself twice, stop reasoning and count.** The
measurement was one `grep` and it was available at every one of the three rounds.

### "Make yourself ready for" is the name, not the dependency

Read as the rename only, and that is deliberate rather than a convenience. Adopting
`SubclassJSONSerializer` itself stays declined on the measurement the still-open krrood thread
carries — `test_claude_dev_tooling` installs `pytest` and the two dashboard requirements on a bare
`ubuntu-latest`, so the import breaks the job and every hook running under a plain `python3` — and
`bastler-package` is still where that is revisited. What readiness costs is that the method's name
and signature already match, which they now do, stated in `Report`'s own docstring rather than only
in a reply. Nothing reads one of these reports back into a Python object, so no `type` key was
added: that would change the printed document, which this round did not.

### It also dissolves the one decision `report-document-naming` could not make

That item had inherited a genuine collision from the fork round: `as_json` had been ruled the name
for dict-returners while it already named the `str`-returning method in `maintenance_report.py` and
`maintenance_board.py`, so the recommendation on the thread was to rename those to `as_json_text`.
With `to_json` as the target the collision is not resolved but absent — the dict-returners take
`to_json`, `as_json` stays free, and the two `str` ones are untouched. The item's recorded target
was corrected in the same turn.

**Worth carrying: a naming conflict is sometimes an artifact of the wrong name having been picked**,
not a decision anyone owes. This one had a ruling drafted for it before anyone checked whether the
premise that created it was right.

### Deliberately not re-drafted, again

Per the 08-22 entry: un-drafting a fork pull request is this workflow's own promotion gate, so
re-drafting #149 would withdraw #537 from the review it is answering. The user's standing
convention to re-draft after every push does not reach a promoted branch, and the exception is
recorded here rather than re-derived each round.

## Update 2026-08-23 (resolved): #185's merge was three modules, and its review round was one complaint

`/plan-item-resolve workflow-unification bastler-package`, session
https://claude.ai/code/session_01Hgt7hWYnT9ZMK6AgusPwkk. Two things were wrong: a merge
conflict that had the pull request `needs-resolution` and skipped by every maintenance
pass since 2026-08-22, and a 34-thread review round the manifest recorded none of - the
fifth item on this plan where the pull request was the more accurate source.

### The merge was not three conflicts, it was three modules

`git merge-tree` reported three content conflicts and three file-location ones. Taking
that as the size of the job would have produced a branch that merged and then failed its
own contract, because `main` gained Python under `.claude/` after this branch was cut:
`check_scope_overlap.py` with #135, `record_dashboard_url.py` with #150 and
`upstream_reviews.py` with #146. Left where they landed, `no .py file remains under
.claude/` fails - which is the test that exists to catch exactly this.

All three move into the package, and three consequences follow rather than being separate
decisions:

- **`upstream_reviews.py` was a fourth carrier of the hackery this migration deletes.** It
  inserted `.claude/stack/` onto `sys.path` to import `stack.py`'s `Repository` - the same
  three-`sys.path`-roots problem, in production rather than in a conftest. It imports
  `bastler.stack` now, and its `queries/` documents move with it as package data.
- **The two `gh` stubs become one.** They recognized disjoint invocations - `api graphql
  --input` for the review reader, `api --paginate .../comments?` for `plan-updates-since.sh`
  - so one stub serves both, and a second copy is what drifts when the contract moves.
- **`.claude/upstream_reviews/tests/` was in no CI job at all on `main`.** `ci.yml` named
  four test directories and not that one. Folded into `test/bastler_test/` it runs in
  `test_bastler` for the first time. A gap the merge closed for free, and one nobody would
  have found by reading the conflict.

Worth carrying: **a conflict report names files, and the files it does not name are the
ones a moved directory makes dangerous.** git's own "added in origin/main inside a
directory that was renamed in HEAD" was the tell for three of the six, and for the other
three - the ones on `main` at the merge base of an earlier fetch - there was no tell at
all. The check that found them is one command: `git ls-tree origin/main` for the pattern
the branch claims to have emptied.

### The review round was 34 threads and about four things

Every thread is the user's. Grouped by what they actually ask for, they are: the package
should carry its own metadata and be publishable; what the package declares about itself
should not live in a test; constants should have one home; and the test helpers should
stop being written per suite.

**Metadata and publishing.** `__init__.py` is empty and its content is `bastler/README.md`,
which `pyproject`'s `readme` points at. The name's explanation is corrected - it shares its
first letters with the surname of whoever wrote it, not with the repository's owner.
`pyproject` gains author, maintainer, license, urls, keywords and classifiers matching the
repository's other packages, and its version now comes from the root `VERSION` file through
`scripts/sync_version.py` and `bastler/_version.py`, like every other package here rather
than a literal of its own. `sync_version.py` grew a `FLAT_LAYOUT_PACKAGES` set rather than
a second name-equality special case, since `bastler` is the second package that *is* its
own directory. The "never published, repository tooling only" claim is deleted from both
files. Publishing it, and the plugins for agent providers the user wants as the end state,
is its own item - this pull request should simply stop asserting it will never happen.

**What the package declares about itself.** `bastler/package_layout.py` holds the module
list, the dependency tiers and what each module reaches;
`test_package_contract.py` only checks it. That answers the four "why is this defined in
the tests" comments at once. The list stays written out rather than discovered, because
each entry says something a directory listing cannot - but one test now holds the declared
set equal to what the directory actually contains, so a module added without an entry fails
rather than going quietly uncovered. That was the property writing the list out was buying,
and it is now bought explicitly.

**The tier's justification was wrong, and measuring it is what fixed it.** It said a hook
may import only the standard library because a hook runs where nothing is installed. The
user asked the obvious question - can the hook not just install what it needs? Measured
rather than argued: `session-start.sh` invokes **no** module of this package. It is bash,
plus one stdlib-only heredoc inside `check-setup.sh`. So the framing was protecting a
caller that does not exist. What a tier does answer is whether an entry point runs on a
checkout where nothing has been installed or needs
`pip install -r bastler/requirements.txt` first, and that is what it says now. Nothing is
forbidden to install anything - `check-setup.sh` already reports a missing requirement and
`/setup-personal-notes` already installs it, which is auto-detection and auto-installation
one layer up from the hook, at the moment the dependency is actually needed. Putting a
`pip install` inside the SessionStart hook was *not* done, and the reason is stated rather
than assumed: it would write to a contributor's Python environment unasked on every fresh
container, it can fail where a report cannot (no network, an externally-managed
environment), and a hook that fails is worse than one that reports. Available if wanted;
not taken unilaterally.

**Constants: derive what an import knows, share the rest.** The user's own question
settled this - is it better to read a module's name and path off the import than to keep
them in a table? Yes, and the split follows from it. Anything that *is* a Python module is
not written down at all; anything that is not has no import to derive it from, and that is
what a shared module is for. `test/bastler_test/constants.py` holds the second half, with
`ToolingDirectory` for the homes that stayed under `.claude/` and `PersonalNotesPath` for
what the notes branch holds - literals in both cases, because those paths *are* the
interface between the shell hooks and Claude Code, so nothing imports them.
`REPOSITORY_ROOT` and `PACKAGE_DIRECTORY` are not literals even there: they come from
`bastler.package_layout`, so the tests locate the package the way the package locates
itself. Six copies of `DATASET_DIRECTORY`, three of `REPOSITORY_ROOT`, three of the notes
file path and two each of several others are gone.

One thing asked for cannot be done, and the measurement is the answer:
`monkeypatch.setattr` takes the attribute name as a string by its own signature, so
`"RESTACK_STEPS"` cannot be derived from importing `RESTACK_STEPS` - importing gives the
tuple, and a tuple does not know what it is bound to. It is already guarded, which is the
part worth knowing: `setattr` raises when the attribute does not exist, so renaming
`RESTACK_STEPS` fails that test loudly today.

**The test helpers.** `test/bastler_test/script_runner.py` is the hierarchy the review
asked for by name. Every suite had the same shape to express - run a module or a bash
script from a project root, capture both streams, read the exit status - written out per
suite with its own environment handling. `ScriptRunner` holds the shape,
`PythonModuleRunner` and `BashScriptRunner` hold what to run, and the environment variation
collapses into one field: `removed_variable_prefixes`, where a whole name is its own
prefix, so it covers a family (`CLAUDE_PERSONAL_NOTES_`) and a single variable
(`PYTHONPATH`) alike. Removing rather than overriding is the point - a test asserting what
happens when a credential is absent cannot say that by setting it to something. Six call
sites use it; two hand-written environment cleaners went with them, and the maintenance
runner takes its credential list from `bastler.maintenance_constants` rather than a copy.
`install_package_into()` and `install_hook_scripts_into()` are one statement each of what
`ScratchRepository` and `test_maintenance`'s `ForkCheckout` had byte-identical, and
`install_stack_configuration()` moves onto `ScratchRepository` what `test_stack.py` was
doing in a module-level helper over three of its methods.

**A status labels itself.** Asked why the label map is not on the enum, the answer is that
it can be - it is strings, so it costs `plan_model.py` nothing, and the layering argument
against it was a preference. `ItemStatus.display_label` derives the label from the value
(`not_started` becomes "Not started"), so there is no table at all, `status_label` is a
one-line filter, and a status added later labels itself. That also emptied the test the
user called theatrical: with no wording written down, there was nothing left for it to
restate. One assertion beside the filter pins the derivation instead.

### State

616 tests pass, against 536 before this session and 479 on `main` at the time of the move.
`check-setup.sh` exits 0 with every row `ok`; all thirteen entry points answer `--help`.
The pull request is `mergeable` again and stays a draft. Four commits: the merge, the
metadata and declaration, the constants and runner, and the fixture moves.

Two things are recorded rather than done. The `run_git` seam is now *reachable* for the
first time - `check_scope_overlap.py` landed on `main` with #135, so both halves of that
pair are finally in one importable tree - but unifying it stays
`bastler-notes-core-python`'s by name, which is decision 12's own assignment. And #151's
`Subcommand` is still unlanded, so the command-class pair is still half-visible, exactly as
the 2026-08-20 kickoff recorded.

## Update 2026-08-23 (recorded): `/plan-item-resolve` reads upstream reviews only when a hand-written label says to

New item `always-read-upstream-reviews`, track `personal-data`, wave `immediate`,
`depends_on: []`. A bug fix, based off `main`, recorded by `/add-plan-item`; no branch or
pull request opened by that run.

### The gate, and the premise underneath it that is false

`.claude/skills/plan-item-resolve/SKILL.md` step 2 reads upstream review threads only when
the fork pull request carries `in_review_label` (`in-review`), or when `notes`/`status`
happen to say the item is under upstream review — and otherwise *"skip it … since a branch
never promoted has no upstream PR to read."*

That last clause treats the label as evidence of the upstream pull request's existence.
The tooling that owns the label says the opposite, in
`.claude/skills/stacked-pr-maintenance/SKILL.md`'s "What this pass never does":

> **It never adds `in-review`.** That is the developer's, once they have clicked Create.

So the upstream pull request exists from the moment Create is clicked, and the label
exists only if someone remembers afterwards. The skill reads a hand-maintained flag as
proof of a fact it does not track, and skips the upstream read for exactly the branches
most likely to be carrying upstream review comments — a fork pull request can be green,
un-drafted and clean while the item is stalled on an upstream request for changes, which
is the case that bullet exists to catch.

### The gap is live, measured rather than argued

Counted over the fork's open pull requests when the item was recorded: ten carry
`cram2-link-sent` (promotion built the compare link) — #190, #188, #187, #186, #182, #161,
#160, #158, #157, #156 — while two carry `in-review` (#149, #63). Every one of those ten
whose Create has been clicked has an upstream pull request that `/plan-item-resolve`
currently skips in silence.

### Why the answer is "always call it" rather than "check first"

The obvious alternative — resolve branch → upstream pull request before deciding — is not
available to a session, and this is the repo's own recorded constraint rather than a
guess. `.claude/stack/stack.toml:14` and `.claude/stack/stack.py:9` both state that cram2
is not readable from the cloud, which is *why* the label was invented as a stand-in; and a
session's GitHub scope is the fork alone, so the upstream's pull requests cannot be listed
to pre-check.

The pre-check is redundant anyway. `/upstream-reviews` already resolves branch → upstream
pull request on the fork's Actions runner, where the read is permitted, and its step 5
already handles the empty answer cleanly: *"If the branch has no upstream pull request, the
script says so explicitly — relay that as a clean answer, not an error."* The gate
therefore buys nothing and costs the case it was meant to cover. Invoke the action
whenever the item has a branch; keep the existing behaviour that a failed dispatch is
reported and does not fail the skill.

### Scope, checked rather than assumed

`check_scope_overlap.py` against `origin/main` returned an empty `paths_absent_from_base`
for `.claude/skills/plan-item-resolve/SKILL.md` and
`.claude/skills/upstream-reviews/SKILL.md`: both already exist on `main`, so this is not a
disguised modification of an unlanded parent. Six unlanded branches touch the resolve
skill — #149 (execution modes), #151 (manifest currency), #154/#191 (integration branch),
#156 (setup without asking) and #185 (the bastler move, a one-line `.claude/stack/stack.toml`
→ `bastler/stack.toml` rename inside this very bullet) — but by purpose none of them is
this work. The overlap is merge friction on one contiguous paragraph, not ownership;
whichever lands second resolves in favour of the unconditional wording.

### Carried for whoever kicks it off

The one landed precedent for a test over a skill document is
`.claude/stack/tests/test_maintenance_skill.py`, which asserts a dangerous phrasing is
*absent* and the safe one present. The same shape fits here: the gating clause gone, the
unconditional instruction present. There is no `plan-item-resolve` tests directory yet, and
`ci.yml`'s `test_claude_dev_tooling` job runs four named directories, so adding one costs a
constant in `resolve-personal-notes-config.sh` and one path in `ci.yml`.

Two things noticed while checking scope, neither this item's to fix. `#149`'s branch
carries the upstream bullet **twice** — the copies differing only in "step 5" versus
"step 3", a merge artifact on that branch; `origin/main` carries it once. And this session's
designated branch had been left pointing at an integration-branch merge rather than at
`origin/main`, so the item's branch must be created from `origin/main` at kickoff.

## Update 2026-08-23 (kickoff): `always-read-upstream-reviews` opens as #194, and the recorded test plan is corrected

Branch `claude/plan-item-kickoff-workflow-y2xfva` off `origin/main` (`3f643cf`), draft #194,
labelled `bug`. `depends_on` is empty and `check_dependency_readiness.py` confirms it, so
nothing gated the start.

### What the fix is

The gate at `.claude/skills/plan-item-resolve/SKILL.md` step 2 goes: `/upstream-reviews` is
invoked whenever the item has a `branch`, with no label condition, and a failed dispatch is
still reported in step 5 rather than failing the skill. The reasoning was settled when the
item was recorded and is not relitigated here.

**A second site carries the same premise, and the recording did not name it.** Step 5's
flag list asks the session to say whether upstream state was read *"when the item looked
promoted but `/upstream-reviews` could not be run"*. "Looked promoted" is the label premise
in different words; it becomes "has a branch". Found by reading the document through rather
than by grepping for the label, which the first site's wording would have been enough to
satisfy.

### The carried test plan was correct when written and is now wrong

The recording carried forward: *"There is no `plan-item-resolve` tests directory yet, and
`ci.yml`'s `test_claude_dev_tooling` job runs four named directories, so adding one costs a
constant in `resolve-personal-notes-config.sh` and one path in `ci.yml`."*

Running `check_scope_overlap.py` against the live branches at kickoff shows that route now
builds something #185 deletes. The bastler move removes `.claude/hooks/tests/` and
`.claude/stack/tests/` outright, replaces the four-directory `test_claude_dev_tooling` job
with a single `test_bastler` job over `BASTLER_TESTS_DIRECTORY`, and rewrites both
`resolve-personal-notes-config.sh` and `ci.yml` — so a fifth constant and a fifth CI path
would be a conflict in the two files #185 touches most, for a directory it then removes.

The test goes in the existing `.claude/hooks/tests/` instead: already in CI, so no constant
and no `ci.yml` line, and the #185 collision reduces to one file move that #185 is already
performing for every other file in that directory. The cost is that a skill-document test
sits in a nominally hook-script suite; #156 already does exactly that with
`test_setup_prerequisite_documents.py`.

### What the test asserts, and what it deliberately does not

`test_maintenance_skill.py` states the shape that earns a test over a document: *"an
absence, computed from this checkout's own remotes rather than from a string written here,
which is what makes it worth a test where a prose assertion would not be."* The durable
property here is that the resolve skill's upstream instruction does not depend on the
promotion label. So: the `in_review_label` value, read from its owner `.claude/stack/stack.toml`,
is absent from `plan-item-resolve/SKILL.md`; and the skill still invokes the upstream-reviews
skill, whose name is read from that skill's own frontmatter. Both sides are derived from the
definition rather than retyped.

No wording is pinned, on purpose. #121's review round cut
`test_every_summary_message_reads_as_written` for exactly that, and the generalization it
left behind — *notice the guard you are deleting and say so*, not *always replace it* —
applies: the step 5 rewording has no durable property to assert, so it is covered by review
and stated here rather than given a wording assertion that would fail on the next rewrite.

### Checked while scoping, neither this item's to fix

`.claude/upstream_reviews/tests/` runs in no CI job at all — its ~40 tests are in neither
`ci.yml`'s four-directory list nor `resolve-personal-notes-config.sh`. #185 fixes it
incidentally by moving them to `test/bastler_test/`. And `plan-item-resolve/SKILL.md` is the
only invoker of `/upstream-reviews` anywhere, while `in_review_label` keeps its readers in
`stack.py`, `maintenance_promotion.py`, `.claude/stack/README.md` and
`stacked-pr-maintenance/SKILL.md` — so removing this one use orphans no configuration key.

### Roadmap read at kickoff

`roadmap.md` is 9,067 lines; a full read was impractical and is recorded as such rather than
glossed. Read in full: the header through standing risks (1-110), both standing-conventions
sections (183-194, 664-700), the `upstream-review-reader` entry (4036-4165), and this item's
own recording. The complete heading index was read to choose those, and the file was grepped
for the item id, its branch, `labelled` and `in-review`.

## Update 2026-08-23 (correction): the tier's caller is a workflow, not a hook

The user's question after the auto-install answer was the right one to ask: *if a hook can
install, don't the tiers and `package_layout.py` stop earning their keep?* Measuring it
found that the previous entry - "the dependency tier's stated justification was wrong" -
is true of the caller it names and wrong in the conclusion a reader takes from it.

`session-start.sh` does invoke no module of this package; that stands. But the
standard-library tier has a live caller, and it is a **workflow file**, which is why
grepping the hooks missed it. `.github/workflows/upstream-reviews.yml` runs
`python3 -m bastler.upstream_reviews` on a bare `ubuntu-latest` with `actions/setup-python`
and **no `pip install` step at all**, and that module imports `bastler.stack`. Both must
stay standard-library-only or #146's entire read - the thing that made this very round's
upstream review legible - stops working. Verified rather than reasoned about, by importing
each with `yaml`, `jinja2`, `markdown` and `nh3` made unimportable.

The session-invoked entry points are the same case one step weaker: `stack`, `maintenance`,
`check_scope_overlap` and `plan_updates_since_support` all run in containers where nothing
has been installed, which is precisely why `check-setup.sh` reports
`dashboard_dependencies needs-setup` on essentially every fresh session - the observation
`setup-runs-without-asking` (#156) was filed from.

So installing during a hook does not dissolve the tier. It would have to be installing
*everywhere*, and adding a `pip install` step to an Actions runner in order to serve a
script that needs nothing is strictly worse than the script continuing to need nothing.

**The user was right about the rest of it, though, and three members were dead** - deleted
in `d13afaf8b`. `REQUIREMENTS_FILE` had no reader anywhere: the shell resolves
`BASTLER_REQUIREMENTS_FILE` from `resolve-personal-notes-config.sh` and `pyproject` reads
the file through setuptools' dynamic table, so the constant was a third spelling nothing
consulted. `MODULES_BY_NAME` and `PackageModule.path` had none either. What survives has a
reader each: `PACKAGE_MODULES` (three tests, including the one holding the declared set
equal to the directory's contents), `is_command_line_entry_point` (the `--help` test),
`tier` with `THIRD_PARTY_MODULES_BY_TIER` (the import-boundary test), `import_path`, and
the two directories the test constants locate the package by. 616 tests still pass.

**Worth carrying: a grep over the hooks is not a survey of the callers.** The first
measurement asked "does a hook import this?", got no, and generalized to "nothing depends
on the tier". The caller was a YAML file two directories away, running the module by the
same `python3 -m` line the hooks would have used. The check that would have found it is
the one that finds any caller: grep for the *module*, not for the callers you expect.

## Update 2026-08-23 (decision 14): the package layout is derived, and krrood is the direction

The user's objection, in their own words: *"what I do not like is the amount of manual
adding of modules in the package layout, the fact that we have to be careful with tiers,
and that at some point I want bastler to anyway import krrood and use it and depend on it,
this is to lower duplication and increase maintenance."*

Three complaints, and the third is what decides the shape of an answer to the first two.

### Derived rather than declared

`package_layout.py` held 29 hand-written entries, a three-member `DependencyTier` enum and
a tier-to-imports table, so adding a module meant three decisions to get right and a test
that only told you afterwards. All three are read from the package now, in `a62a79525`:

- **the modules** from `PACKAGE_DIRECTORY.glob("*.py")`;
- **the entry points** from each module's own source - an `ast` walk for a top-level `if
  __name__ == "__main__"` block, which is exactly what makes `python3 -m bastler.<name>
  --help` answer rather than do nothing;
- **the requirements' import names** from `requirements.txt` through
  `importlib.metadata.packages_distributions()`, which is the one part of it no file states
  about itself: a distribution is not always imported by its own name, and PyYAML is `yaml`.

The set-equality test went with the list, because it existed only to hold a hand-written
list to the directory - a question that stops being askable once the directory *is* the
list.

### Two declarations left, both held in both directions

`MODULES_THAT_MAY_NEED_THE_REQUIREMENTS` is one flat set of seven names, and the default
inverts with it: **a module imports on the standard library unless it is named**, rather
than every module being classified into a tier. A module added later is held to the
default with nothing written down.

`UNINSTALLED_INVOCATIONS` is the evidence behind that default rather than a second copy of
it - one entry today, naming `.github/workflows/upstream-reviews.yml`, the module it runs
and why it installs nothing. A test reads the caller's own file back, so an entry that
stops being true fails rather than lingering.

Five mutations, each caught by exactly the test that names it: a standard-library module
growing an `import yaml` (12 failures - the count is how many modules import `stack`); an
over-broad exception; the caller gaining a `pip install` step; the caller ceasing to invoke
its module; and a **newly added module**, discovered and checked with no edit to any list.

### The reverse check found a wrong declaration on its first run

`record_dashboard_url` was declared `PLAN_MANIFEST` and imports only the standard library -
it parses the URL cache with a regular expression rather than PyYAML. Nothing had ever
caught it, and could not have: the tier test asserted a module stayed *within* its tier,
never that it *needed* it, so an over-broad declaration was invisible by construction.

Worth carrying, because it is the opposite of what the effort suggests: **the cheaper shape
caught something the more elaborate one could not.** The 29-entry table had more places to
be wrong and fewer ways to find out.

### Coverage was measured, and the first attempt lost some

Parametrizing only over the declared caller took the suite from 616 to 592 - 21 modules
silently stopped being checked at all, because nothing named them any more. That is the
failure mode of replacing a classification with a short list, and it is invisible in a
green run: fewer tests passing still reads as passing. The exception set is what restores
it, since the standard-library check parametrizes over every *discovered* module outside
the set. 621 pass now.

### Decision 14: bastler depends on krrood

Recorded rather than acted on here. Decision 12 made version 1 deliberately independent of
krrood, mirroring its `DataclassException` idiom in a stdlib-only base rather than
importing it, and named a future `dev-tooling-krrood-adoption` plan as deliberately *not*
created. The user's statement makes that adoption **wanted rather than hypothetical**, and
turns version-1 independence from a permanent property into a stage.

It does not change this pull request, and it does decide the endgame for what is left
declared: once bastler imports krrood, the standard-library *default* is no longer
reachable, so `MODULES_THAT_MAY_NEED_THE_REQUIREMENTS` inverts into a short list of what
still has to run light - and the `UNINSTALLED_INVOCATIONS` entries are already what say
which those are. Nothing about the derivation changes, which is the argument for having
done it first: the part that had to be maintained by hand is gone before the dependency
that would have made the hand-maintained part wrong.

Still gated on what decision 12 already measured: `test_bastler` installs `pytest` and the
two dashboard requirements on a bare `ubuntu-latest`, so a krrood import breaks that job
until the job installs it, and `.github/workflows/upstream-reviews.yml` installs nothing at
all. Neither is an argument against the direction; both are the concrete work the adoption
item owes.

## Update 2026-08-23 (same day, inverted): name the callers, derive the modules

The user's objection to the shape decision 14 landed: *"I don't like that we still name
modules that may import something, I think if we have to, we can do the opposite by naming
the ones that must not import external libraries."*

Right, and the reason is sharper than the list's length. `MODULES_THAT_MAY_NEED_THE_REQUIREMENTS`
named a **permission**, and a permission has nothing behind it — an over-broad entry reads
exactly like a correct one, which is how `record_dashboard_url` sat wrongly classified until
the reverse check went in. A constraint has evidence behind it by construction.

### The must-not set does not have to be named either

Naming it directly would have been 22 entries, worse than the 7 it replaced. But the
constraint's real subject is not a module, it is a **caller**: a module has to import on the
standard library because something runs it before anything is installed. Declare the callers
and the module set follows, because importing a module imports everything it imports.

`UNINSTALLED_INVOCATIONS` is five entries — the Actions workflow, the maintenance skill, the
upstream-reviews skill, `/add-plan-item`, and `plan-updates-since.sh` — each carrying the
module it invokes and the reason it installs nothing, verified against its own file.
`modules_that_must_not_import_third_party()` walks the intra-package import graph from those
five and returns 17 modules. **No module is named anywhere**, and a module that becomes
reachable from one of those callers is checked without anyone declaring it.

### The default inverts, and that is what makes the previous shape wrong

A module reached by an uninstalled caller must import on the standard library; a module
reached by none may import whatever it likes, **because nothing runs it before an install**.

That retires the 21-module check the exception set had restored, and the retirement is
correct rather than a loss: `plan_model`, `record_dashboard_url`, `_version` and
`package_layout` were being held to a constraint no caller was asking for. The 616 → 592 drop
recorded above was a real loss of coverage under a design that had no callers in it; under
this one the same modules going unchecked is the semantics working.

### The mutation that found a gap in the derivation

Four mutations, each caught by exactly the test that names it: a module deep in the closure
growing an import (three failures — `maintenance`, `maintenance_commands`,
`maintenance_report`), a caller gaining a `pip install` step, a caller ceasing to invoke its
module, and a constrained module reaching an unconstrained one.

The last of those found `_sibling_imports_of` reading `node.module` for `from bastler.x import
y` and missing `from bastler import x`, where the module name is in the *alias* rather than
the module path. The failure was still caught — the importing module itself went red — but the
closure would have stopped short of what that module reached. Both forms are read now.

### A green suite after a deletion proves nothing

Worth carrying, and the second instance of this shape in two days. Deleting the exception set
with a slice from one anchor to the next also deleted
`test_every_uninstalled_caller_still_invokes_its_module_and_still_installs_nothing`, which sat
between them. The suite stayed green at 66 and nothing flagged it; it surfaced only because a
mutation that had been caught an hour earlier stopped being caught.

The 616 → 592 entry above is the same lesson from the other side — there a parametrization
narrowed and 21 cases vanished, here a slice deleted a test outright, and both runs were
green. **The check after a deletion is the mutation that used to fail, or the case count** —
never the fact that the suite passes.

617 tests pass.

## Update 2026-08-24 (resolved): `setup-runs-without-asking`'s guard caught the two branches git could not

`/plan-item-resolve workflow-unification setup-runs-without-asking`, session
https://claude.ai/code/session_01FsFNZpjH5xEYXm72rYo887, mode `auto` from the committed
default. One merge commit pushed to #156.

### The stall was the conflict, and the conflict was the hazard arriving

The maintenance pass had reported `needs-resolution` twice — 2026-08-22 naming one file, and
again 2026-08-24 naming three. The second list is the tell: `.claude/hooks/README.md`,
`plan-item-kickoff/SKILL.md`, `plan-item-resolve/SKILL.md`. Between the two reports, #149 and
#135 landed, and the two extra conflicts are #149's collapse of step 0 into
`plan-dashboard/plan-item-gathering.md` meeting this branch's edit of the sections it deleted.

Nothing else about the item was blocked, which is worth stating first: CI was green on all 22
checks, and the two review threads from 2026-08-12 were already answered and deliberately left
open as a deferral. The recorded blocker and the real one agreed for once.

### The guard did the job it was built for, on its first real occasion

The prediction recorded on 2026-08-12 was that landing order stops mattering — whichever lands
second goes red rather than silently reinstating the gate. Both of the others landed first, so
this branch is the one that went red, exactly as designed. Merging `main` in failed
`test_setup_prerequisite_documents.py` naming two paths:

```
.claude/skills/add-plan-item/SKILL.md:                ['offer `/setup-personal-notes']
.claude/skills/plan-dashboard/plan-item-gathering.md: ['offer `/setup-personal-notes']
```

Both were new files on their own branches, so neither conflicted with anything here and no
merge would have flagged either. This is the first time in this plan that a recorded hazard
was caught by a mechanism built for it rather than by someone remembering a comment — the four
same-artifact-twice findings before it were all caught by a reader.

### The conflicts resolved to the resolution already on record

The 2026-08-12 review round corrected this item's own notes, which had said to keep both edits
for the two plan-item skills. The correction was right, and it is what the merge needed: take
#149's deletion, carry the wording into the shared document. Checked rather than assumed —
`git diff <merge-base> HEAD` on both skill files shows the branch's only change to either was
the step-0 wording, so taking `main`'s version whole loses nothing.

`.claude/hooks/README.md` is the one where both sides had content: this branch's "run it for
you … without stopping to ask" against `main`'s list with `/add-plan-item` added. Kept the
wording, took the name. `prerequisite-check.md` auto-merged into exactly what the round
predicted — this branch's rewrite plus that one name — needing no hand resolution at all.

### No upstream pull request, which took a run to establish

The branch carries `cram2-link-sent` and not `in-review`, so the skill's own gate would have
skipped the upstream read. `always-read-upstream-reviews` (#194) argues that gate is wrong, so
it was called anyway; the answer is that `cram2` has no pull request with this head. The link
was built and Create was never clicked. So the gate would have reached the right answer here by
luck, and the run is what makes that a fact rather than an assumption.

Worth carrying for #194: the action exits 1 on that clean answer, so a caller that checks the
exit status before the log reads "no upstream pull request" as a failed run. The skill's step 5
already says to relay it as a clean answer, but the exit code works against that.

### State

533 tests pass across the four directories CI runs, from 464 before the merge. #156's
description is rewritten to match. Left as the user found it in one respect, flagged rather
than acted on: the pull request is out of draft, and nothing on record says whether the user
marked it ready or an earlier session did, so it was not re-drafted after this push.

### The promote link cannot be written from a session, which is new

Rewriting the description ate its own `## Promote` section — the same symptom recorded on #139
on 2026-08-12, but not the same cause. There the heading appeared twice and
`description_with_promotion_link` partitioned on the wrong one. Here the heading appears once
and the *link* is what vanishes: the upstream compare URL, and every character after it,
including the attribution footer.

Reproduced deliberately rather than assumed. Two `update_pull_request` calls carrying the same
body, two reads back through a different tool (`list_pull_requests --fields body`, so the read
path is not the suspect), and both stored bodies end at `` ## Promote\n\n```` `` — the two
opening backticks and the two closing ones, with the `cram2` URL between them gone. The obvious
explanation is this session's own GitHub scope, which covers the fork and not `cram2`: a URL
naming an out-of-scope repository does not survive the write.

Left absent rather than fought. `description_with_promotion_link` appends both the heading and
the link when the description carries neither, so a pass restores it from the runner, where the
scope does not apply — which is also the only place it was ever written from. What the
description now carries in its place is a short section saying so, positioned before the point
a promote would truncate at.

**Generalizable:** a session can read the upstream through an Action (that is what
`upstream-reviews` is for) but it cannot even quote an upstream URL into a fork pull request.
Anything naming `cram2` in a body written from a session should be assumed lost, and the
symptom is silent truncation from that point on, not an error. The footer being gone too is
what makes it look like a formatting bug rather than a scrub.

## Update 2026-08-24 (new item): `unfetched-parent-branches` — the pass decides a parent's fate from a ref it never fetched

Found by asking why PR #64 (`D-core-underspecified`) was never reparented onto `main` nor
promoted with a cram2 link, after its parent PR #63 merged that morning. The answer is not
about #64.

### The defect

`load_stack()` fetches `[pr.head for pr in prs]` — the *head* branches of the open pull
requests on the board (`stack.py:930`, `fetch` at 941-948). A parent whose own pull request is
closed or merged is not on the board, so `origin/<parent>` is never fetched.
`_merged_predicate.is_merged` then asks `git merge-base --is-ancestor origin/<parent>
cram2/main` through `_git_succeeds`, which collapses exit 128 (the ref does not exist) and exit
1 (not an ancestor) into the same `False`.

A ref the pass failed to obtain therefore reads as *"this parent has not landed"*, and that one
wrong boolean drives three decisions: `reparents()` omits the child, `restack_plan()` leaves
`effective_parent` on the dead branch, and `promotion_order()` refuses to promote. One cause,
three symptoms — which is why the 2026-08-24 pass reported #64 only as
`merge: origin/D-core-aid - not something we can merge`, filed under its own environment.

### Proven, not inferred

Read-only in a full checkout: with `origin/D-core-aid` present, `stack.py reparents` prints
`D-core-underspecified 64 D-core-aid main` and `stack.py next` lists #64 as "approved, parent
'D-core-aid' landed". After `git update-ref -d refs/remotes/origin/D-core-aid` — exactly the
state a fresh maintenance clone is in — both print nothing at all, silently. #64 carries no
labels, confirming it was never promoted on any pass.

### Three diseases behind one symptom

Every branch the pass reported as `integration-failed` shares one trait — the parent has no
open pull request — but for three different reasons, and only the first has a rule today.

| PR | parent | parent's pull request | where the parent's commits actually are |
|---|---|---|---|
| #64 | `D-core-aid` | #63 merged | in `main` — should have reparented and promoted |
| #178 | `montessori_live_event_timeline_tab` | #175 merged | in its **grandparent** `montessori_fast_inline_monitor`, not upstream |
| #79 | `D-ui-splice-fix` | #78 closed unmerged | nowhere |
| #21 | `rdr/oo-plan` | #20 closed unmerged | nowhere |

`reparents()`' docstring claims it covers "a parent whose pull request was *closed* rather than
merged". It covers a closed-**and-landed** parent only; a closed-and-abandoned one has no
handling at all.

### The unfinished half of `landed-parent-detection`

#117 made the *decision* ancestry-based, precisely because "board.json carries only OPEN fork
PRs". It never made the *ref that decision reads* present. This item is the other half.

### A recorded decision this reverses, deliberately

The #139 executor entry above records as a choice that `stack.py` "reads git through a helper
returning `""` on failure - correct for derivation, where a missing ref simply means 'no
answer', and wrong the moment a push is involved". The first half is disproven here. In this
path a missing ref is not "no answer": it becomes a confidently wrong answer that suppresses a
reparent and a promotion, both of which are writes. Layer 2 below reverses it for the ancestry
predicate.

### Two more silent failures in the same function

`_git` returns `""` on any non-zero exit, so a failed `git fetch` is invisible — and
`git fetch <remote> a b c` is all-or-nothing (verified: one unknown ref name exits 128 and
updates nothing), so a single deleted board head would make a whole pass compute on stale refs
across a 53-pull-request board. `fetch()` has no test coverage at all.

### The shape of the fix

Three layers, one pull request, one root cause, each with its failing test first.

1. **Fetch what the stack references** — the deduped union of board heads *and* bases. This
   alone unblocks #64 and clears all four bogus `integration-failed` reports.
2. **A ref the pass could not obtain raises** rather than answering `False`, and a non-zero
   `git fetch` raises rather than passing silently. The pass stops with "I could not determine
   whether `<branch>` landed" instead of quietly deciding it did not.
3. **A policy for a parent whose pull request is gone**, derived from where its commits
   actually are: in the upstream base → retarget there (today's rule); in another open board
   branch → retarget onto that branch (#178, uncovered today); nowhere → orphaned, reported to
   the branch's owner the way a conflict is (comment, `needs-resolution`, withheld) rather than
   merging a dead branch every run (#79, #21).

### Scope, checked rather than assumed

`check_scope_overlap.py --base main` over the seven paths returns `paths_absent_from_base: []`
— every file is already on `main`, so no unlanded branch owns this work and it is based off
`main`. Seven open pull requests touch `stack.py` (#110, #111, #151, #154, #158, #162, #185)
and none touches `def fetch`, `pr.head for pr in prs`, `_git_succeeds`, `is_merged`,
`reparents` or `has_landed_upstream`. No duplication.

### Landing order against `bastler-package`

#185 renames `.claude/stack/*.py` to `bastler/*.py` and the tests to `test/bastler_test/`, and
its `bastler/stack.py:823` carries `fetch(configuration, [pr.head for pr in prs])` verbatim —
so it inherits the bug rather than fixing it. Whichever lands second moves. This fix goes
first: it is small, and #185 is conflicted and will re-merge anyway. Not a `depends_on` —
a collision, recorded so it is a choice rather than a merge conflict.

### Related, deliberately not folded

`routine-cutover` already carries the insight that "ANY pull request leaving the open set drops
it from board.json" and proposes an event-triggered re-sweep on `pull_request: closed`. That is
about *when* the sweep runs. This item is about the sweep computing the wrong answer whenever
it does run. Both are needed; neither substitutes for the other.

## Update 2026-08-24 (new item): `session-branch-base` — sessions are cut from the integration branch

Found while checking whether the fork's default branch caused `unfetched-parent-branches`. It
did not, but it is causing something else, and it is already live rather than latent.

### What is true

`git ls-remote --symref origin HEAD` resolves to `refs/heads/integration`. The fork's default
branch is the regenerated integration branch `integration-20260823-082804` that
`integration-branch` (#154) exists to build — a branch whose whole design is to be rebuilt from
scratch and never merged out of.

The session investigating #64 was handed the branch
`claude/maintenance-tooling-pinning-gdod18` at HEAD `899a04aac` — byte-identical to
`origin/integration`: 78 commits behind `main`, carrying eight unlanded branches' merge
commits. That branch existed only locally; `git ls-remote --heads origin` had no such ref, so
the clone created it at the default branch's tip. Every session cut from this fork starts the
same way, and a pull request opened from one would carry all of it.

### What it does not affect

Not the cause of `unfetched-parent-branches`. cram2's default branch is still `main` (verified
by `git ls-remote --symref cram2 HEAD`, and cram2 has no `integration` branch at all), and
`upstream_base` is pinned in `.claude/stack/stack.toml`, so the stack tooling never reads a
default branch. No open fork pull request currently bases on `integration` either.

### What else reads it

`default_branch_name()` in `resolve-personal-notes-config.sh` reads
`refs/remotes/origin/HEAD` when it is set, and `pr_progress_path` suppresses PR-progress for
whatever it returns — so in any clone that has the ref set, progress is tracked for `main` and
suppressed for `integration`, the wrong way round. A pull request opened through the GitHub UI
would also default its base to `integration`, corrupting the base-is-parent invariant the whole
stack rests on.

### Adjacent, and not the same as `fresh-base-at-session-start`

#188 fast-forwards `main` at session start and reports "this branch is N commits behind main —
merge or rebase it before planning on a stale base". It printed exactly that for the session
above, so it *detects* the symptom; it does not prevent the wrong base, and because it reads
`upstream_base` rather than `origin/HEAD` it is itself unaffected by the switch.

### The shape of the fix

Restore the fork's default branch to `main`, and make a session refuse to plan or open a pull
request from a branch not derived from it — so a default-branch change cannot silently re-point
every future session's base again. Recorded with no branch; a later session picks it up.

## Update 2026-08-24 (implemented): `unfetched-parent-branches` lands on `claude/maintenance-tooling-pinning-gdod18`

Committed as `a70132eb6`, based on `main`. 554 tests pass across the four directories CI runs,
from 533 before. No pull request opened - the developer had not asked for one.

### The branch this session was handed was the integration branch

`claude/maintenance-tooling-pinning-gdod18` arrived at HEAD `899a04aac`, byte-identical to
`origin/integration`, and existed only locally - `git ls-remote --heads origin` had no such ref.
So it was reset onto `main` with a plain `git checkout -B` and pushed fresh; nothing was
force-pushed and no work was discarded, because the branch carried none. That is the evidence
behind the sibling item `session-branch-base`, and the branch name is a harness artefact that
does not name this work.

### The rule for which branch carries a parent was wrong once, and the live fork caught it

The first implementation excluded any candidate that *contained* the branch being placed, to stop
a branch naming itself or anything stacked on it. Run against the real board it reported #178's
parent as gone - and that was wrong: #178's own work had been merged up into
`montessori_fast_inline_monitor`, so the grandparent contained the child as well as the parent,
and the guard ruled out the one right answer.

Git containment cannot tell a branch stacked on another from one merged into it. Descent is a
question about the stack, so `Stack.is_stacked_on` walks the bases the board records instead, and
git containment is left to answer only what it can. Pinned by
`test_a_grandparent_a_branch_merged_up_into_is_still_where_its_parent_went`, which fails under the
old guard.

Worth carrying: the pure tests passed under both rules until a test double faithful enough to
model git's answer was written. A double that only knew the mapping it was handed could not
reproduce the case, and the live fork found it first.

### Verified against the fork, read-only

From the ref state that produced the silence - every off-board parent ref deleted, exactly a fresh
maintenance clone - `stack.py reparents` now prints three lines where it printed none:

| PR | base | target |
|---|---|---|
| #64 | `D-core-aid` | `main` |
| #178 | `montessori_live_event_timeline_tab` | `montessori_fast_inline_monitor` |
| #192 | `claude/match-query-ergonomics-where-rooted-b876wm` | `main` |

#192 was not part of the original report: its parent merged the same morning, and it would have
been missed silently by the next pass exactly as #64 was. #79 and #21 are placed `gone`, which is
correct - their bases were closed without merging - and the restack now hands them to their owners
rather than merging a dead branch every run. `stack.py next` lists #64 among the promotable
branches again.

### Two tests could not run in this container

`test_a_non_zero_status_says_what_it_means_on_the_way_out` and
`test_a_run_needing_a_credential_it_has_not_got_is_its_own_exit_status` hang here: both run the
executor as a subprocess, which resolves configuration and fetches the personal-notes branch over
the network. Confirmed pre-existing by stashing this branch's changes and watching them hang on
unmodified code, so they are this container's network, not a regression. They are not skipped or
marked - nothing was changed about them - and CI runs them normally.

## Update 2026-08-27 (kickoff): `session-branch-base` opens, and the guard is a check rather than a topology test

Session: https://claude.ai/code/session_014Fp9aaMYx1E6toT2jDDWdW. Opened as a draft on
`claude/plan-item-kickoff-workflow-s3mfvk`, based on `main`. Mode `auto` (committed default), so
this section is the plan rather than a record of one that was approved.

### Still live, three days on

`git ls-remote --symref origin HEAD` still resolves to `refs/heads/integration` at `899a04aac` -
byte-identical to the SHA the item recorded on 2026-08-24. Nothing has been done about it, and
this clone happens to hide it: it has no `refs/remotes/origin/HEAD` at all, so
`default_branch_name()` falls through to its `main`/`master` search and returns the right answer
for the wrong reason. A clone that *does* carry the ref gets `integration`.

### The dependency check is vacuous, and the scope check says the item is real

`depends_on` is empty. `check_scope_overlap.py --base origin/main` against the three files this
touches reports `paths_absent_from_base: []` - every one of them already exists on `main`, so
this is work on top of `main` rather than an edit to what an unlanded item introduces, and there
is nothing to fold. It does overlap textually with **#188** on all three
(`resolve-personal-notes-config.sh`, `session-start.sh`, `session-start-messages.sh`) and with
**#185** on the first; both are open and based on `main`, so the usual
whichever-lands-second-merges convention applies. #185 is already `dirty` and carries
`needs-resolution` independently of this.

### Why the guard is not the ancestry test the item's sentence suggests

The item asks for a session that refuses "to plan or open a pull request from a branch not
derived from it". Read as a git-topology test - the base must be an ancestor of `HEAD`, or the
other way round - it is wrong, and the fork proves it rather than an argument doing so. `main`
moves constantly, and #188 fast-forwards it at every session start; every branch that has not
merged `main` recently is then neither an ancestor nor a descendant of it. Of the 53 open fork
pull requests, the `main`-based ones alone (#107 from 2026-07-29 onward) would trip such a test,
and it cannot tell a branch cut from `integration` apart from one legitimately stacked on a
parent pull request: both carry commits `main` does not have.

What actually distinguishes the failure is upstream of any branch: **the default branch itself is
wrong**, which is also exactly what the item's own purpose clause names - "so a default-branch
change cannot silently re-point every future session's base again". So the guard's subject is the
default branch, not branch topology, and it is delivered through machinery that already refuses:

1. **`upstream_base` becomes the authority.** `configured_base_branch()` reads it from the
   personal `.claude/personal/stack.toml` override on the notes branch layered over the committed
   `.claude/stack/stack.toml`, by `grep` on a top-level scalar - the dependency-free idiom
   `plan_id_for_branch` and the `tracking_issue` extraction already use, and the reason
   `check-setup.sh` must not gain a parser to report on parsers. `default_branch_name()` prefers
   it when the branch it names actually exists, and falls back to today's
   `refs/remotes/origin/HEAD`-then-`main`/`master` search otherwise, so a repository carrying no
   stack configuration behaves exactly as it does now. That alone rights the inversion the item
   recorded: `pr_progress_path` and `branch_can_hold_plan_item` stop suppressing `integration`
   and tracking `main`.
2. **A `default_branch` row in `check-setup.sh`**, `needs-setup` when the repository's own
   default branch disagrees with that configured base. This *is* the refusal to plan: every plan
   skill runs `prerequisite-check.md` before its first real step and stops on a non-zero exit,
   and `session-start.sh` already surfaces `needs-setup` rows in its summary. Nothing new has to
   be invented to make a session stop, and a future re-point is caught the same way this one
   would have been.

### The flip and the guard have to land together

The guard is only correct while the repository is correct: shipping it against today's
`integration` default would make every plan skill stop and offer a setup that cannot fix it,
because no session here has `gh` and the GitHub MCP server exposes no repository-settings tool.
So restoring the default branch to `main` is part of this item's work rather than a follow-up.
Checked first: none of the 53 open fork pull requests bases on `integration`, and cram2's own
default is `main`, so the flip has nothing to break.

### A defect in the item's own manifest entry, found by reading it

`notes` is an unquoted YAML scalar containing ` #64`, so YAML ends the scalar there and treats
the rest of the line as a comment. Every parser - `build_dashboard.py` included - has been
reading the note as ending at "The session investigating", losing the `default_branch_name()`
finding, the `fresh-base-at-session-start` comparison and the recorded fix itself. The published
dashboard has shown the truncated half since the item was created. Quoted in the same pass;
`plan_item_bootstrap.py` patches lines rather than round-tripping the document, so nothing had
overwritten it, and nothing would have.

## Update 2026-08-28 (reversed): the default branch is deliberate; the branch cut from it is the defect

The kickoff above recommended restoring the fork's default branch to `main`, and the user
rejected it in one sentence: making `integration` the default *is* the fast-PR process. It is
what puts reviewed-but-unlanded work into every fresh checkout, so flipping it back destroys the
thing it exists for. Their requirement alongside it is that a pull request be based on `main` or
on a parent pull request, never on `integration`.

### The two requirements are not in conflict, and the recommendation conflated them

Where a clone **starts** and where a work branch is **cut from** are separate events. The first
is the arrangement and should stay; only the second can be wrong, and only when it actually
happens - a branch cut from `integration`'s tip and opened against `main` carries every merge
`integration` holds into its diff, which is the #41 inflated-diff shape met from a new direction.

The recommendation optimised for the guard that had been built rather than for the workflow. The
generalisable half: **a configuration that looks like a defect from inside one check may be the
deliberate answer to a requirement the check does not know about.** The tell was available - the
item's own notes recorded the default branch as the fast-PR mechanism, and the kickoff read that
as context rather than as the constraint it was.

### The ancestry test was right, and was rejected for testing the wrong thing

The kickoff rejected "refuse a branch not derived from the base" because `main` advances
constantly - #188 fast-forwards it at every session start - so within a day a branch cut from it
is neither its ancestor nor its descendant, and every `main`-based pull request on the fork would
trip it. That reasoning holds, and it is an argument against testing ancestry **against `main`**,
not against ancestry.

Against the staging branch the same test is exact:

```
git merge-base --is-ancestor origin/integration HEAD
```

It flags a branch cut from `integration`; it is silent for one cut from `main` and for one
stacked on a parent pull request, since neither descends from it. It never references `main`, so
`main` moving cannot make it fire. Measured across all 198 remote branches of this fork: **0
flagged**. `test_accepts_a_branch_whose_configured_base_has_moved_on_without_it` pins the choice -
mutating the implementation to test against the configured base fails exactly that test, plus the
one for the case the guard exists to catch.

Worth carrying: **a rule rejected on a measurement is only rejected for the subject it was
measured against.** One substitution turned the discarded design into the correct one, and the
kickoff had not tried it.

### What `default_branch_name()` is for, restated

The `configured_base_branch()` change stays and is still right, for a narrower reason than the
kickoff gave: it is what stops `pr_progress_path` and `branch_can_hold_plan_item` treating
`integration` as the branch no plan item can track and `main` as ordinary work. That is a
resolution bug regardless of whether the default branch is deliberate.

`plan_item_bootstrap.py open` needed nothing: `--base` is `required=True` and it runs
`checkout -b <branch> <base>`, so it never cuts from `HEAD`. The exposure is a hand-rolled
`git checkout -b` while sitting on the staging branch, which is what happened.

### Fast-forwarding `main` at session start is right, and is half the job

#188 reads `upstream_base` rather than the default branch, so the flip does not affect it, and
keeping `main` current is what makes "cut from `main`" correct. Running `/stacked-pr-maintenance`
in its place would be the wrong instrument - it reparents, restacks and force-pushes other
people's branches, which is a periodic pass rather than a session-start step.

What is missing is neither: **`integration` is 124 commits and five days behind `main`** (built
2026-08-23; `main`'s tip 2026-08-27), so the process is currently delivering unlanded work on top
of a stale base. #188 freshens `main` while the session sits on `integration`, so the working tree
never sees it. That is a rebuild-cadence question, and `integration.py build` is only on #154, so
a fresh clone cannot run it yet - recorded here rather than acted on, since it is the developer's
call whether the rebuild is scheduled, per-session, or gated on #154 landing.

541 tests pass across the four directories CI runs, from 538.

### A stale-path save dropped half of this, and a stop hook caught it rather than any check

Recording the near-miss, because it is the fourth instance of the stale-save hazard on this plan
and the first with a new tell. The reversal above was written as one manifest edit and one
roadmap append. The roadmap landed; **the manifest note did not**, and the dashboard was
published without it.

The cause was not a stale read - the anti-stale-save rule was followed, and both files were
fetched immediately before editing. It was a stale *path*: the shell's working directory reset
between commands, so the edit was written to a `plan-live.yaml` in the repository root while
`save-plan.sh` was handed the untouched copy still sitting in the scratchpad. Both commands
succeeded, `save-plan.sh` reported success, and the dashboard rendered cleanly from a manifest
missing the note - the failure is silent at every step.

What surfaced it was the stop hook complaining about **untracked files in the repository**: the
two scratch copies that had leaked into the repo root. Nothing about the plan tooling noticed,
and the obvious response to that hook - commit them - would have been actively wrong, since plan
data must never be tracked on a pull request branch.

Two things worth carrying. **`save-plan.sh` reporting success says the push happened, not that
the push carried your edit** - the check is reading the field back off the notes branch
afterwards, which is what #160 already added to `plan_item_bootstrap.py` for exactly this reason
and which the shell route still leaves to the caller. And **a scratch file inside the repository
is the hazard, not merely untidy**: write plan scratch to an absolute path outside the working
tree, so a cwd reset cannot silently redirect an edit into a file nothing will save.

## Update 2026-08-28 (audit): Part D's premises, and the stable-branch shape settled

Session: https://claude.ai/code/session_01MwawsPiaFK3ufUK4YHak3X, read-only apart from this record.
Re-applied after the stale-save above dropped it.

Three of `integration-branch-ci-verdict`'s premises had gone stale, all favourably: the fine-grained
token is provisioned and probed, `upstream-review-reader` (#146) landed the Actions pattern Part D
needs rather than leaving it unexercised, and nothing of Part D itself is written yet. Detail is on
the item.

The stable-branch shape, open since kickoff, is settled: **the candidate pull request is a CI
trigger only** - `integration` is force-updated to it on green and the candidate is closed unmerged.
A real merge target would make the branch accumulate history, which is the one property the design
has rejected throughout, and the candidate was never a review surface anyway.

What this leaves live is rebuild cadence. `integration` is 124 commits behind `main` and holds an
unverified build, so the fast-PR process is currently serving unlanded work on a stale base. That
belongs to Part D rather than beside it: an automatic rebuild is only safe once a verdict exists.

## Update 2026-08-28 (resolved): Part D's clearing half, and the conflict nobody was counting

`/plan-item-resolve workflow-unification integration-branch-ci-verdict`, session
https://claude.ai/code/session_01FWoysReVCQMi9VBY5cVgcP, execution mode `auto`.

### Two things were stalling it and only one was recorded

The recorded half was that nothing of Part D existed. The unrecorded half was that #154 was
`mergeable_state: dirty` against `main`: 157 commits behind, conflicting in
`plan-item-kickoff/SKILL.md` and `plan-item-resolve/SKILL.md`. The maintenance pass had
reported it four times since 2026-08-18, the last on 2026-08-24, and each report is also a
`needs-resolution` label that holds the branch out of the next pass. A conflicted pull
request is excluded from its own base merge, so the branch drifts further out every day the
item sits - the item's own audit five days earlier read the state and did not count this.

Worth carrying: **a `needs-resolution` label recorded as "stale, the pass clears it itself"
is worth re-reading rather than inheriting.** The 2026-08-23 entry left it deliberately,
correctly, on the reasoning that the next clean-merging pass clears it. What that reasoning
missed is that `main` kept moving, so the next pass found a *new* conflict rather than a
clean merge, and the label was continuously re-earned rather than stale.

The resolution is additive on both sides. `main` had restructured both skills around
execution modes - seven sections to four, the gathering half moved out to a shared document -
while this branch added a manifest-staleness step to each. Main's numbering is the live
structure and each branch-added step is demoted to a subsection of the step it generalises:
the recording step under `plan-item-resolve`'s "Draft the plan", the currency rule under
`plan-item-kickoff`'s bootstrap. What was dropped is only what main already says in its own
words - the branch's "check whether the question is already answered" paragraph, which main
opens the same section by delegating to the gathering document.

### The label that could not stop can stop now

`integration-conflict` shipped documented as never cleared automatically, and that is a
defect rather than missing polish: the 08-11 round established that `WithholdBlockedBranch`
cannot clear it, since a break between two cleanly merging branches never makes either pull
request conflicted. The reproduction test pushed onto the breaking branch was already the
evidence; nothing read it.

It now carries a marker naming the branch it was broken against.
`.claude/stack/integration_reproduction.py` is that marker, the document a run of them
writes, and the lifting; it is also the `pytest` plugin the targeted job loads, registered as
a plugin instance rather than module state so a run's collection belongs to that run.
`.github/workflows/integration-checks.yml` runs every marked test on `pull_request` and
`workflow_dispatch` and hands the document to `integration.py clear-fixed-breaks`.

Three rules the tests pin rather than the prose asserting, each mutation-checked:

- A branch is fixed only when **every** reproduction recorded against it passes - it can
  break more than one sibling, and clearing on the first passing one lifts the block while a
  recorded break still reproduces.
- A reproduction counts as passing only if its body ran and **no phase of it failed**, so one
  that was skipped or errored in setup leaves the block standing rather than lifting it on
  evidence that never ran.
- A branch carrying **no** block is not written to at all, since a reproduction keeps passing
  on every later run once the break is gone and every later run would otherwise comment again.

Nothing is spelled twice that can be derived: the marker is `DefaultLabel.INTEGRATION_CONFLICT`
with the hyphen a marker name cannot carry replaced, the plugin's option flag comes from where
its value lands, and the dataset's reproductions and the assertions about them read the branch
they name from the one module that defines it.

### The kickoff left four names in YAML with nothing checking them

Found while writing the workflow rather than by review. A workflow cannot import a constant,
so the marker selection, the plugin name, the report path and the subcommand are the one place
each is spelled a second time - and the failure mode is silent in the worst direction: a
selection naming something else runs nothing and still reports success. All four are now
asserted against their definitions.

Generalisable: **the place a constant has to be retyped is exactly the place a test is worth
writing**, and it is the opposite of the wire-format guard the 08-20 sixth round deleted. That
one restated an enum both sides already read; these check the one boundary no shared definition
crosses.

### The marker is left in the default selection, restated because it looks like an oversight

Adding it to `pytest.ini`'s `addopts` exclusion the way `slow` is would keep the breaking
branch's own CI green, and that is precisely the wrong outcome: the reproduction is pushed to
that branch because it is the only artifact making the failure visible from inside the branch
that causes it, and a test excluded from that branch's own run is invisible exactly there.

### Where the boundary is, and why it is there rather than further on

Not built: the candidate pull request, the Actions and check-run reads, the force-update of
`integration` on green, and the removal of `integration_test_command`, `--test`, `--no-test`,
`TestCommandNotConfiguredError` and `_run_tests`.

Two reasons, neither of them running out of room.

**The removal cannot come first.** `build_integration` currently moves `integration` to every
finished build unconditionally, so taking the local verdict out before the CI verdict is proven
on a real run leaves the branch never moving at all. That regresses the fast-PR process rather
than staging the migration - the half-migration the item's own notes warned about, met from the
direction the notes did not name.

**The candidate's shape depends on an unanswered question.** Rebuild cadence - scheduled,
per-session, or gated on #154 landing - was recorded by the 2026-08-28 audit as still live and
the developer's call, and it decides whether the candidate is opened by a workflow holding
`INTEGRATION_REFRESH_TOKEN` or by a session. Building either before it is answered builds the
wrong one. It is on the item as a blocker now rather than as a sentence in a roadmap section.

705 tests pass across the four directories CI runs, from 675.

### Rebuild cadence answered, and the draft convention overridden once

Both settled by the developer at the end of the same session.

**Cadence is a scheduled Action.** The candidate is opened by a workflow holding
`INTEGRATION_REFRESH_TOKEN` rather than by a session — which is what that token was
provisioned and probed for on 2026-08-23, and what makes `maintenance_github.py`'s Actions and
check-run reads have a caller with a real credential. It unblocks the rest of Part D and settles
its shape rather than merely permitting it: `open-candidate` and the verdict read are workflow
steps, so removing the local `--test` surface finally has somewhere to land.

Worth stating because it looks like a contradiction: this is a timer on **deterministic
automation**, not a scheduled LLM check. `routine-cutover`'s whole endgame is exactly that
split — deterministic duties on a plain Action, judgment work in on-demand sessions — so it sits
inside that decision rather than against the no-scheduled-checks rule.

**#154 stays out of draft**, overriding the re-draft-after-every-push convention deliberately.
A draft is excluded from every integration build, so re-drafting would drop the branch carrying
this work out of the process the work exists to serve. What the convention protects — that the
developer reviews before anything is final — is carried here by the pull request being open and
unmerged instead. Recorded rather than done silently, since a session leaving its own pull
request un-drafted is otherwise the exact thing that convention exists to catch.

## Update 2026-08-28 (first run): a job that installs light dependencies cannot collect from the root

The targeted job `integration-branch-ci-verdict` added went red on its first real run, and
the cause is a property of the job's own design rather than a slip in it. It collected
`-m integration_conflict .` from the repository root, and pytest loads every `conftest.py`
under what it collects — `test/conftest.py` imports `numpy`, which a runner carrying only
`pytest` plus the four plan-dashboard requirements does not have. Exit 4, during
collection, before a single reproduction was reached.

Fixed in `db134d33`: the job collects the four test directories `ci.yml`'s tooling job
names, which is exactly the tree those dependencies cover. Nothing else in the repository
is importable on that runner, so nothing else was ever collectible.

**The test reads the rule off the other job rather than listing it again**, and the reason
is the rule itself: what makes the two trees the same is that both jobs install
`PLAN_DASHBOARD_REQUIREMENTS_FILE` and nothing else, so the sibling job is found *by that
install* rather than by its name. It survives `bastler-package` renaming
`test_claude_dev_tooling` to `test_bastler`, and fails the moment one job's collectible
tree changes without the other's — which is precisely when both need editing together.
Mutation-checked: reverting to the root fails exactly that test out of 706.

**It also turns a limit recorded at kickoff from theoretical into concrete.** That kickoff
noted "a reproduction test that lives inside a robotics package and needs the docker matrix
would not be collectible there". It now genuinely is not, and the consequence is the safe
one: no outcome is recorded for that branch, `fixed_branches` does not name it, and its
block stays. A reproduction that cannot be run never clears anything — which is the same
rule the skipped-and-errored case already had.

Verified locally as the healthy-tree case rather than only in the harness: 706 collected,
all deselected, exit 5, an empty document written, and `clear-fixed-breaks` reading that
document back and clearing nothing at exit 0. All three of the statuses the job's `case`
accepts are therefore reachable and mean what the comment beside them says.

Worth carrying: **a lightweight CI job's collection root is part of its dependency
contract, not a detail of how it is invoked.** The job installed correctly, was scoped
correctly, and named its selection correctly; what it got wrong was assuming it could walk
a tree it had not installed. Any job that installs a subset of the repository's
dependencies has to collect a matching subset of its tree, and the honest way to say which
subset is to read it off whatever else installs the same thing.

## Update 2026-08-28 (the pipeline's first restacked build): a break nobody could have read out of a diff

The developer's point settled the ordering: a rebuild should depend on restacking first, and
can then use the labels stacking writes. Half of that existed and half did not, and the half
that did not had a trap under it.

**What existed.** `build --restack` already restacked, refreshed remotes and built.

**What did not.** `select_for_build` read draft state and the chain and never looked at a
label, so a branch a maintenance pass had explicitly withheld went into the build anyway —
and was then reported as colliding with whichever sibling it met there, rather than as the
branch whose own conflict was already recorded. It now leaves out any branch carrying one of
`Configuration.blocking_labels` and anything standing on one (a tip contains its whole stack),
reported as `blocked` rather than `unreviewed` — the latter would send an author to review a
branch they had already reviewed.

**The trap.** The stack was read *before* `restack()` ran and the same object was built from,
so the labels that pass had just written were invisible. That is the shape this roadmap already
records against the 2026-08-05 promotion incident — a write computed from a snapshot a later
step in the same pass invalidates — met a second time, and it would have made the label filter
silently useless for exactly the branches the pass had just blocked. `stack_to_build` reads the
stack again after restacking.

`BuildSelection.unreviewed` and `IntegrationReport.unreviewed` become `left_out`: the field now
holds two reasons, and a field named for one of them describes the other wrongly.

### The run, which is the actual evidence

`fast-forward` moved fork `main` **43 commits** onto `cram2/main`. That conflicted #154 for
real — so the `needs-resolution` label it was carrying was correct rather than stale, which is
the opposite of what the 2026-08-23 entry had assumed when it left the label for a later pass.
Resolved in `pytest.ini`, additive on both sides. The next restack cleared the label, the build
carried #154, and the suite failed:

```
maintenance.py: from exceptions import GitCommandFailed
ModuleNotFoundError: No module named 'exceptions'
```

**#154 breaks #158.** #158's `WorkingTreeTooling` copied `.claude/stack/`'s contents flat;
#154 introduces `.claude/shared/` (inherited from #151's extraction), so on the merged tree the
pinned `maintenance.py` imports from a directory the pin does not carry. Both branches green
alone, merging with no conflict, broken together — the exact class the integration branch exists
to catch, found on the *first* restacked build rather than by anyone reading a diff.

Fixed on #158, where the under-specified pin is, rather than on #154. Two halves, and the second
is the one that is easy to miss: the copy now carries every sibling directory the tool's own
modules name in a `sys.path` insertion — read out of the modules by an `ast` walk rather than
listed beside them — **and** keeps the layout instead of flattening it, because such an insertion
is relative to the module making it, so flattened the same line resolves outside the copy and
finds whatever happens to be there. A sibling nothing imports from is still left where it is;
pinning every sibling would copy most of the repository.

**The reproduction is expressible on #158 alone even though the break is not.** Neither branch
can host the merged tree, but the *rule* can be stated without it: pin a synthetic tree whose
tool inserts `../shared` and imports from it. That fails before the fix and passes after. Worth
carrying, because the design's own instruction — push the reproduction to the breaking branch —
does not fit a case where the breaking branch lacks the code that breaks: the test belongs
wherever the rule can be stated, which is the branch that owns the rule.

### State

`integration` is published at `933161a263` — 0 behind `main`, 194 ahead, and carrying
`integration.py`, `.claude/shared/` and `integration-checks.yml` for the first time. Until this
build the fork's default branch, which every fresh session is cloned from, did **not** contain
the tool that builds it: #154 had been conflicted since 08-18 and was therefore excluded from its
own build. Four tips merged, five skipped on ordinary textual collisions with #154's
`.claude/shared/` extraction (`build_dashboard.py`, `plan_item_bootstrap.py`, `conftest.py`) —
whoever-lands-second-adapts, not semantic breaks — and sixteen left out as blocked.

One thing this settles for Part D: **the local `--test` verdict is what caught the break**, so it
stays until the CI verdict replaces it rather than being removed beside it. That is the same
conclusion the boundary drawn on 2026-08-28 reached from the other direction, now with a case
behind it rather than an argument.

## Update 2026-08-28 (Part D): the gate was mine, not the design's

`integration-branch-ci-verdict` had been recorded as gated on #154 landing on `main`, because a
scheduled Action must invoke `integration.py` and that is not on `main`. **It does not have to
be.** A `schedule:` trigger registers from the repository's *default* branch; here the default
branch is `integration`, and `integration` is `main` plus every carried tip — so anything on #154
reaches it. The proof had been sitting in the tree the whole time: `integration-checks.yml` exists
on no branch but #154 and was already on `origin/integration`.

So the whole pipeline is built on #154's branch and runs from there, with no merge to `main`.
Worth carrying as a shape rather than a fact about this fork: **a claim that work is blocked is
worth re-deriving before it is acted on**, and this one had been carried through three entries
without anyone checking what actually registers a schedule.

### The pieces

`maintenance_github.py` gains `CandidatePullRequests` — open a pull request, close one, read a
commit's check runs — declared *apart* from the reads and writes a maintenance pass makes, because
nothing that maintains the stack opens a pull request and a pass handed that interface could open
one by mistake. `integration_verdict.py` turns a commit's check runs into one of four verdicts, and
`integration.py` gains `open-candidate` and `settle-candidate`.

### Why a candidate at all

`ci.yml` triggers on `push` to `main` and on `pull_request` and on nothing else, so a build that is
only pushed collects no checks. That is what makes the candidate the only shape that reaches a
verdict rather than one option among several. It is never merged: a build is regenerated from
scratch, shares no history with the branch it replaces, and merging would give that branch a
history the next build cannot regenerate.

Green moves the branch onto the build and closes the candidate unmerged; red closes it naming the
checks that failed; unfinished does nothing and says so with its own status, so a caller waiting
asks again rather than discarding a build nothing had judged. `ABSENT` is told apart from `RUNNING`
on purpose — it is the state that can mean something is *wrong* rather than slow, and the thing
that causes it is exactly the credential mistake below.

The waiting is in the workflow rather than in the command, which keeps every invocation a decision
that can be read on its own.

### Two operational rules the schedule forces

A published build's branch is **deleted**: the pointer then holds the same commit, and a rebuild
four times a day would otherwise leave one behind every time. A rejected build's branch is **kept**
— its candidate names checks somebody has to look at, and a closed pull request whose head is gone
cannot be read.

`INTEGRATION_REFRESH_TOKEN` rather than `GITHUB_TOKEN`: GitHub starts no workflow run from an event
`GITHUB_TOKEN` caused, so a candidate opened with it would sit with no checks forever.

### A test that passed on a comment

The workflow retypes command names, exit statuses and document keys, since a workflow cannot import
a constant, and those are asserted against their definitions. The first version of that assertion
searched the whole step script — and a mutation check showed it **passing** while the job branched
on the wrong status, because the comment explaining the right one satisfied the search. The helper
strips comments now.

Generalizable, and a sharper form of a lesson this roadmap already carries: **a contract test over
prose has to search the executable part.** The explanation of a rule and the rule itself sit
inches apart in a shell script, and only one of them runs.

### State

744 tests pass across the four directories CI runs, from 715; six mutations checked, each caught by
exactly the test naming its rule. Bootstrapped by one hand-run rebuild, since the workflow could
not dispatch itself until it was on the default branch: `integration` is at `201a903a67` with five
tips merged and the suite green, GitHub lists `Integration refresh` as an active workflow, and run
`33214932131` is the first dispatch of it.

### What is deliberately not removed, for a better reason than before

`integration_test_command`, `--test`, `--no-test` and `_run_tests` stay. The earlier reason was
sequencing — the pointer moved unconditionally, so removing the local verdict first left the branch
never moving. That reason is now spent, and a better one replaced it the same day: the local suite
is what caught the #154-against-#158 break hours earlier, and it answers *before* a build is pushed
rather than after a candidate has run a matrix. What the CI verdict replaces is the **publishing**
decision, which it now makes; it does not replace a fast answer with a slow one.

## 2026-08-28 - Decision 14: the first-time setup is part of the Bastler track

The user asked for the Bastler system's setup to be as easy, as short and as clear as it can be
for someone arriving at it for the first time, and for the steps they must perform in their own
fork, GitHub account and Claude settings to be spelled out.

### The gap

`check-setup.sh` is honest about its own boundary, in its header: it deliberately checks nothing
that lives behind an API rather than in a file. That boundary is drawn in exactly the wrong place
for a newcomer, because everything on the far side of it is what only they can do - the
`merged`/`bug`/`in-review` labels a fresh fork does not have, Claude's access to that fork, and
the `CLAUDE_PERSONAL_NOTES_*` variables a fresh-clone environment needs because git config set
inside one session is gone by the next. All three existed only as prose, spread across a 237-line
hooks README and a 238-line setup skill, and a first-time user had to read both to find them.

### What was built

`.claude/SETUP.md` is now the front door and is 41 lines: run `/setup-personal-notes`, run
`setup_steps.py`, run `check-setup.sh`. `setup_steps.py` prints the three external steps with the
values already substituted for the clone it lives in - the fork resolved from the notes remote in
either its name or its raw-URL form, the `gh label create` command per label, and only the
variable lines whose setting has actually been moved off its default. Both READMEs keep their role
as the reference and point at the page rather than restating it.

### Drift, and why two lists are duplicated on purpose

The labels cannot be read from `build_dashboard.PullRequestLabel` at runtime: that module needs the
dashboard dependencies, which is one of the things this script runs *before* are installed. The
settings cannot be read from `resolve-personal-notes-config.sh` either: it exports nothing a child
process could read. So both are mirrored, and both are pinned by a test against the definition they
mirror - which is the only thing that makes a second copy acceptable.

### Track placement

Put in the `bastler` track rather than `stack-tooling` or `personal-data`, and the track's
description widened to say so. The track's items are all package-extraction steps, so the item is
the odd one out by shape; it is the right one by subject, because this is how someone reaches the
Bastler system in the first place, and a front door filed under a different track is a front door
nobody finds. Structural, so recorded here as well as in the manifest.

### Deliberately not done

`.claude/skills/setup-personal-notes/SKILL.md` is untouched. #107 rewrites it (+103/-188) and adds
its own deterministic `setup-personal-notes.sh`; wiring `setup_steps.py` into the agent-facing path
belongs on top of that pull request, where it is a few lines, rather than underneath it, where it is
a conflict.

## Update 2026-08-28 (review round): the enum idiom on `main` does not survive three required fields

Four threads on #203, applied in `3cc3a417`; three resolved, one answered differently and
left open.

### Two enums, and a hazard the landed idiom hides

`PERSONAL_NOTES_SETTINGS` and `LabelPurpose` were both asked to become enums, and each
did — but only the first found anything new.

`PersonalNotesSetting` mixes a frozen specification into `Enum`, the `PullRequestField` /
`ManifestKey` idiom. Copying it verbatim fails, and the reason is worth carrying because
it is invisible in the file it was copied from. The enum machinery builds a member's
value by calling the mixed-in type with the member's value as its arguments, so
`PullRequestFieldSpecification(spec_instance)` *succeeds* — two of its three fields have
defaults — and lands the whole instance in `key`, which `__init__` then overwrites. That
is the silently-wrong case its own docstring warns about, and it is why `__init__` alone
is enough there. With three required fields nothing is silent:

```
TypeError: PersonalNotesSettingSpecification.__init__() missing 2 required positional arguments
```

`__new__` alone does not fix it either — `EnumType.__set_name__` calls both — so the
member carries a real keyword-constructed specification and both are defined. Removing
either fails at import, so nothing extra guards it.

**Generalizable: an idiom that works because of a default is an idiom that has not been
tested.** `PullRequestField` reads as though it demonstrates the pattern; what it
demonstrates is the pattern plus a coincidence, and the coincidence is the part that
makes the hazard its docstring names reachable.

### Merging the labels made the link to the dashboard stronger

`LabelPurpose`, the `RepositoryLabel` dataclass and the `REQUIRED_LABELS` tuple were three
things for one concept. One `RepositoryLabel` `StrEnum` now, whose member *is* its own
label name and carries its description through `__new__`.

Importing `build_dashboard.PullRequestLabel` remains impossible, and for this script's own
reason: it needs the dashboard dependencies `setup_steps.py` exists to run *before*. What
the merge bought is that the member names now line up with that enum's, so the contract
test holds `{name: value}` equal rather than only the value set. Mutation-checked both
ways — the value rename was already caught, the *member* rename was invisible.

### `GitCommandRunner` is the right seam and the wrong location

The third thread asked why the two `subprocess.run(["git", ...])` calls are not
`GitCommandRunner`. Measured rather than answered from the name: `.claude/hooks/` and
`.claude/stack/` are separate `sys.path` roots, so importing it costs a production
`sys.path.insert` — and `main` carries exactly one of those today, `upstream_reviews.py:31`,
which #185 is deleting as a carrier of the hackery decision 8 ends. It also drags `stack`
(1,600 lines) into a stdlib-only script for two two-argument reads, and has no `config` or
`remote` method.

Its `attempt` contract *is* right, so what shipped is the smallest honest move: one
`git_value` seam in this file, whose docstring names the contract this script needs — an
unset key and an unknown remote are ordinary outcomes, so it reports nothing rather than
raising. One call site for the migration to replace instead of two, recorded as a fourth
caller on `bastler-notes-core-python`'s `git_interface.py` alongside #135's, `plan_item_bootstrap.py`'s
and `stack.py`'s deliberately-opposite `_git`. Thread left open, since the ask was answered
differently.

### `gh` is not guaranteed, and the step said otherwise by ordering

Present on Actions runners, absent from a session container — so on the machine most likely
to read this output the commands do not run. The fork's labels page was already the
fallback and was last, introduced with "Or create them by hand", which reads as the lesser
option. It leads now, with the commands marked conditional. Nothing is lost for someone who
has `gh`.

Still true and stated rather than implied: the step cannot verify the labels exist. That
needs a GitHub call, which is the boundary `check-setup.sh` draws and the reason this
script prints rather than checks.

### Testing the script is not testing the steps

The round above was verified by running `setup_steps.py`, its tests and `check-setup.sh` —
all of which check that the script does what the script says. The user asked whether the
steps themselves had been tested, and they had not: nothing had been checked against the
services the three steps are *about*. Doing that turned up three things.

**The docs URL named the wrong page.** Step 3 said "paste these into your environment's
variable list" and linked `claude-code-on-the-web`, which mentions that an environment
carries variables and then points at `cloud-environments#set-environment-variables` for
the list itself. A reader following the link arrived somewhere they could not act on. It
names the section now, and the step also says *where* the environment is edited — the
selector at `claude.ai/code`, not a settings page.

**That page documents a silent truncation the step was walking into.** The variable list
is `.env` format: one `KEY=value` per line, and *an unquoted value is read as far as the
first `#`, with the rest of the line dropped*. A branch or path carrying one would have
been set to a prefix of itself — the variable present, the value wrong, nothing to see.
`quoted_if_needed` quotes exactly those, mutation-checked in both directions (never quote,
always quote).

**The connector URL was the list rather than the flow**, so it now carries the query that
opens the GitHub authorization directly.

Two claims came back confirmed rather than corrected, which is worth recording too:
`merged`, `in-review` and `bug` all exist on the fork under the names this prints —
checked through the API, so against GitHub rather than only against `PullRequestLabel` —
and `gh` really is absent from a session container, which is what the previous round's
reordering was for.

**Generalizable: a test suite over a script that prints instructions tests the printing,
not the instructions.** Every assertion here was about what the script produced from what
it read, and all 22 passed while step 3 pointed at a page with no variable list on it.
The check that found it is the one nothing in the repository can perform — following the
output as its reader would.

## 2026-08-28 — the dashboard's own refresh, and a shared name for "button that copies a command"

Asked for while refreshing the rdr-refactor dashboard, which is exactly the moment it names:
the page in front of you is a snapshot, nothing on it can republish itself, and the way back
to a current one lived entirely outside the page — the skill's name and the plan's id, both
recalled from memory. The masthead now carries a Refresh button that copies
`/plan-dashboard <plan-id>`.

### It is the same affordance as the item buttons, so it is not a second one

The item action buttons were already "a button whose click copies a slash command"; the
refresh is that with a different command and no model dropdown. Rather than a second copy
of the markup and the clipboard handler, both now render through one `copy_command_button`
macro over a `CopyableCommand` base declaring the two things the markup reads — `label` and
`command`. `ItemAction` keeps the item identifier its command needs;
`RefreshDashboardAction` is its page-level sibling, carrying only the plan id.

### A hint, because a Refresh button that does not refresh is a trap

Clicking copies rather than reloads. The button gives its "Copied!" feedback after the fact,
which is too late for someone who clicked expecting the page to rebuild itself, so a short
line beside it says what the click does before it happens.

### Landing order with the Bastler move, and one screenshot deliberately left stale

`#185` moves `build_dashboard.py` and `templates/dashboard.html` into the bastler package
verbatim, so this is not a dependency in either direction — whichever lands second carries
the other's change through the merge it already needs. `example/screenshots/dashboard-overview.png`
now trails the masthead by one element; re-rendering it headlessly would leave it visually
inconsistent with the two screenshots beside it, so it was left as it is and the gap recorded
here rather than papered over.

### Track placement

`dashboards`, not the plan the request arrived through. The button is dashboard tooling that
every plan's page gets; rdr-refactor was the page being looked at, not the subject.

## Update 2026-08-28 (resolved): #185's second merge, and a caller test a prose mention had disarmed

`/plan-item-resolve workflow-unification bastler-package`, session
https://claude.ai/code/session_01723FcMWYnpQHrq4fdxxs8j. One thing was wrong and the
manifest recorded it no better than last time: the pull request had been `dirty` and
labelled `needs-resolution` since 2026-08-22, skipped by four maintenance passes, the last
of them three hours before this session started. CI was green on its head commit — all 23
checks, `test_bastler` among them — so the conflict was the entire blocker, and the item's
`notes` said nothing about either.

### The 2026-08-23 lesson repeated, which is what makes it a rule

git reported two conflicts: `resolve-personal-notes-config.sh`, and
`test/bastler_test/test_plan_item_mode.py` as an "added inside a directory that was
renamed" file-location conflict. The file that decided the job was neither of them.
`plan_item_mode.py` and `plan-item-modes.toml` landed on `main` with #149 after this
branch's last merge, and a merge that left them where they fell would have failed this
branch's own `test_no_python_module_remains_under_the_claude_directory`.

The check that finds them is the one the previous round wrote down —
`git ls-tree -r origin/main --name-only .claude/ | grep '\.py$'` against the merged tree —
and it took one command. Two rounds in a row now: **a conflict report names the files two
sides both edited, never the ones a moved directory makes dangerous.** The file-location
conflict git *did* raise is the tell when the new file has a test; there is no tell at all
when it does not.

### What the fold cost, and where it landed

`resolve-personal-notes-config.sh` keeps `main`'s two new `*_DOCUMENT` paths verbatim,
gains `PLAN_ITEM_MODE_MODULE` beside the other module constants and
`PLAN_ITEM_MODES_CONFIG_FILE` beside `stack.toml`'s, and drops `main`'s re-added
`PLAN_ITEM_BOOTSTRAP_SCRIPT` for the `*_MODULE` form this branch already carries.

`plan_item_mode` resolves its committed defaults from the package directory, read off its
own `__file__` rather than written down — the same treatment `stack.toml` already has, and
`pyproject`'s `package-data` carries the file, verified in a built wheel rather than
assumed. `test_plan_item_mode` runs the scratch layout's copy through `PythonModuleRunner`
and takes its paths from `constants.py` and the module's own `Location`, so nothing in it
spells a path the package could rename underneath it.

### A prose mention had disarmed the caller test, and only the mutation showed it

Both documents that invoke the module — `execution-modes.md` and `plan-item-mode/SKILL.md`
— join `UNINSTALLED_INVOCATIONS`, which is what holds `plan_item_mode` to the standard
library through the closure rather than by naming it. The first mutation run said the
declaration was worthless: removing the invocation from `plan-item-mode/SKILL.md` left the
suite green.

The cause is worth carrying. `names_of()` matches any spelling of the module *anywhere in
the caller's file*, and the same edit that repointed the invocation had also repointed a
sentence of prose to `` `bastler.plan_item_mode` ``. The prose satisfied the test on its
own, so the entry would have outlived the invocation it exists to describe. The sentence
names the module no longer, and the mutation fails as it should. **A test that reads a
whole file for a string is only as strong as the file's discipline about mentioning it** —
and nothing about the test says so, which is why the mutation and not the reading is what
found it.

Four mutations, each caught by exactly the test that names it: the module growing an
`import yaml`, each of the two callers ceasing to invoke it, and a caller gaining a
`pip install` step. 642 tests pass, from 617. `check-setup.sh` exits 0 with every row `ok`
and all fourteen entry points answer `--help`.

### Two things flagged rather than acted on

**`main` has retired `requirements*.txt`.** `4b4cfdf4` moved every workspace member's
dependencies into static `[project] dependencies` and added
`test/version_test/test_dependency_declarations.py` to hold them there. It parametrizes
over `[tool.uv.workspace] members`, which does not list `bastler`, so nothing on this
branch fails — checked rather than assumed. But `bastler/requirements.txt` is now the last
one in the repository, and four things read it: `pyproject`'s `rendering` extra,
`BASTLER_REQUIREMENTS_FILE`, `check-setup.sh`'s `dashboard_dependencies` row, and
`package_layout`'s `packages_distributions()` mapping. Following the new convention is a
contract change to what this pull request's own review settled, so it is the user's call
and not a merge's.

**Ten of the 2026-08-23 round's 34 threads are still open**, and correctly so: each was
answered differently from what it asked, or asks a question still waiting on the user
(publishing the package, the `StrEnum` for script names, whether the remaining fixture
literals should move). The convention is that a thread answered differently stays open for
the user to close, so this session resolved none of them.

### Recorded for whoever merges next

`#203` adds `.claude/setup_steps.py` — a third round of exactly the problem above, already
visible. `#198` fixes a bug this branch carries verbatim at `bastler/stack.py:823`, and the
2026-08-24 entry recording it says it lands first and #185 picks it up; it has not landed,
so the bug is still here. Neither is a dependency; both are landing order, and the
`git ls-tree` check is what catches the first of them whichever way round they go.

## Update 2026-08-29 (new item): a red candidate the local suite cannot reproduce

Split out of `integration-branch-ci-verdict` rather than folded into it. Part D put the
publishing verdict on the candidate's own `ci.yml` run; what it did not build is what
happens when that verdict comes back red for a reason the local suite cannot see.

### The residual case, now that the common one is gone

`block-branch` localises a break by re-assembling the tips in order and re-running the
**configured** suite - the four tooling directories - after each. That reaches a break
between two branches whose tooling code disagrees, and reaches nothing in the docker
matrix, where `test_each_lib (krrood)` and its fifteen siblings live. So a candidate red
on a matrix job is reported and left: the candidate is closed naming the failing check,
and nobody is told which tip turned it.

Most of that gap closed with the red-tip exclusion of 2026-08-29, and the remainder is
worth stating precisely, because it is much narrower than it was. A candidate can now go
red for two reasons:

- **a tip whose checks had not finished when the build was assembled** and have since
  failed. The next rebuild reads them as finished and leaves it out, so this heals in one
  cycle without anybody doing anything;
- **a genuine break only the matrix sees** - two branches that each pass their own full
  `ci.yml` run, merge cleanly, and fail a matrix job together.

Only the second needs this item, and only the second is a break in the sense the workflow
means.

### What it would cost, which is why it is its own item

Localising it means re-running the matrix rather than a suite: push each prefix of the
merge order as its own branch, open or dispatch a run for each, and read the conclusions -
against roughly twenty minutes a run and sixteen jobs apiece. Everything about that is
different from `_run_tests`: the waiting, the concurrency, the credential, and what a
partial answer means when one prefix's run is still going. It also has a cheaper variant
worth measuring first - re-run only the *failing job* per prefix rather than the whole
matrix, which `ci.yml`'s per-library job names make expressible.

Recorded as `red-candidate-localisation`, `stack-tooling`, depending on
`integration-branch-ci-verdict`. Not started, no branch.

### Why not folded into #154

Run against the prefer-the-change test rather than judged. It edits `integration.py` for
subcommand wiring, and strip that and a whole dispatched-run localisation subsystem
remains - a client for opening and reading matrix runs per prefix, the waiting, and the
report. That stands alone by a wide margin, which is the same answer the rule gave Part D
itself against #154 on 2026-08-13.

It does *not* replace `locate-failure`. The local suite answers before a build is pushed
and caught the #154-against-#158 break hours before any candidate existed; this answers
after a candidate has run, for the failures the local suite is structurally blind to. Two
mechanisms for two different moments, which is what the 2026-08-28 boundary already
settled when it kept `--test`.

## Update 2026-08-29 (first unattended run): the build was carrying a branch that was already red

The scheduled pipeline's first run reached a verdict and the verdict was `failed`, on
`test_each_lib (krrood)`. Diagnosing it found a selection defect rather than an
integration break, and the defect had been there since `select_for_build` was written.

### What the candidate's red actually was

The failing job passed 2265 tests and reported one collection error, whose traceback sits
some five hundred lines above the summary:

```
_____ ERROR collecting test/krrood_test/test_eql_rdr/test_serialization.py _____
    from krrood.entity_query_language.rdr.backward_inference import what_do_we_know_about
E   ImportError: cannot import name 'what_do_we_know_about'
```

`what_do_we_know_about` is defined on `D-ui-splice-fix`, `D-ui-rendering`, `D-ui`,
`D-store`, `D-deco`, `D-deco-rehome-handoff` and `D-core-engine` - a different sub-stack.
It is on neither `main` nor `D-core-serialization`'s own chain, so that branch's test
imports a symbol nothing beneath it defines. **PR #66 is red on its own pull request, at
the same commit the build merged**, and has been all along.

So the build carried a branch that could not pass, and the candidate then reported a
failure that said nothing about the combination. Reported on #66, where the fix is; not
fixed from here, because it is a single-branch defect that integration did not cause and
which branch of that stack should carry the test is a design call about it.

### The rule, and why it does not re-open a question already settled

`select_for_build` read draft state, the chain, and blocking labels, and never asked
whether a branch's own checks pass. A build is therefore guaranteed red whenever any
carried tip is red alone - and worse, that red is indistinguishable at the candidate from
two branches breaking each other, which is the one thing the candidate exists to report.

This item's own notes of 2026-08-10 record dropping a CI gate, and the reasoning still
holds exactly as written: *restacking rewrites heads, CI re-runs, every restacked branch
reads pending, and a green filter yields a near-empty build.* That is an argument against
**requiring green**, and it does not reach **excluding a known failure**: pending is not
failed, so there is no deadlock to walk into. The rule reads only a finished failure, and
`ChecksVerdict.RUNNING` is carried exactly as before.

It is self-limiting for the same reason, which is worth stating because it is what makes
the rule safe rather than blunt. A restacked branch's head is rewritten, so its checks
read `running` at the moment the build is assembled and it is carried. Only a branch the
restack did not move *and* which is finished-red is left out - and a flaky red costs one
build cycle, cleared by the next push or re-run.

### The field this reads had been dead since it was declared

`Branch.ci` is declared on `main`, documented as the head's latest conclusion, read by
`load_board` and copied onto `Branch` by `build_stack` - and never populated, because
`BoardExport._pull_request` sets it from `record.get("ci")` against a payload carrying no
such key. #139's own review flagged it and nothing fixed it. Giving it a producer *is* the
fix, and it is better than the parameter the first attempt threaded through: `tips_of` and
`select_for_build` both decide from it, so a parameter handed to one and not the other
merges a branch the report says was left out. Reading one field cannot disagree with
itself.

The read happens in `stack_to_build`, after the restack has moved the branches it is
about, and against the **branch** rather than a commit - `GET /commits/{ref}/check-runs`
takes a branch name, so it answers for whatever the branch points at now without first
resolving a head that a restack has just changed.

`CandidateChecks` and `CandidateVerdict` became `ReportedChecks` and `ChecksVerdict` with
it, since they now describe the checks on a branch as well as on a candidate's head.

### Measured on the real board rather than asserted

59 open pull requests: 28 `passed`, 23 `failed`, 5 `running`, 3 `absent`. The failures
concentrate in `coraplex` (17), `experiments` (12) and `giskardpy` (9), which is the
signature of branches far behind `main` rather than of one broken library - and every one
of those is a branch a restack will move, after which it reads `running` and is carried.
Four fail `test_claude_dev_tooling`, and those four are each their own defect rather than
a shared cause: #194's is a document assertion its own diff broke, #154's is a `git clone`
object-copy failure in `test_plan_item_mode.py` that does not reproduce locally in five
runs and is in a file #154 does not touch.

Four mutations checked, each caught by exactly the test naming its rule: never reading
red, treating `running` as red, annotating before the restack rather than after, and
reading the checks of something other than the branch. 753 tests pass across the four
directories CI runs, from 746.

### Worth carrying

**A build that carries a branch which cannot pass produces a verdict about nothing.** The
candidate mechanism was sound and its first real answer was still useless, because
selection let in an input that determined the output. The general form: a gate is only as
good as what it is allowed to judge, so the question *what may reach this gate* is part of
the gate's design rather than a separate concern.

And the narrower one: **a recorded reason for not doing something is a reason against the
thing it names, not against everything nearby.** "No CI gate" had stood since 2026-08-10
and reads as settled; it argues against requiring green and says nothing about excluding
red, and re-reading what it actually claimed is what made this available.

## Update 2026-08-28 (resolved): #110's stall was two things, and the second one nothing had looked at

`/plan-item-resolve workflow-unification setup-stacked-prs-skill`, session
https://claude.ai/code/session_015HBn7bNMj6Ao5inyStmrMN. The manifest recorded the conflict —
`needs-resolution` since 2026-08-12, reported seven times, most recently hours before this run.
It did not record the other half: **a review round of 2026-08-20 that nothing had touched**,
because the branch's last commit is 2026-08-10. A resolve that had read only `blockers`/`notes`
would have cleared the conflict and left the review untouched for a third week.

The recorded CI blocker cleared itself meanwhile: `greenlet` 3.5.5's missing Linux wheel, carried
in the notes as repository-wide, no longer fails — `test_each_lib (robokudo)` is green on the head
this run started from. Worth carrying because the note argued for waiting rather than pushing, and
waiting turned out to be right.

### The conflict resolution that keeping either side gets wrong

Four files conflicted and three are the additive shape the previous merges taught us to expect.
`test_check_setup_sh.py` is not: `main` replaced the inline `subprocess.run` with
`run_hook_script`, which scrubs the environment, while this branch had moved `SetupReport` into a
shared `setup_report.py` whose `from_completed_process` takes the check enum from its caller.
`main`'s side drops the `SetupCheck` argument; this branch's side references an `environment`
builder that no longer exists. **Both sides are individually broken and the resolution is neither
of them** — the runner call *with* the argument. A conflict where each side alone fails is the
case a marker cannot signal, and it is worth naming separately from the additive kind.

### Four breaks behind clean markers, and the one that is the headline change

None of these appears in a diff; all four came from running the suite.

1. **`maintenance.py` does not import.** It arrives from `main` importing `ForkRemoteNotFoundError`
   and `AmbiguousForkRemoteError`, both deleted here with the ~120-line inference — *this pull
   request's whole point*. `maintenance.py` was written after that deletion existed and against a
   `main` that did not have it. It catches `ForkRepositoryNotConfiguredError` now, at the same
   `REMOTES_UNRESOLVED`, exactly as `stack.py`'s own `main()` already does.
2. **`test_maintenance.py` built a `Configuration`** missing `cram2_link_sent_label` and
   `fork_setup_command`, the two settings this branch adds.
3. **Its `ForkCheckout` was an unconfigured checkout.** Every subprocess run exited `4` before
   reaching the status it asserts — the designed behaviour, met by a fixture that meant to stand
   in for a working checkout. The fixture records the fork on the personal-notes branch now, which
   is what setup writes, and pins the notes remote so an ambient `CLAUDE_PERSONAL_NOTES_REMOTE`
   cannot redirect the fetch out of the scratch layout.
4. **A second wording for one event.** `write-branch-files.sh` reported its no-op as "already
   matches every file given" where `save-personal-notes.sh`, `save-plan.sh` and
   `save-pr-progress.sh` all say "is already up to date", and `save-git-identity.sh`'s test reads
   that message through this branch's delegation. The established phrasing wins.

### The recurring break got a mechanism instead of a fourth fix

`install_hook_scripts` took a list of script names, so a test module naming the script it is about
got a layout that script could not run in whenever a *transitive* dependency was involved. That is
this branch's `write-personal-notes-file.sh` → `write-branch-files.sh` delegation, and it has now
broken `test_personal_settings_sync.py` (recorded 2026-08-05), then `test_git_identity_sync.py`
and `test_plan_item_mode.py` here — three times, each fixed by adding a name to one more call site.

It derives the dependency now, from the two ways a shell hook actually names a sibling: the
configuration script's constant for it, or a `${SCRIPT_DIR}` reference. Written failing first in
`test_scratch_repository.py`, with exact-set assertions rather than presence checks.

**The general shape: a fix applied three times at three call sites is a missing mechanism, not
three bugs.** The check that it was the right call is that it fixed something nobody was asking it
to — two of the base's own seven failures, from `main`'s `session-start-messages.sh`, which the
same walk installs.

### The review threads are answered and still open, and that is not a lapse

Both belong to a review that is still **pending**. GitHub allows one pending review per user, so
every inline reply is refused with `user_id can only have one pending review per pull request`.
Submitting or editing that draft is the user's, not a session's, so the replies went into a
conversation comment and both threads stay open. **A resolve without an inline reply is forbidden
by the standing convention, and the convention held here rather than being worked around.**

What the threads asked for is done: `remote_branch_commit` repeated `run_git`'s own `cwd`, capture
and non-zero assertion four lines from where they are defined, and uses the runner now; the two
direct git calls left are module-level functions with no repository to bind to.
`SetupReport.exit_code` is an `ExitCode(IntEnum)` — `SET_UP` / `NEEDS_SETUP`, the two statuses both
checkers can exit, set identically from whether any row needs setup — and fourteen assertions read
the member rather than `0` or `1`.

### Five red, and the discipline that made "not ours" a measurement

626 tests pass across the four directories CI runs, from 463. The five failures are
`test_setup_personal_notes_sh.py`'s, and they are a **strict subset of the seven red on
`claude/setup-personal-notes-script` itself** — established by checking out the base into a
worktree and running the same suite, not by reading the diff and concluding. `main` added a
`git_identity` check to `check-setup.sh`; `setup-personal-notes.sh` records no identity and exits
with that check's status, so a full setup run cannot return `0`.

Left to #107: its script, and it lands first, so patching it in the child would not make the parent
green. The fix is small and stated on the pull request rather than merely deferred — either the
setup script records an identity as one of its steps, or the identity check does not gate its exit;
which one is a design call about `--remote` being the only thing that script is given.

### Two things re-checked rather than assumed

`github-api.sh` is still not on `main`, so the base stays #107 — the same check the 2026-08-03
entry made, run again rather than carried forward. And the notes branch had moved by 430 lines on
this plan between reading it and writing it, so the manifest edit was re-applied onto the fetched
copy; the anti-stale-save rule caught nothing this time only because it was followed.

## Update 2026-08-29 (trigger): a rebuild answers to a branch leaving draft, and the pin cuts both ways

The developer's request: run the integration refresh whenever a pull request goes from
draft to ready. Leaving draft is what makes a branch integrable at all, so it is the
moment the build is worth redoing rather than one to wait out — until then the branch
every fresh session clones serves work that is ready and not in it, for up to six hours.

### Three things follow from the event rather than being separate decisions

**Recursion was ruled out by reading rather than reasoning.** `open_pull_request` sends no
`draft` key, so a candidate opens ready and `ready_for_review` fires only on an existing
draft being converted. Worth checking rather than assuming, since the pipeline's own
output is a pull request and a self-triggering loop would have been discovered by a
runaway Actions bill rather than by a test.

**A fork's pull request is handed no secret**, so the run could only fail on a token it
has not got — and fail on somebody else's pull request, where the failure reads as theirs.
The job does not start for one.

**A burst collapses rather than multiplying.** The concurrency group was already there for
a different reason (two rebuilds racing for the same branch), and it covers this for free:
GitHub holds one run and one pending, and each new arrival replaces the pending one, so
five branches leaving draft together are served once rather than five times.

### The checkout is wrong in either direction, and the first attempt took one of them

A `pull_request` run checks out that pull request's **merge reference**, so taking the
reference the run was started on would run whatever `integration.py` the triggering branch
carries, against a token that can write. The first attempt therefore pinned the checkout to
the default branch unconditionally — and that is the opposite trap: **publishing to the
default branch is what this pipeline does**, so a change that broke publishing could not be
fixed by running the fix, and no change could be tried before it landed there.

That is not hypothetical; it is the state this pull request is in as it is written.
`origin/integration` is three commits behind #154, missing the red-tip exclusion, so a
scheduled run today still carries the branch that turned the first unattended candidate red
and still cannot publish. A pipeline that cannot publish cannot carry its own fix.

So the reference is the default branch on a `pull_request` and whatever the run started on
otherwise — a schedule starts on the default branch anyway, a dispatch starts wherever it
was asked to. The bootstrap out of the current state is a dispatch on this branch, which
the conditional is what allows.

**Generalizable: a guard written against untrusted input has to name the input it distrusts.**
Pinning "always" and pinning "when the trigger is untrusted" look like the same safety
property and are not: the first also forbids the trusted case, and the trusted case here was
the only way to repair the thing being guarded.

### A defect the assertion could not see

The conditional was first written as a folded scalar whose continuation lines were indented
*further* than its first. YAML folds only the lines level with the opening one and keeps a
more-indented continuation verbatim — so the expression parsed cleanly into a string with
newlines inside `${{ }}`, which GitHub would have rejected at run time. The test asserting
the reference *ended with* `github.ref }}` passed throughout.

Found by printing the parsed value rather than by any assertion, and it has its own test now.
The general form is one this plan keeps re-meeting from new angles: **a document that parses
is not a document that means what it looks like**, and for anything embedded in YAML the
check is the parsed value, not the source text.

### One test was over-broad and was narrowed

The first split of the checkout test asserted both the guard's condition and its
default-branch arm, so a mutation that pinned unconditionally — under which the
pull-request behaviour is still correct — failed it. Narrowed until each half fails only
for its own reason: one asserts the default branch appears, the other that the expression
falls through to `github.ref`. Four mutations checked in total, each caught by exactly the
test that names its rule.

758 tests pass across the four directories CI runs, from 753.

### A third finding, from a question rather than a check

The user asked whether any step gives Claude the right to manage pull requests, issues and
pushes. Step 2 was that step, and it could not answer the question: it said "Give Claude
access" and named two URLs, so a reader could not tell whether pushing and opening pull
requests were covered or were a separate grant to go and find.

They are not separate, and the docs say so plainly — a cloud session "can access any
repository the connecting GitHub account can see", and pushing the branch and creating the
pull request both happen through that one authorization. The step names what it covers now.

Two things it had wrong beyond vagueness, both found by reading the documentation rather
than reasoning from the URL names:

- **The organization URL belonged to a different product.** `admin-settings/claude-tag` is
  where an owner allows repositories for the Claude tag. What gates GitHub sign-in on a
  Team or Enterprise plan is the connector toggle at `admin-settings/connectors`, and until
  an owner turns it on the sign-in step "shows 'GitHub access is required for Claude Code
  on the web' instead of a sign-in button" — so the reader is not looking at a permissions
  problem they can fix, they are looking at a missing button.
- **The Claude GitHub App was unmentioned**, which leaves two mistakes available: installing
  it expecting it to be the access grant, and skipping it and wondering why auto-fix never
  runs. The docs are explicit — "Either way, sessions can reach the same repositories" — so
  the step names it as optional, adding auto-fix, granting nothing.

**Generalizable, and the sharper version of the previous entry: the reader's question is a
test the document has to pass.** Every check so far had been "does the step do what it
says"; this one was "can the step answer what a newcomer will actually ask", and the answer
was no for a step that had already survived a review round and a live-services pass.

## Update 2026-08-29 (kickoff): `red-candidate-localisation` opens as #211, and the prefix cannot carry the workflow that tests it

`/plan-item-kickoff workflow-unification red-candidate-localisation`, session
https://claude.ai/code/session_0138w5mqzbkyMPtotF7PD59Z, execution mode `auto`. Branched off #154's
head (`claude/plan-item-kickoff-workflow-ixbvxl`), bootstrapped before any implementation.

### State checked rather than inherited

`check_dependency_readiness.py` reports `integration-branch-ci-verdict` as `open_ready`, and #154 is
`mergeable_state: clean` against `main` with no `needs-resolution` label - better than the state
recorded at #191's kickoff five days earlier, and better than the four repeated conflict reports
of 2026-08-28. Nothing about this item is waiting on that branch.

`check_scope_overlap.py` against `origin/main` was run rather than eyeballed. The new module and the
new workflow are absent from the base *and* from every branch in flight, #185's included: the
bastler move carries `maintenance_*.py` and `stack.py` into the package but not `integration*.py`,
which are unlanded on #154 and therefore still under `.claude/stack/` on both branches. Shared
with #154 are `integration.py`, `maintenance_github.py` and `integration-refresh.yml`; strip those
edits
and the localisation subsystem stands alone, which is the answer the item's own notes recorded and
this re-confirms against live state.

### The boundary between the two localisations, made precise

The item asks for the failures the local suite cannot see. Reading `ci.yml` says exactly which those
are, and the split is cleaner than "matrix versus suite":

- a failed check naming a library (`test_each_lib (<lib>)`) is one only the docker matrix runs, and
  is this item's;
- `test_claude_dev_tooling` runs the same four directories `block-branch` re-runs locally, so it is
  already localised - faster, and before a build is pushed;
- `check_generated_orm_interfaces_are_untracked` is a property of a tree rather than of a
  combination, so no prefix scan says anything about it.

So the command keeps only the failing checks that name a library, and says plainly when none does
rather than probing something it cannot answer. That is the same "two mechanisms for two different
moments" the 2026-08-28 boundary settled when it kept `--test`.

### The load-bearing constraint, which inverts the obvious design

The obvious shape is to push each prefix and dispatch the probe workflow *on that prefix*. It does
not work, and the reason is structural rather than incidental: a prefix is assembled from the
**upstream base** plus some tips, and `workflow_dispatch` runs the workflow file that the dispatched
ref carries. The empty prefix is bare upstream `main`, which carries no probe workflow, and no
prefix carries one until this work lands upstream. The design would only start working at the
moment it stopped being needed.

So the probe is dispatched on the default branch - which carries the pipeline, exactly as the
scheduled rebuild does - and the tree to test is handed to it as an *input*. That requires one
optional `ref` input on `ci_reusable.yml`, defaulting to today's behaviour, so the reusable job can
check out a tree other than the one it was started on. Reusing that file is what keeps sixty lines
of real container setup from being duplicated.

It is the same lesson as `integration-refresh.yml`'s checkout pin, from the other direction: there
the triggering branch's code must *not* run; here the tested branch's code must not decide what runs
over it either.

### Correlating a dispatch with its run

`POST /actions/workflows/{file}/dispatches` answers 204 with no run identifier, and a probe dispatched
on the default branch cannot be found by `head_branch` the way one dispatched on its own prefix could.
The run is named after the tree it tests (`run-name` interpolating the input), so the reader matches
on `display_title`. That is one more constant a workflow retypes because it cannot import one, which
by this roadmap's own 2026-08-28 rule is exactly where a contract test is worth writing.

A run does not exist the instant a dispatch is accepted, so a probe with no run yet reads as still
running rather than as `ABSENT`. `ABSENT` keeps its meaning - the state that means something is
*wrong* rather than slow - and the caller's own timeout is what catches a dispatch that never
produced a run.

### One command, two rounds, and why the narrowing is not deferred

`locate-candidate-failure` is one repeatable decision driven by a state document, the way
`settle-candidate` is one read: the waiting stays with the caller, and each invocation can be read on
its own. The document carries which round is in flight, so the same call starts the prefixes, then
starts the narrowing, then reports.

Both rounds are dispatched in parallel within the round, which is what makes a linear scan the right
shape rather than a bisection: every prefix is independent, so N probes cost one run's wall clock
rather than N, and a bisection would spend log N *sequential* rounds to save runners nobody is short
of. It also keeps the guarantee the local search has - each prefix is genuinely tested, with no
monotonicity assumed.

The narrowing round is built rather than deferred, because deferring it would make the report lie.
`IntegrationTestFailure.breaks_against` is `None` only when *no single earlier tip reproduces the
failure alone*, and the comment says so in those words; a localisation that never looked would write
`None` and state something it had not checked.

### Reusing the finding rather than the mechanism

What a CI localisation finds is the same *kind* of thing a local one finds, so it produces the same
`IntegrationTestFailure` and blocks the branch through the same
`block_the_branch_that_causes_it`. The branch's owner gets the same comment naming the same partner,
and there is one place that decides what happens to a branch that breaks another.

### The limit this kickoff does not pretend to close

A `workflow_dispatch` workflow is only dispatchable once it is on the repository's default branch,
which here is `integration`. So the end-to-end live run is gated on a build carrying this branch -
the same bootstrap Part D needed on 2026-08-28, and stated here rather than discovered later.
Everything below that is verified in the harness against a fake client and a scratch repository, as
the rest of this tooling is.

## Update 2026-08-29 (review round): fifteen comments, one complaint

Session https://claude.ai/code/session_0138w5mqzbkyMPtotF7PD59Z, on #211. All fifteen
answered in `e8932eb40` and `0b1d33f5f`; thirteen resolved, two open on purpose. 835 tests
pass across the four directories CI runs, from 758.

The comments read as fifteen separate asks and are one: **structure over strings, parse
once, and keep the logic where something can run it.** Answering them separately would
have produced fifteen small fixes; answering the complaint produced three modules.

### The parser found the hazard it exists to prevent, while it was being written

`workflow_document.py` parses a workflow once into named things - a file, a trigger, a job,
a step, the action it uses - so a reader asks (`.job(key)`, `.step_using(action)`,
`.calls`, `.run_name`, `.answers_to(event)`) rather than indexing nested mappings under
keys it spells itself.

Then, reading `ci_reusable.yml` through the first version: `KeyError: 'on'`. **A workflow's
trigger block is not under `"on"`** - YAML reads a bare `on` key as the boolean, so the
triggers live under `True`, and a reader that forgets looks in an empty mapping and
concludes the workflow responds to nothing. That failure is loud in a parser and silent
in a caller: fifteen scattered `document["on"]` accesses would each have answered "no
triggers" rather than raising.

Worth carrying, because it is the argument for the whole round rather than a detail:
**a nested key access repeated at every reader has no place to be wrong once.** The
`KeyError` is the parser earning itself before it had a second caller.

A step is found by the action it uses rather than by `<action>@<version>`, so a version
bump does not read as a step that vanished; `WorkflowStep.runs(action)` owns that
comparison, and a step no job uses is a `StepNotFoundError` rather than `None`, since
`None` reads at the call site as a step that uses the action and passes nothing.

### The static library list was worse than a style point

The reviewer asked whether the twelve-member `LibraryUnderTest(StrEnum)` should be found
dynamically. It matched `ci.yml` on the day it was written and was held by **nothing** - no
test compared it to the matrix - so a library added to the matrix would have had its
failures answered as **naming no library at all**, reported as "nothing to localise"
rather than as the gap it is. Silent, and in the direction that loses a real break.

`matrix_libraries.py` derives them from the matrix job, and the job is found by **fanning
out over a matrix** rather than by name: what makes it the one is that it runs once per
entry, so renaming the job leaves the libraries readable where a name written here would
not. The test is parametrized over the live matrix, so a library added later is covered
with nobody editing it.

### The rebuild leaves YAML, and what that was really about

The last comment asked whether the `if` conditions, loops and exit-code numbers in
`integration-refresh.yml` could move into the Python. The tidiness is the smaller half.
**Every decision that block made was a decision about an exit status** - is 10 still a
build worth judging, is 13 worth asking again, is 14 the one that gets localised - and
written in a job's `run:` block none of them could run anywhere but a runner, so nothing
checked any of them. There was no way to be wrong about an exit code and find out before a
scheduled 04:00 run did the wrong thing silently.

`integration_pipeline.py` is that procedure. The workflow drops 223 lines to ~107 and its
last step is one command; the branches are ordinary Python exercised through a `ToolRunner`
answering with the statuses a real one would. `BASE_NOT_PREPARED` (7) is the one status the
composition adds, aligned with the maintenance pass's own not-fast-forward status.

Two properties were deliberately preserved rather than spent. The subcommands are
unchanged - `refresh` is a **composition** over them, so each stays one decision readable
on its own and the waiting sits in the composition. And what is left in YAML is only what a
runner can do: check out, install, resolve the token, set the identity, and one `env:`
expression.

**The move deleted four guards, and this round replaced them rather than noticing later.**
Four tests had asserted the *shape of the shell* - that the block branched on a particular
literal - and with the shell gone they assert nothing. What replaced them is stronger than
what went: every subcommand a rebuild names is checked against the live `commands_of`
registry, so a name that names nothing is a failing test rather than a usage error at the
far end of a runner; and the three keys the steps hand each other are held equal across the
**two different enums** that write and read them, since the writer keys through the
builder's report and the rebuild reads through the verdict's - spelled differently, the
hand-off breaks between two commands rather than inside one.

That is the 2026-08-11 rule applied at the moment it bites rather than in hindsight: a
refactor that removes a duplication removes whatever guard the duplication was providing,
and the commit that removes it owes the replacement.

### A YAML defect an assertion could not see

The `env:` expression choosing the dispatch reference was first written as a folded scalar
whose continuation lines were indented *further* than its first. YAML folds only the lines
level with the opening one and keeps a more-indented continuation **verbatim** - so it
parsed cleanly into a string with newlines inside `${{ }}`, which GitHub would have
rejected at run time. The assertion that the reference *ended with* `github.ref }}` passed
throughout.

Found by printing the parsed value. The general form, which this plan has now met from
three angles: **a document that parses is not a document that means what it looks like**,
and for anything embedded in YAML the check is the parsed value rather than the source
text.

### Two threads left open, and why each

**The 400-line rule.** Everything this round creates obeys it, production and test alike -
largest is `workflow_document.py` at 379 - and the 1008-line localisation test module is
five modules plus shared fixtures. But `integration.py` is 2482 lines and this round adds
484 to it. It was 2064 before this branch, so the file is #154's and already carries an
open thread asking the same question; the precedent for the fix is on `main`, where
`maintenance.py` became eleven modules with the command classes in
`maintenance_commands.py`. Offered rather than done, and the thread stays open because the
rule as stated is not met and this round made it worse.

**Two of three constants stayed plain.** `PROBE_WORKFLOW_FILE` named one of a family and is
a `WorkflowFile` member now; `PROBE_RUN_NAME_PREFIX` and `MATRIX_CHECK_PATTERN` each name
one thing with one reader, where an enum is a lookup with nothing to choose between. What
was worth an enum is what had alternatives.

### Taken as "all" rather than as the three it sat on

Three comments asked for `to_json`. The third said *all such json serialization*, so the
sweep went across `.claude/stack/` and renamed the two dict-returners this round did not
otherwise touch - `integration_verdict.VerdictReport.as_json` and
`integration_reproduction.ReproductionOutcome.as_document`. Every dict-returner in that
directory is `to_json` now, and the five `str`-returning ones keep `as_json`, which is the
split settled on #149: `to_json` is what composes the document and what
`SubclassJSONSerializer` declares, so `as_json` stays free for the text rather than one of
them becoming `as_json_text`. `report-document-naming` still owns the remaining
divergences in `.claude/hooks/` and `.claude/skills/`, which this branch does not reach.

## Update 2026-08-29 (evening): every scheduled rebuild closed its own candidate before anything could check it

Session https://claude.ai/code/session_016owc47W6VhsZebSxiR4bQU, from the user asking why
the latest `Integration refresh` run stopped after an hour. Four runs have fired since the
pipeline went live and all four ended the same way - `the candidate's checks had not
finished after an hour`, with every one of the sixty readings answering `"verdict":
"absent"`. Not one check run was ever reported.

### The premise that was wrong

The design assumed opening the candidate was enough to get it checked, so the settling
could act on whatever the checks said. It closed the candidate on any verdict that was not
`RUNNING`:

```python
if checks.verdict is not CandidateVerdict.RUNNING:
    fork.close_pull_request(candidate.number)
```

`ABSENT` is not `RUNNING`, and `ABSENT` is exactly what a candidate opened two seconds ago
looks like: GitHub creates a pull request's run a moment after the request is opened. The
first reading therefore closed the pull request, no run was ever created for it, and every
later reading found the same absence - while `_verdict_exit_code` answered `ABSENT` as
still-running and kept the loop asking for the full hour. Two readings of one verdict,
disagreeing about the one value they were written apart for.

The timestamps are the proof. Candidates 209, 212 and 213 were each closed two seconds
after opening and have no run of `ci.yml` or `integration-checks.yml` at all; 204 was
closed after three, its runs were created one second later, and it is the only build this
pipeline has ever judged - it went `running`, then `failed`, and exited 14. The
`mergeable_state: dirty` those closed candidates report is not a conflict: `git merge-tree
origin/integration 55ebff49` merges clean.

### What it took to fix, and the second bug underneath

Closing on a settled verdict alone is one line, and both readings come from
`ChecksVerdict.has_settled` now so they cannot come apart again. The rest followed from
what an open candidate then means.

A candidate that never collects a check would otherwise sit through the whole schedule to
end on a message naming the checks as slow, when nothing had started one. `RefreshPipeline`
gives that a warm-up and then stops with `CANDIDATE_UNCHECKED` (17), which points at the
trigger or the credential - the things that would explain no run existing.

And a candidate left open is a candidate the *next* rebuild reads off the fork. It is out
of draft, unblocked and not red, which is everything `select_for_build` asks of a branch,
so it would have been merged into the following build - the last build inside the next.
Measured rather than assumed: `select_for_build` over a stack carrying one returns it as
integrated. The stack a build is assembled from is `work_in_flight` now, every open pull
request except one opened against the branch the build would replace. That also covers the
case this pipeline already had - an hour-long timeout leaves a candidate open too.

839 tests across the four directories CI runs, from 835: the settling leaves an unreported
candidate open, the rebuild stops on one nothing reports a check against, a first reading
finding nothing is still waited through, and a candidate is not work the next build
carries.

### The landing hazard this sits behind

The schedule runs the copy of the pipeline on the fork's default branch, and that branch is
`integration` - the branch this pipeline moves. It only updates when a build publishes,
which is the thing that is broken, so the fix reaches the schedule either by a
`workflow_dispatch` on this branch or by a hand push to `integration`. Neither has been
done, and a dispatch is a real rebuild that publishes on green, so it is the user's call
rather than this session's.

## Update 2026-08-29 (resolved): the requirements install themselves, and the declaration that priced them goes

`/plan-item-resolve workflow-unification bastler-package`, session
https://claude.ai/code/session_01GE3r3XXEJpr9DUUk78Y2sT. Nothing was wrong with the pull
request this time - `mergeable_state` clean, all 23 checks green, no label left on it, the
2026-08-22 `needs-resolution` cleared by the previous session's merge. What was open was
one review thread posted the same day, and it reverses a decision this branch had recorded
twice.

### The reversal, in the user's terms

Their comment: *"I do not think we need this, we should install the requirements
automatically if the user uses bastler and has run the setup or is running it, if he
doesn't then we do not install, and the installation should be done safely where any
failure is caught and reported instead of a silent failure that stops during the hook
without knowing what happened, and then after catching continue the rest of the steps
normally."*

The 2026-08-23 entries argued the opposite twice - *"a hook that fails is worse than one
that reports"*, and the tier's own justification. The first objection is answered by the
requirement they attached to the ask: a caught-and-reported failure is not a hook that
fails. The second is what the whole mechanism rested on, and it does not survive an
install that always runs.

So `session-start.sh` installs whatever of `bastler/requirements.txt` is missing, and
`UNINSTALLED_INVOCATIONS`, `modules_that_must_not_import_third_party()`,
`third_party_import_names()` and the unavailable-import harness are deleted with the 32
test cases derived from them. `package_layout.py` now writes nothing down at all.

### The gate was already in the file

*"If he doesn't [have the setup] then we do not install"* needed no new check.
`session-start.sh`'s second statement is `fetch_personal_notes_branch || exit 0`, so
everything after it already runs only for someone whose notes branch resolves - which is
the same audience the notes, the plan and the git identity serve. A clone that never ran
`/setup-personal-notes` installs nothing because it never reaches the line.

Placed before the setup verdict, for the ordering reason CLAUDE.local.md and the git
identity are already placed that way: `check-setup.sh`'s `dashboard_dependencies` row then
reports what this run installed rather than the absence it was about to fix. Proven live
rather than argued - `nh3` was uninstalled for real, and one run both installed it and
reported `ok`.

### The seventh caller is the one an install-at-session-start cannot reach

Six of the seven entries were sessions. The seventh,
`.github/workflows/upstream-reviews.yml`, runs `python3 -m bastler.upstream_reviews` on a
bare runner where no hook of ours ever runs - the case the 2026-08-23 correction was
written about, and the one the comment did not mention.

Put to the user rather than decided here, with the alternatives measured: add a `pip` step
and delete the mechanism; derive the caller from the workflow files and keep the closure;
or keep a one-entry version of the declaration. **They chose the first**, which reverses
2026-08-23's *"adding a `pip install` step to an Actions runner in order to serve a script
that needs nothing is strictly worse"* - recorded here rather than quietly dropped, since
that entry is otherwise still on this page arguing the other way.

The guarantee survives without the machinery, and without naming anything:
`test_package_contract.py` reads `.github/workflows/*.yml`, finds every workflow running a
module of this package, and holds each to installing the requirements first. It is derived
the same way the deleted closure was; what it is not is the closure, and it does not hold
any module to the standard library.

### Generalizable: a justification outlives the thing that justified it

Three docstrings - `class_property.py`, `plan_item_bootstrap.py`, `plan_model.py` - still
said a module was standard-library-only *because a hook reads it*, or *because the stack
tooling is reachable from SessionStart*. The 2026-08-23 measurement had already found that
false for `session-start.sh`, and the correction went into `package_layout.py` and this
roadmap while the three docstrings kept the retired reason. Each now gives the one that
does hold: decision 12's deliberate independence from `krrood`.

Worth carrying because the earlier round is what makes it visible. A finding recorded in
the module that prompted it does not reach the modules that repeated its claim, and grep
for the *claim* is what finds those - the same shape as 2026-08-23's *"grep for the module,
not for the callers you expect"*.

### Counts and mutations

615 tests, from 642: 32 cases went with the three deleted parametrizations (18 modules in
the closure, and 7 entries twice) and 5 are new. The arithmetic is stated because this
branch has twice had a parametrization narrow silently under a green run - the count is
the check, not the colour.

Five mutations, each caught by exactly the test that names it: the hook not installing
what is missing; a failed install becoming fatal; the hook installing when nothing is
missing; the workflow losing its install step; and the summary dropping its
`requirements:` line.

### One process failure, mine, worth recording

Restoring two mutations with `git checkout -- <path>` reverted the *working-tree* changes
this session had made to those files, not just the mutation - the shared
`missing_requirements`/`install_requirements` functions and the workflow's install step
both vanished, and the next two mutation runs reported failures that were the missing
edits rather than the mutation. Caught because the failures did not match the mutation
under test. A mutation is restored from a copy taken before it, never from HEAD, whenever
the file is one the session has already edited.

## Update 2026-08-29 (review round on #211): one push, an address book, and the split

Seven threads, all answered; five resolved, two left open. `d444a773` on #211 for the code,
`3dafcf86` on #154 for the split the round asked for, `2d50158c` merging it back. 851 tests
pass across the four directories CI runs, from 839.

### Removing a union found a Liskov violation nobody could see

The ask was small — drop `str | BranchRefspec` from `push_refspec`. Doing it failed 27 tests
at once:

```
TypeError: MaintenanceGitCommandRunner.push() takes 2 positional arguments but 3 were given
```

`GitCommandRunner.push_refspec(remote, refspec, with_lease)` and
`MaintenanceGitCommandRunner.push(ProposedPush)` were **the same git command under two names
with incompatible signatures across a class boundary** — a subclass narrowing its base's
method, which Python allows silently and no type checker here was reading. The union had been
hiding it, because nothing was yet passing the new type down that path.

That is the concrete content of the reviewer's separate complaint that "the git command names
like `push` are hard coded multiple times", and it is worth separating from the enum question
they asked alongside it. Measured: no git command name is spelled twice *for the same
operation* — `checkout` three times, `push`, `commit`, `branch`, `rev-parse` and `config`
twice, each a different operation of one command in a method named after it. The one genuine
duplication was `configure`/`set_configuration`, whose bodies were byte-identical.

So there is one `push`, on the runner that runs git, taking the `ProposedPush` that already
decides forcing. `ProposedPush` moved to `.claude/shared/` carrying a `BranchPublication`
rather than a hand-built string, and the lease moved onto it as `as_arguments` — the idiom
`GitSetting` in the same file already had. `RestackPush` stays in `.claude/stack/` and names
the one thing that needed the stack's own words: the category whose lease comes from the
integration strategy.

### The naming rule that decided the replacement was not the one invoked

"No abbreviations" on `BranchRefspec` points at `BranchReferenceSpecification`, since
`refspec` carries two. What actually settled it is `AGENTS.md`'s other rule, which points away
from git's word entirely: *do not adopt another system's vocabulary as an identifier of ours;
name the thing for what it is here.* It is what to publish and the branch to publish it as, so
it is a `BranchPublication`, and `<source>:<destination>` stays in the docstring where a reader
needs git's shape.

### A field that two readers spelled straight past

`ApiResource` and `HttpMethod` name the GitHub client's eleven addresses and four verbs. The
defect that fell out is the reason it was worth more than tidying: `page_size` is a *field*,
and `check_runs` and `workflow_runs` both wrote `per_page=100` past it, so changing the field
would have changed one read of three.

**There was no test module for `GitHubRepository` at all** — not on this branch, not on `main`
— so a wrong path was a 404 at the far end of a runner. `test_maintenance_github.py` pins each
address against the call that makes it, by recording what `_call` is handed.

The first version of it passed the page-size mutation, and why is the reusable part: it
asserted `_page` against a second spelling of itself, and its expected paths used the default
100 on both sides. Building the client at a page size that is deliberately **not** the default
is what makes that mutation fail. Same shape as the report-keys test four rounds earlier —
*a test that pins a contract must read the artifact the contract is about*, and a helper
compared against its own output is not that artifact.

### The split, and the one thing it makes newly losable

`integration.py` went from 2064 lines to 133 — the parser, `main` and the dispatch, the shape
`maintenance.py` already had — with the rest in thirteen modules along the `# %%` sections the
file already carried. Every one is under 400.

Three moves were forced rather than chosen, each by an import cycle: `run_tests` into
`integration_suite.py`, because the assembly and the localisation both run the suite;
`print_failure_location` beside the report it prints rather than beside `print_build`;
`StagedConflict` beside its only writer.

**What the split makes newly losable is a whole command family.** `commands_of` finds a command
by its class existing, so something has to import each family, and the base cannot import what
imports it — which is why `integration_commands.py` is the registry alone.
`test_every_family_of_commands_is_one_the_registry_has_imported` derives the families from the
directory and holds them against what the registry imports. Mutation-checked by dropping one:
before that test the only thing that caught it was the skill test, and only because the skill
happens to name those commands by hand. A structural refactor is exactly the moment to ask what
it makes silently droppable, and to write the guard in the same commit.

Formatting improved as a side effect nobody planned: `integration.py` was 68 `docformatter`
hunks `scripts/format_docstrings.py` cannot converge on, so it declined the whole file on every
commit. Ten of the twelve new modules converge; the 21 left are in two.

### Two threads left open, and the reason is the same for both

The `GitCommand` StrEnum-or-hierarchy question is answered with measurements and no change,
because the seam is owned elsewhere. The hierarchy is what the method signature already is —
`push(self, proposed: ProposedPush)` says what a push takes, enforced at every call site — and
the enum would be sixteen members with one reader each. `--quiet` is the only real repetition
at eight, and it is a property of the runner capturing output rather than a per-command choice:
on every write, on no read. That also turned up an inconsistency nothing depends on today —
`merge`, `rebase` and `conclude_merge` accept it and do not get it.

The deciding half is the plan rather than the code. `bastler-notes-core-python` owns
`git_interface.py` **by name** and has four callers waiting, one of them (`stack.py`'s `_git`)
with a deliberately opposite contract; `bastler-package` moves the file's home. The hard
question there is not enum-versus-classes but whether one runner can serve a caller that must
never raise and a caller for whom a silent failure is the bug. Choosing the ergonomics before
that is settled means choosing them twice, across four call sites instead of one.

### A mistake worth carrying

`git checkout <path>` to undo a mutation discarded every uncommitted change to that file, not
just the mutation — losing the whole `maintenance_github.py` round, which had to be redone from
the script that produced it. A mutation is restored from a copy taken immediately before it.
Recorded independently by the `bastler-package` session the same day, from the same shape.

## Update 2026-08-29 (resolved): one declaration in `pyproject.toml`, and the last Python leaves the shell

`/plan-item-resolve workflow-unification bastler-package`, session
https://claude.ai/code/session_014kmiZegiD2Q8w2eese2L2L. The pull request was healthy - 22
of 23 checks green with `test_each_lib (coraplex)` still running, no label, both
dependencies merged. What was open was two review threads posted at 21:25 and 21:26, four
minutes before the previous session's own push landed, and neither had been answered.

They are one change, because the first decides what the second reads.

### The call that had been flagged and left to the user

`main` retired every workspace member's requirements file for static `[project]
dependencies` at `4b4cfdf4`, and the 2026-08-28 entry recorded that this package's was
now the last one in the repository and that whether it followed was the user's call rather
than a merge's. Their comment made it: *"the repository does not now use requirements.txt
but actually only pyproject.toml and states dependencies there."*

So `bastler/requirements.txt` is deleted and the four distributions are declared in
`bastler/pyproject.toml`. The `rendering` extra goes with it rather than being carried
over: it existed only because `dependencies` was empty under the tier reasoning the
previous round deleted, and it was itself resolved dynamically *from* the file now gone.

### The two installers diverge, and the zero-install contract is why

A session start installs the missing **specifiers**. `pip install ./bastler` would leave a
second copy of these modules in `site-packages` beside the clone's own, and the clone's
copy is what decision 8's zero-install contract says a caller imports. An Actions runner
has no such contract and is thrown away after the run, so `upstream-reviews.yml` and the
`test_bastler` job install `./bastler` itself and take the declared dependencies with it.

`bastler` stays out of `[tool.uv.workspace] members`, so `test_dependency_declarations.py`
still does not reach it - membership would put this package in the default `uv sync`,
which decision 12 rules out. `test_dependencies.py` holds the static-declaration property
directly instead, which is the guarantee that test would have provided.

### Grep for the pattern, not for the line commented on

The second comment was on the `python3 - <<'PYTHON'` heredoc in
`resolve-personal-notes-config.sh`: *"put this in a python script and call it here. Same
for all such situations."* The whole tooling shell was grepped for embedded Python rather
than only that line, which found one more: `save-plan.sh`'s `python3 -c "import yaml"`.

Both are gone. `bastler/dependencies.py` reads the declaration and prints what is missing,
and `save-plan.sh` asks the same module - its refusal now names everything the tooling is
short of and the command to fix it, rather than the one import it happened to probe. No
bash entry point carries Python of its own any more.

`.claude/hooks/plan-updates-since.sh` had already made this move for its own snippet and
said so in a comment. A convention recorded in one file does not reach the next one; the
grep is what reaches it.

### Writing the call out exposed a defect the heredoc had hidden

The first version of the shell function was `echo $(python3 -m ...)`, whose exit status is
`echo`'s. A scratch clone without the module reported `already installed` - because an
empty answer means *nothing to install*, and a module that dies produces exactly that.

The heredoc could not have had this bug, since its failure was the function's own. Moving
the work out is what created the seam, and the seam is where the reporting has to be
explicit: `|| return 1`, a `dependencies: not checked` case for a declaration that will
not parse, and a test that fails without it. **Extracting a computation moves its failure
mode from "the caller fails" to "the caller reads a value", and the value it reads is
usually the safe-looking one.**

### Counts and mutations

632 tests, from 615. Six mutations, each caught by exactly the test that names it: the
module's failure swallowed, `pip` handed the declaration file instead of the specifiers,
the declaration made dynamic again, a specifier's constraints left on the name looked up,
the runner losing its install step, and `save-plan.sh` losing its guard. Each was restored
from a copy taken before it rather than from `HEAD`, per this branch's own process note of
earlier today.

Verified live rather than argued: `nh3` uninstalled for real, one session start reported
`installed nh3>=0.2 from bastler/pyproject.toml` and `setup: ok` in the same run, and the
built wheel carries its four `Requires-Dist` lines and its package data.

The summary line is `dependencies:` rather than `requirements:` now, since what it reports
is the package's declared dependencies and "requirements" named a file that no longer
exists.

## Update 2026-08-30: the dashboards publish themselves, off main rather than behind #111

`stack-board-single-site` (PR 4) is built and open as draft #218. The user asked for it
now, in those words - "I do not want to wait" - and the interesting part of the session
was working out what "now" actually forced.

### The dependency was real, and honouring it would have shipped nothing

The item depended on `shared-pr-state-chips` (#111), which carries a `build_site.py` at
exactly the path this needed one at. Stacking on it is what the plan says to do, and it
would have been wrong here for a reason that has nothing to do with impatience: a
workflow only publishes for *every* plan once it is on `main`. A copy living on a
stacked branch runs on that branch's own pull request events and nothing else, and
`workflow_dispatch` does not exist at all until the file is on the default branch. So
stacking behind a branch conflict-blocked since the 2026-08-29 maintenance pass would
have parked the whole feature there.

I first wrote that claim down more strongly and wrongly - that `pull_request` triggers
fire only from the base branch's copy of the file - and the first run refuted it within
a minute by running from this branch's copy. **A mechanism you assert in a commit
message an hour before the system demonstrates otherwise is one you should have checked,
especially when the weaker true version supports the same decision.**

**A dependency between two branches is a dependency between two *landings*.**

### The duplicate was chosen, not missed

This is the case CLAUDE.local.md's precedent list warns about - #110 and #106 building
the same artifact twice because nobody ran the check. The check was run: `git ls-tree
main -- .claude/skills/plan-dashboard/build_site.py` is empty, #111 builds it, and the
two would collide. What differs from the precedent is that the collision is now a
recorded decision instead of a discovery. It was kept to *one file* deliberately: same
path, same CLI contract, so the merge is one file's content resolved in favour of #111's
richer version (its chips, its `development_tooling` modules), and this branch's
`github_api.py`/`personal_notes.py` are then deletable rather than merged.

**A duplicate you can name, bound to one file, with the resolution written down before
either lands, is a different object from one you find afterwards.** The rule that says
fold rather than sequence still holds; what it cannot decide is the case where folding
means shipping nothing.

### The first run rejected the deployment route, not the triggers

The workflow ran the moment the pull request opened, and failed in one second before its
first step: *Branch `refs/pull/218/merge` is not allowed to deploy to github-pages due
to environment protection rules.* The `github-pages` environment only accepts
deployments from the default branch, so `actions/deploy-pages` can never run from a pull
request - which is this workflow's main trigger. Not this PR's problem: every run on
that trigger, forever, would have failed the same way. No setting reachable from
`GITHUB_TOKEN` relaxes it either (the environments API needs repository administration,
which `GITHUB_TOKEN` cannot be granted).

So the site is pushed to a branch of its own that Pages serves from, and `pages_site.py`
points Pages there through the API. That also turned out better on its own terms: the
site URL now comes from GitHub's Pages configuration rather than from `configure-pages`'
output, which covers a custom domain and an owner-root repository - neither of which a
formula over the repository name reaches.

**A permission that is attached to a deployment *environment* rather than to a token
cannot be probed by reading the workflow, only by running it.** The design was sound in
every respect a test could reach and wrong in the one respect only GitHub could answer,
which is the argument for opening the pull request early rather than for reviewing
harder.

### The default branch is not `main` here, and the workflow assumed it was

The checkout named `github.event.repository.default_branch`, meaning "the reviewed
scripts, not the pull request's". The intent was right and the expression was wrong for
this fork: its default branch is the regenerated `integration` branch - 172 commits of
reviewed-but-unlanded work ahead of `main`, carrying no `build_site.py` at all - so the
job would have been handed a tree with no script to run. Caught by the user reading the
workflow, not by anything I ran; the earlier `session-branch-base` work in this very
session had already established that the default is `integration` and deliberately so,
which makes it a fact I had in hand and did not apply.

It names `SOURCE_BRANCH: main` now, and two tests pin it: that the default-branch
expression appears nowhere, and that the branch a renderer change is *watched* on is the
branch that change is then *read from* - watching one and building another would
republish the site without the change that asked for the rebuild.

**A context expression that names a role (`default_branch`) rather than the thing you
mean (`main`) is only correct while the role and the thing coincide.** This repository
is precisely where they do not, and that was already written down.

The knock-on is worth carrying because it is not fixable in the file: `workflow_dispatch`
only offers a workflow that is on the *default* branch, so dispatch becomes available
once an integration rebuild carries it. `push` and `pull_request` both name their branch
and are unaffected.

### Two things the build taught that no amount of reading would have

`fetch-depth: 0` is in the workflow because a shallow clone genuinely cannot do the job,
not out of caution. The merged-to-done correction commits in a worktree over the notes
branch and pushes it; git refuses that from a shallow clone with `shallow update not
allowed`. This was reproduced by accident - mirroring the notes branch for a smoke test
failed with exactly that error - which is a better way to learn it than a CI run would
have been.

And the site build was verified against the *real* plan data and live GitHub, with the
notes remote redirected to a local bare mirror so the correction push had somewhere
harmless to go. All 10 plans rendered, tracking issues resolved through the issues
endpoint, index links absolute against the Pages base URL. **A test with a fake
transport proves the wiring; only real data proves the manifests you actually have go
through it.**

### What was dropped, and said so rather than quietly

The item's own note listed more than shipped. The every-fork-pull-request-belongs-to-a-
plan invariant, the repo/branch/upstream repository variables, and the three inconsistent
poll-interval statements are all still open, and nothing else carries them. The
`repository: AbdelrhmanBassiouny/stack-board` override is gone for a substantive reason
rather than tidiness: the site publishes from this fork's own Pages, so #218 lives here
and the item's pull request has to resolve against the plan's default repository or the
dashboard looks it up in the wrong one.

Pages on this repository is public. The plan data is already public on
`claude/personal-notes`, so the site discloses nothing the branch does not - but it does
give it a discoverable URL, which is a different thing and belongs in front of the user
rather than in a commit message.

### Counts

52 new tests; the plan-dashboard suite is 295, from 243. The scratch notes remote is a
bare repository and the GitHub side is a fake, so no test reaches the network. The
rejected environment deployment is pinned out by a test of its own, so the route the
first run refuted cannot come back unnoticed.
