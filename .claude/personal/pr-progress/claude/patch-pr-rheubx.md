## PR #101 — Add /setup-personal-notes, a guided one-time setup command

Branch `claude/patch-pr-rheubx`, based directly on `origin/main` (bcd322c2), draft,
subscribed to all activity.

### Origin
Not a plan item and not a session-authored design: the user handed over a ready
`git format-patch` file (`0001-Add-setup-personal-notes...patch`) and asked for it to
go up as a new PR. Scope is therefore exactly the patch — no additions, no cleanup.

### Plan
1. [x] Verify the branch's base — it was already exactly at `origin/main`, so no
   rebase/restack was needed.
2. [x] `git apply --check` (clean), then `git am` to preserve the patch's own author
   (Abdelrhman Bassiouny) and commit message.
3. [x] Fix the committer identity: `git am` recorded `Claude <noreply@anthropic.com>`
   as *committer* (author was already correct). Repo git config was set to that
   assistant identity — reset it to the human's name/email and `--amend --no-edit`.
   AGENTS.md forbids an assistant identity as either author or committer.
4. [x] Verify the new tooling actually works rather than trusting the diff:
   `check-setup.sh` on this clone (correctly flagged the 2 uninstalled dashboard
   requirements, exit 1; exit 0 after installing them), and confirm no stale
   `plans/README.md` references survive the schema-doc move.
5. [x] Run the tests: 12/12 in the new `test_check_setup_sh.py`, 215/215 across
   `.claude/hooks/tests/` + `.claude/skills/plan-dashboard/tests/`.
6. [x] Confirm CI covers the new suite — `ci.yml`'s `test_claude_dev_tooling` job
   already runs `${HOOKS_TESTS_DIRECTORY}`, so no workflow change is needed. Tests
   use a local `git init --bare` fixture, so they need no network or credentials.
7. [x] Push, open as draft (personal convention), subscribe to PR activity.
8. [x] Second ask from the user, same session: `.claude/hooks/README.md` is too verbose —
   rewrite it as a short, point-based, step-based guide. Done on this same branch
   (378 → 139 lines), because the harness pins this session to
   `claude/patch-pr-rheubx` and PR #101 already edits that exact file, so a separate
   branch would conflict with it. Offered to split it out if the user prefers.
   Also repointed `PullRequestLabel`'s docstring at the renamed section so the
   cross-reference doesn't go stale. PR description rewritten to cover both parts.
9. [x] Third ask: surface the worked example at the top of the README, for people who'd
   rather jump straight into using it. Added as a callout under the opening paragraph
   (walkthrough link + "or just run /setup-personal-notes"); the plan-dashboard
   section's own entry dropped to a bare link so the description isn't stated twice.
   Also fixed the walkthrough's footer, which still called the README the setup guide
   "this walkthrough assumes you've already followed" — its own intro (rewritten by the
   original patch) no longer assumes that, and with the README now pointing readers
   into the walkthrough, the stale line pointed them straight back out.
10. [~] Watch CI to green; handle review comments.
    - CI failure on 53abfdc (`test_each_lib (semantic_digital_twin)`) investigated and
      confirmed **not** caused by this PR: single failure was
      `test_multi_sim.py::test_world_sim_state_sync` (1 failed, 871 passed), and the
      identical failure is on `main` itself at 05fee32 (2026-07-28, predates this
      branch) with near-identical numbers — box ends at ~origin, expected
      `[0.3, 0.2, 0.15]`, both runs. Not a marginal-tolerance flake: the target pose
      appears not to be applied at all, intermittently. Worth its own investigation,
      out of scope here. Posted the evidence once on the PR thread; did not fix.
    - `test_claude_dev_tooling` (the job covering these changes) green on every push.
    - Second failure, head 8ad4d612: `test_each_lib (giskardpy)` on
      `test_integration_pr2.py::TestSelfCollisionAvoidance::test_attached_self_collision_avoid_stick`
      (1 failed, 319 passed). Also confirmed **not** this PR's, with stronger evidence
      than the sdt one: that same giskardpy job **passed** on the previous head
      53abfdc, and the whole diff between the two heads is the README rewrite, one
      docstring line and one walkthrough footer line — nothing a PR2 self-collision
      motion-planning test imports or executes. So the job flipped pass→fail across a
      diff that cannot reach it.
    - Note for later: the two runs each flaked on a *different* physics/motion job while
      the other passed. Both tests sit near recent collision-handling work on `main`
      (lazy-init refactor, new self-collision tests). Flagged on the thread as a lead
      only; not investigated, out of scope for this PR.
    - **User instruction (2026-07-29): ignore these errors.** Stop investigating,
      re-running or commenting on the robotics-job failures. The check-in prompt was
      retuned to watch only for review comments, merge conflicts and merge/close;
      `test_claude_dev_tooling` is the only job to act on. A `rerun_failed_jobs`
      attempt was already refused with 403 (run still in progress) and is not being
      retried.
    - Everything else on the current run is green, `test_claude_dev_tooling` included.
