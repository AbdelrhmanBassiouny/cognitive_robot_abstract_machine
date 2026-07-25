# Plan-dashboard system — status: PR #91 open (draft, base main), 2 review rounds addressed
# (62222c34, 9d4f7c6e), all 42 inline threads replied-and-resolved, subscribed to all activity.

## Review round (2026-07-25, 26 new threads on 023a63ec + a top-level "handle my feedback,
## clean up the code" review) — DONE, pushed as 62222c34
Session dispatched to branch `claude/pr-91-review-feedback-aqdu0o` (the assigned task branch),
but that branch didn't exist and isn't PR #91's head (`claude/plan-dashboard-system-sxnazc` is) -
confirmed with the user via AskUserQuestion (same situation as PR #87's precedent) that fixes
should go directly on the real PR head branch instead. Worked there.

Also found and fixed a real environment problem while testing save-plan.sh: this sandbox's
ambient git identity was `Claude <noreply@anthropic.com>`, violating AGENTS.md's Version
Control policy - some earlier commits on this PR/branch (and the disposable self-test commit
this session made before catching it) carry that identity. Fixed going forward by exporting
GIT_AUTHOR_NAME/EMAIL + GIT_COMMITTER_NAME/EMAIL inline in the same Bash call as every commit
(shell state doesn't persist between tool calls, so this must be repeated each time, not set
once) rather than touching git config. Cleaned up the disposable test commit with a
correctly-authored revert. Flagged to the user in the summary PR comment that older commits may
still need cleanup if they care.

Plan (tracked as TaskCreate tasks #1-#11 this session, all completed):
1. Remove remaining `rdr-refactor`/`rdr-roadmap.md` mentions: hooks/README.md:216,
   plan-create/SKILL.md:183 (the "I still see rdr-refactor" follow-up on an already-"fixed" thread -
   a real miss, only `SKILL.md`'s body text had been swept before, not the historical-note asides).
2. Centralize plan.yaml/roadmap.md path construction: add plan_manifest_path/plan_roadmap_path to
   resolve-personal-notes-config.sh, use from session-start.sh + save-plan.sh instead of each
   re-deriving the literal path. Fixes save-plan.sh's INDEX_PATH duplicating the already-sourced
   PLAN_BRANCH_INDEX_PATH constant (a real bug the reviewer's "hardcoded/repeated strings" comment
   caught).
3. branch-index.yaml's pseudo-YAML (matched via fixed-string grep, per the reviewer's "more
   deterministic/standard format" question) -> real TSV, awk-parsed. Fully regenerated every
   save-plan.sh run, so no migration needed.
4. save-plan.sh: add --manifest/--roadmap file flags so plan-create doesn't need the
   marker-edit-CLAUDE.local.md dance just to bootstrap a new plan (reviewer's "can this be
   automated" question on the marker flow).
5. Design-question threads answered inline (track vs wave definition, depends_on already supports
   multiple ids - just undocumented, "should sessions edit manifest + comment on steward issue" -
   answering with reasoning, not silently redeciding the already-locked-in tracking_issue design).
6-7. build_dashboard.py/build_index.py/render_common.py: StrEnum + dataclasses throughout (Plan/
   Wave/Track/Item/ValidationProblem/Summary; markdown_to_html's tuple-tagged blocks -> typed
   classes), no abbreviations, full type hints + RST docstrings, match/case where it clarifies,
   HTML building restructured into smaller named helpers (kept dependency-free - no templating
   engine - per render_common.py's own stated design goal).
8. pytest tests for all three scripts + a new lightweight (non-docker-matrix) CI job.
9. Root README.md: new dev-tools section linking hooks/README.md + both skill READMEs.
10. Global sweep of AGENTS.md rules (abbreviations, hardcoded strings, dataclasses, docs/type
    hints) across every file this PR touches, per the reviewer's explicit "apply my local comments
    globally" instruction on the top-level review.
11. Reply-and-resolve every thread once genuinely addressed; leave open (reply only) any thread
    that's a question rather than an actionable ask, per the personal convention.

**Result**: all 11 tasks done, pushed as commit 62222c34 (16 files, +2021/-561, new
`tests/` dir with 50 pytest tests). 25 of 26 inline threads replied-and-resolved; 1 left
open (reply only) - the "should non-steward sessions edit the manifest directly + comment"
design question, since it's a real coordination-model choice for the user to make, not
something to redecide unilaterally. Also replied to the top-level "handle my feedback, clean
up the code" review with a summary comment. PR description updated to describe this round;
PR was already draft, stayed draft. `subscribe_pr_activity` call this session failed
("Could not subscribe to this PR") - unclear if another mechanism already covers it or the
session's subscription silently didn't take; worth a manual check if events don't show up
on a future push.

## Review round 2 (2026-07-25, 16 new threads on 62222c34 + the design-question follow-up
## comment) — DONE, pushed as 9d4f7c6e
User answered the open design question directly (not via review comment): any session may edit
plan.yaml structure directly (no steward), must always comment on the tracking issue, and
sessions actively working an item should subscribe to the tracking issue itself for realtime
awareness of structural changes other sessions make. Confirmed via AskUserQuestion: chose
"Subscribe to tracking issue" over posting a comment to every affected session's PR (subscribing
reuses the existing subscribe_pr_activity mechanism, which already works identically on a plain
issue number, and scales without an N-PR fan-out on every structural edit).

Implemented for real (not just answered in a reply):
- session-start.sh: TRACKING_ISSUE_NOTE rewritten to state the any-session-edits model, require
  a comment on the tracking issue for every structural change, and tell an actively-working
  session to subscribe to the tracking issue in addition to its own item's PR.
- hooks/README.md: matching rewrite of the tracking-issue paragraph (was still describing a
  "designated planning/steward session" model).
- PR #91's own description: "Single-writer coordination" section renamed and rewritten to match
  (was stale from before this decision).

Other 15 threads, all code-level follow-ups on round 1's rewrite:
- render_common.py: hand-rolled markdown block parser replaced with the real `markdown` library
  (tables + fenced_code extensions); only the heading-level-shift logic stayed custom. Verified
  actual output via direct experimentation (paragraph continuation keeps literal newline, links
  get no target=_blank, raw inline HTML passes through unescaped) before writing tests against it
  - disclosed both behavior differences from the old hand-rolled version as accepted trade-offs
    in the reply rather than silently absorbing them.
- build_dashboard.py/build_index.py: all hand-built HTML-string methods deleted, replaced with
  Jinja2 templates (templates/dashboard.html, templates/index.html) - autoescape on by default,
  `| safe` used explicitly only at the one deliberately-unescaped call site (pre-rendered roadmap
  HTML). Python side now returns plain data (StackedItem/TrackSection/WaveSection dataclasses)
  for the templates to iterate, not markup.
- ValidationProblem redesigned from ValidationProblemKind (enum) + generic dataclass into an ABC
  with one concrete dataclass subclass per problem (DuplicateItemId, UnknownTrack, UnknownStatus,
  InvalidDependsOn, UnknownDependency, UnknownWave, InvalidSchemaVersion), each owning its own
  describe(). Caught and fixed my own bug mid-edit: first pass used a list comprehension for
  DuplicateItemId's payload, which would double-count an id appearing 3+ times - reverted to the
  original set-based dedup wrapped in sorted().
- LiveState gained an explicit NO_PULL_REQUEST member (replaces a `None` special-case, keeps the
  existing live-none CSS class); Item.pr -> Item.pull_request_number, DashboardRenderer.pr_data ->
  pull_requests_by_repository (wire format / YAML key `pr` unchanged, only the Python identifiers
  spelled out); "GFM" spelled out to "GitHub-flavored markdown" in prose.
- save-plan.sh's two inline `python3 -c` snippets extracted into a real, tested, documented script
  (plan_manifest_tools.py, read-id + regenerate-branch-index subcommands).
- Docstring audit pass: every previously-undocumented public method in build_dashboard.py got one
  (7 describe() overrides, _load_pull_requests_by_repository, _classify_items, _live_state_of,
  _drift_description_of, _compute_next_steps, _status_counts, the nested walk() in
  _build_track_stack).
- Replied (no code change) to: why conftest.py uses a sys.path shim instead of a package
  __init__.py (script is a standalone tool, not a package); why Plan/Item are real dataclasses
  and not raw dicts in the tests too; that a plan id is a deliberate kebab-case slug, not a UUID.
- README.md: added the missed "local-code-review" skill bullet to the dev-tools section (the
  skill existed already, just wasn't linked yet).

**Result**: all 16 threads replied-and-resolved (including the design-question thread, now
genuinely answered and acted on rather than left open). Test suite grew 50 -> 53 passing; CI's
pip-install list extended with jinja2 + markdown. Pushed as 9d4f7c6e (commit message: "Second
review round: Jinja2/markdown libraries, ValidationProblem hierarchy"). PR description rewritten
to add a "Review round 2" section and to fix the now-stale "single-writer/steward" coordination
paragraph in the Summary. PR was already draft (round 1 left it that way), stayed draft - no
new push-then-forgot-to-redraft gap this round since it was draft the whole time.

## PR #91
- https://github.com/AbdelrhmanBassiouny/cognitive_robot_abstract_machine/pull/91 — draft, base `main`.
- Contains only the main-bound infra (hooks + skill), per the user's request to keep it separate
  from the personal-notes data (schema/rdr-refactor migration, which stays on `claude/personal-notes`
  and is never part of any PR).
- Commits: f224198d (hooks + skill), b59c9b54 (dependency-stacking + next-steps sidebar
  generalization), 66dd5792 (plan-create skill), d11aab31 (roadmap.md rendering fix),
  1f5590fd (tracking-PR mailbox), 6845687f (tracking_issue migration), 2947dd1f (plan-mode-approval
  input clarification), c77cda67 (script extraction + genericization - see below). PR description
  updated to match all 8 commits.
- 2026-07-21 ~14:32 check-in: CI fully green (18/18) on head 2947dd1f, mergeable_state clean.

## Review round (2026-07-21, 6 threads on 2947dd1f)
- 4 threads: "remove explicit rdr-refactor mention" (plan-create x2, plan-dashboard x2) - all
  genuine, both SKILL.md files are meant to be fully generic. Fixed by removing every named
  reference to the rdr-refactor plan as an example. Replied + resolved all 4.
- 1 thread: "why does the skill know how to render the dashboard, shouldn't this be a script?" -
  correct and important: I'd only prototyped the rendering logic in an uncommitted scratch file,
  so every real /plan-dashboard run would have had the LLM re-derive the markdown converter,
  drift/status logic, and stacking algorithm from prose each time. Fixed for real: extracted to
  `.claude/skills/plan-dashboard/{render_common,build_dashboard,build_index}.py` (+ their HTML
  templates), all committed and tested - build_dashboard.py now also owns manifest validation
  (moved out of SKILL.md prose too), confirmed it rejects a broken depends_on/track reference with
  a clear error. SKILL.md rewritten to describe what to gather + how to invoke the script, not the
  algorithm. Replied + resolved.
- 1 thread: "can rendering/status updates be a GitHub workflow instead of tokens?" - real
  constraint found and explained: the Artifact tool (which is what actually publishes to
  claude.ai/code/artifact/...) only exists inside a live Claude session - a GitHub Actions runner
  cannot call it, so full workflow automation of the CURRENT hosting mechanism isn't possible.
  Replied with the actual tradeoff (GitHub Pages + real automation but a different URL/hosting,
  vs. keeping Artifact hosting but still needing a session to fire - now much cheaper, just
  "run script, call Artifact"). Asked which they want, and whether to revisit the periodic-Routine
  idea they declined earlier now that there's a concrete reason to. NOT resolved - awaiting answer.
- Regenerated + republished the live rdr-refactor dashboard from the new committed script's own
  output (confirmed byte-compatible with the prior prose-derived version). One stray duplicate
  Artifact was minted using the wrong file path during this (82418c3c-...) before I caught it and
  republished to the correct original path (55da1cc9-...) - the stray one is harmless/private,
  left alone.

## Follow-up request #6 (formalize the plan-mode -> plan-dashboard hook)
- User asked me to walk through how a normal session (plan-mode: describe features -> Claude drafts
  a markdown plan -> user approves) should connect to the dashboard/tracking-issue/skills system,
  then said to formalize it. Answer given: the two are different layers (native plan-mode = ephemeral,
  per-task; plan-dashboard = persistent, multi-session) and the hook point is the moment right after
  plan-mode approval, judging scope.
- Formalized as a new standing rule in cram-notes.md ("## Plan-mode approval -> persistent plans",
  pushed to personal-notes as 94278860): after approval, if the work is multi-PR/session, either
  `/plan-create` a new plan (feeding it the approved plan-mode markdown as source) or fold it into
  an existing plan (edit directly if designated session, else comment-propose on tracking_issue).
  If single-PR/session, do nothing extra.
- Also clarified plan-create's SKILL.md step 2 (pushed as 2947dd1f): an already-approved plan-mode
  plan from the same conversation is explicitly valid input under "existing freeform doc to migrate"
  - no need to have it saved to a file first.

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
