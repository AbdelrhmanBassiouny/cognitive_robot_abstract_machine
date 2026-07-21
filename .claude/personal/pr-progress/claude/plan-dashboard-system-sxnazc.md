# Plan-dashboard system — status: PR #91 open (draft, base main), subscribed to all activity.

## PR #91
- https://github.com/AbdelrhmanBassiouny/cognitive_robot_abstract_machine/pull/91 — draft, base `main`.
- Contains only the main-bound infra (hooks + skill), per the user's request to keep it separate
  from the personal-notes data (schema/rdr-refactor migration, which stays on `claude/personal-notes`
  and is never part of any PR).
- Commits: f224198d (hooks + skill), b59c9b54 (dependency-stacking + next-steps sidebar
  generalization), 66dd5792 (plan-create skill - see below). PR description updated to match all
  three.
- CI: one failure seen (`test_each_lib (semantic_digital_twin)` - a ROS WorldSynchronizer test with
  a fixed `time.sleep(1)` race, unrelated to this PR's diff (hooks/skills only, no Python touched);
  attempted a rerun but the matrix run was still in_progress so GitHub rejected it (`workflow is
  already running`) - the standing ~1h check-in will re-verify once the run finishes. No review
  comments yet.

## plan-create skill (added after a second follow-up request: "I want a skill or an agent that
## automates plan creation")
- New `.claude/skills/plan-create/SKILL.md` (`/plan-create <plan-id>`): gathers a new plan's scope
  (existing freeform doc to migrate / named branches+PRs to cross-check live / conversation), drafts
  plan.yaml+roadmap.md, validates against the same checks plan-dashboard runs, asks via
  AskUserQuestion before assuming any real structural judgment call, then runs save-plan.sh and
  plan-dashboard itself. Does not invent a new write path - reuses the existing marker+save-plan.sh
  bootstrap flow (still documented as the manual fallback).
- Fixed a real gap found while wiring this in: plan-dashboard's SKILL.md already instructed loading
  the `artifact-design` skill but its `allowed-tools` frontmatter never listed `Skill` - added it.
- Updated save-plan.sh's header comment, hooks/README.md, and plans/README.md (personal-notes) to
  point at the new skill as the recommended path, keeping the hand-written flow documented too.

## Follow-up request #1 (dependency stacking + sidebar)
- Stacked/indented item rendering: items within a track now indent by same-track `depends_on` depth,
  capped at level 4; a chain deeper than that wraps back to level 0 with a left-edge arrow chip back
  to the real parent ("◄ continues from ..."). Generalized in SKILL.md (not plan-specific), applied to
  the real rdr-refactor dashboard (verified: S0-steward's 14-item chain wraps twice, exactly as
  expected: levels 0-4, wrap, 0-4, wrap, 0-1).
- Summary sidebar added: sticky aside with status counts + a computed "what to do next" list (drift
  fixes first, then items whose dependencies are all done ("ready to start"), then blocked items with
  a partially-done dependency set ("blocker may be cleared")). Also generalized in SKILL.md.
- Republished the same dashboard Artifact URL in place (55da1cc9-...) reflecting both changes.

## Delivered
- Schema: `.claude/personal/plans/<plan-id>/{plan.yaml,roadmap.md}` on `claude/personal-notes`
  (flat items tagged with track/wave, thin manual `status` enum, live GitHub state never stored).
  Full reference: `.claude/personal/plans/README.md` (personal-notes branch).
- Migrated `rdr-roadmap.md` -> `plans/rdr-refactor/{plan.yaml,roadmap.md}` (37 items, all waves/
  tracks), cross-verified against live GitHub PR state (found and fixed one real inaccuracy:
  PR #83 isn't uniquely non-draft, #58/#39/#53/#41/#63-67 are too). Old `rdr-roadmap.md` replaced
  with a pointer stub. Zero drift found between manifest and live state (expected, built fresh
  from verified data).
- `.claude/skills/plan-dashboard/SKILL.md` (main-bound, generic): reads any plan, cross-checks
  GitHub, publishes a dashboard Artifact; `/plan-dashboard` with no arg publishes the master index.
  Actually invoked both: dashboard https://claude.ai/code/artifact/55da1cc9-2607-4c2b-ab79-0d328699432b,
  index https://claude.ai/code/artifact/33ffb3e0-3e54-4c2c-a672-06dbafda757a. URLs cached in
  `plans/_generated/dashboard-urls.yaml` so future refreshes update in place.
- `.claude/hooks/save-plan.sh` (new): pushes plan.yaml/roadmap.md + regenerates
  `plans/_generated/branch-index.yaml` (branch->plan-id) in one commit. `resolve-personal-notes-config.sh`
  gained `plan_id_for_branch` (grep/sed against the generated index, deliberately not a YAML parser -
  session-start.sh must not gain a python3/PyYAML dependency on every session start).
- `session-start.sh` extended: auto-loads a plan's manifest+roadmap into CLAUDE.local.md when the
  checked-out branch is one of its tracked items (new BEGIN/END-PLAN-MANIFEST and
  BEGIN/END-PLAN-ROADMAP marker pairs).
- Verified end-to-end in a disposable worktree on the real `D-ui` branch: auto-discovery resolved
  `rdr-refactor` correctly, extracted manifest byte-identical to source, and a save-plan.sh round-trip
  (test edit -> push -> verify -> revert) worked cleanly including reverse-index regeneration.

## Decisions locked in (via AskUserQuestion, before implementing)
- Master index: show all plans, completed ones visually collapsed (not hidden).
- No periodic staleness-backstop Routine for now (can add later once proven out).
- `status` stays thin (not_started/in_progress/blocked/deferred/done); all PR/CI/review state is
  always live-fetched from GitHub, never stored in the manifest.
- Flat items list (tagged with track/wave ids) instead of nesting under wave->track, since a track
  (e.g. why-track) can span/reprioritize across waves and depends_on needs direct item references.
- Dropped the `roadmap:` field from the schema (YAGNI) - `roadmap.md` is a fixed filename.

## Next (if asked to continue)
- No PR opened - ask before opening one (repo convention: draft, bug label if applicable, session
  link, subscribe to activity - N/A here, this isn't a bug fix).
- Optional follow-ups not requested: a periodic Routine backstop (deferred per user's answer above);
  migrating the separate EQL-verbalization P1-P4 roadmap (in CLAUDE.local.md's cram-notes section)
  onto this same schema as a second plan, if ever wanted.