11. [x] Review round 1 (12 comments, 2026-07-29), pushed as 8a2f1cf2:
    - Test structure: `_run_git` was verbatim-duplicated in `test_save_plan_sh.py`, and
      the two `scratch_repo` fixtures repeated the same git init/bare-remote/notes-branch
      sequence. Both moved onto a `ScratchRepository` dataclass
      (`tests/scratch_repository.py`) with the initialized repository as a `conftest.py`
      fixture; `cwd` is gone (it's the object's `project_root`), everything documented.
    - Typing: `SetupReport` is a dataclass, the `(status, detail)` tuple is a
      `CheckResult` dataclass read via fields, and `SetupCheck`/`CheckStatus` are
      StrEnums (checked first — no existing enum to reuse; the only `.claude/` StrEnums
      are `build_dashboard.py`'s four, none about setup checks).
    - Labels: added skill step 8 — checks `merged`/`bug`/`in-review` exist in the fork
      and offers to create them. No create-label tool exists in the GitHub MCP server
      (only `get_label`), so creation shells out to `gh label create` and says so plainly
      when `gh` is absent. Runs even on the fast path, since `check-setup.sh` can't see
      labels; fast-path wording updated to match.
    - README wording: `e.g.`, "see it in action", direct branch condition.
    - Also fixed a stale `.claude/skills/cram-setup` pointer (no such skill).
    - 11 of 12 threads reply-and-resolved. **Left open deliberately:** the "does this
      need a skill at all?" question — replied with the accounting (every mechanical step
      is already a script call; only the remote-ownership check and the label check need
      a session) and proposed a `setup-personal-notes.sh --remote <x>` that would make
      steps 4–7+9 runnable with no session, shrinking the skill to the two session-only
      parts. Asked whether to do it in this PR or a follow-up. **Awaiting answer.**
12. [x] Answer received (2026-07-29): the `setup-personal-notes.sh` extraction is a
    **follow-up**, not part of this PR. Thread reply-and-resolved; all 12 threads now
    resolved. A copyable kickoff prompt for a fresh session was handed to the user in
    the session chat (not written to any tracked file — it describes work that doesn't
    exist yet). The follow-up depends on #101 merging first.
13. [ ] Handle further review comments; watch for merge/close.

### What this PR contains
`/setup-personal-notes` skill + `prerequisite-check.md` + `starter-notes.md`;
`check-setup.sh` (read-only TSV setup inspection, the single source of truth for
"is this clone set up?"); step 0 prerequisite checks wired into `plan-create`,
`plan-dashboard`, `plan-item-kickoff`, `plan-item-resolve`; and the `plan.yaml`
schema reference moved from the personal-notes branch to `main` as
`plan-dashboard/plan-schema.md`, with every reference repointed.

### Next steps
- Watch CI. The known pre-existing unrelated flake on this repo is
  `test_world_sim_state_sync` (semantic_digital_twin physics settling) — if it
  fails, confirm it against `main` before treating it as this PR's problem. This
  PR touches only `.claude/`, so any failure outside `test_claude_dev_tooling` is
  almost certainly not caused by it.
- Handle review comments: reply, then resolve only once genuinely done.
- Re-arm the ~hourly self check-in until the PR is merged or closed.
