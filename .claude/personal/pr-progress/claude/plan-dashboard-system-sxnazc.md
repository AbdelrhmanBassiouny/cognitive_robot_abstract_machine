# Plan-dashboard system — status: PR #91 open (draft, base main), subscribed to all activity.

## PR #91
- https://github.com/AbdelrhmanBassiouny/cognitive_robot_abstract_machine/pull/91 — draft, base `main`.
- Contains only the main-bound infra (hooks + skill), per the user's request to keep it separate
  from the personal-notes data (schema/rdr-refactor migration, which stays on `claude/personal-notes`
  and is never part of any PR).
- Commits: f224198d (hooks + skill), b59c9b54 (dependency-stacking + next-steps sidebar
  generalization), 66dd5792 (plan-create skill), d11aab31 (roadmap.md rendering fix),
  1f5590fd (tracking-PR mailbox), 6845687f (tracking_issue migration - see below). PR description
  updated to match all six.
- CI: last known GREEN as of 66dd5792 (18/18); the `test_each_lib (semantic_digital_twin)` flake
  confirmed as a flake there, not a regression. Not yet re-checked on the four commits since - next
  check-in will confirm. No review or conversation comments as of the last check-in. Still draft,
  awaiting review.

## Follow-up request #5 (user enabled Issues -> migrate off the tracking-PR fallback)
- User enabled GitHub Issues on the repo (in direct response to the tracking-PR workaround's
  documented trade-off) and said so. Per my own documented contingency ("if Issues are ever enabled
  here, a tracking Issue would be the more natural fit and this step should switch to that instead"),
  migrated for real rather than just updating docs:
  - Created real issue #94 for rdr-refactor (title `[plan-tracking] rdr-refactor`), confirmed
    subscribe_pr_activity works on a plain issue number exactly like a PR (no separate
    issue-subscription tool exists - this is the SAME generic subscription mechanism).
  - Closed PR #93 with an explanatory comment pointing at #94, unsubscribed from it. Tried deleting
    its now-unneeded branch `plan-tracking-rdr-refactor` - blocked by the same git-proxy ref-delete
    limitation noted elsewhere (D-ui.md) - harmless, human can delete via GitHub UI if wanted.
  - Schema: `tracking_pr` -> `tracking_issue` (plans/README.md + rdr-refactor's plan.yaml, pushed to
    personal-notes as a4090401). Field describes the mailbox's ROLE, not the literal GitHub object
    type - kept the PR-based empty-commit fallback documented for any repo that has Issues disabled,
    under the same field name, since which mechanism applies is a per-repo fact that can change (as
    it just did here).
  - plan-create: step 5 now creates a real issue by default, falls back to the tracking-PR trick
    only on a 410. Also fixed a real gap noticed while touching its tool list: it never had
    mcp__github__create_pull_request even under the original PR-only design.
  - session-start.sh: renamed the grep/sed extraction (still dependency-free, no python3 added),
    verified end-to-end on the real D-ui branch again - correctly surfaces "#94" now.
  - Dashboard: link now uses issue_read's own `html_url` rather than guessing /issues/ vs /pull/ -
    more robust than assuming based on which field is set. Republished (55da1cc9-... in place).
  - Pushed as 6845687f; PR #91 description updated to cover all 6 commits now on it.

## Follow-up request #4 (tracking-PR mailbox for structural changes)
- Answered the "should this go through a comment on the plan PR" design question from before:
  confirmed empirically that GitHub Issues are DISABLED on this repo (410 on create attempt) - so
  the tracking-issue design I'd proposed is dead, and a tracking PR (the user's original instinct)
  is actually the only viable mechanism. Pivoted cleanly, explained why to the user.
- Built for real against rdr-refactor: branch `plan-tracking-rdr-refactor` (empty commit off main,
  no file changes ever) -> draft PR #93 "[plan-tracking] rdr-refactor". Subscribed via
  subscribe_pr_activity - confirmed it works identically to a normal PR (user's follow-up question,
  verified not assumed). NOT running the normal CI-babysit loop on #93 (nothing to test, no code) -
  just staying subscribed to catch new comments.
- Schema: new optional `tracking_pr: <int>` field (plans/README.md + rdr-refactor's plan.yaml, both
  pushed). New "Proposing structural changes" section in plans/README.md documents the convention.
- plan-create SKILL.md: new step 5 (renumbered 6-9 after it) creates the tracking PR when
  bootstrapping a plan (asks first, default yes unless clearly single-session-owned), subscribes,
  records tracking_pr.
- session-start.sh: extracts tracking_pr via grep/sed (same dependency-free approach as
  plan_id_for_branch, no new python3 dependency on every session start) and adds a standing-
  instruction paragraph to the plan-manifest header telling a session which side of the convention
  it's on. Verified on D-ui test worktree: correctly extracted "#93" and surfaced the note.
- plan-dashboard SKILL.md + the real dashboard: added a "Propose a structural change ->" link in
  the header when tracking_pr is set. Republished (55da1cc9-... in place).
- Pushed as 1f5590fd; PR #91 description updated to cover all 5 commits now on it.

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

## Follow-up request #3 (roadmap.md rendering + open design question)
- User asked "does the dashboard reread the roadmap? so if the roadmap was updated or the plan.yaml,
  it will be updated?" - answer: plan.yaml yes (fresh git show every run), roadmap.md was fetched
  but NEVER actually rendered anywhere in the real build script - a genuine gap between SKILL.md's
  vague "render inline or summarize" instruction and what got built. User said fix it.
- Fixed: build_dashboard.py now has a real (dependency-free, no `pip install markdown`) block-level
  markdown->HTML converter - headings, paragraphs, ul/ol with proper wrapped-continuation-line
  joining (first attempt broke on this - bullets/numbered lists were splitting across lines
  incorrectly, fixed with a proper block-accumulation rewrite), fenced code, GFM tables (the one
  real table in rdr-refactor's roadmap.md was rendering as a wall of raw pipe characters before this).
  Rendered into a collapsed-by-default `<details>` "Background & history" section right under the
  masthead. Verified tag-balanced (details/div/ul/ol/table/tr/code all matched). Republished
  (55da1cc9-... in place). Tightened plan-dashboard's SKILL.md from "render inline or summarize" to
  a concrete, non-optional instruction (summarizing defeats the point of the manifest/roadmap split).
  Pushed as d11aab31.
- Open design question (asked, NOT YET implemented - answered with a recommendation, awaiting
  confirmation): user asked whether sessions proposing structural plan changes (new phases,
  deferring tracks, etc.) should post a comment somewhere for a single "planning session" to apply,
  so only one session ever writes structural changes. My recommendation: a dedicated per-plan
  GitHub tracking Issue (not a PR - plans aren't inherently PRs) as the stable mailbox; worker
  sessions comment-propose there instead of editing plan.yaml directly unless they ARE the
  designated planning/steward session for that plan; a single session applies accumulated proposals
  and replies-and-resolves each comment thread once applied. This mirrors the S0-steward pattern
  already used for real in rdr-refactor (workers flag things to the steward rather than touching
  shared coordination themselves - see D-ui.md's "Flag to steward (S0): #78 may still fold into #68"
  for a real precedent). Would need: a new optional `tracking_issue` field in the plan.yaml schema,
  plan-create creating the issue when bootstrapping a new plan, and a standing-instruction addition
  to session-start.sh's plan-section header + both skill docs. NOT built yet - waiting on the user
  to confirm this design before touching session-start.sh/schema/skill docs for it.

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
