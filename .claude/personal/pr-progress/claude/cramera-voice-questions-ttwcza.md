## PR B — voice questions (draft #168, branch `claude/cramera-voice-questions-ttwcza`)

Stacked on PR A (#167, `claude/cramera-verbalization-voice-ttwcza`) which sits on
PR #165. Status: **PR A merged in as `abcb6ee7a`, pushed; still a draft**.

Layout now: the text bar stays; 🎤 sits inside the bar to the right of Run; a
recognized preset fills the bar with its code and its verbalization shows big
under the bar (from PR A). Matching unchanged: `/api/question` + `/question`,
rapidfuzz token_set_ratio vs label + verbalization text, MINIMUM_SIMILARITY=70,
server-supplied "Sorry, I cannot answer that question." reply.

### Merging PR A (2026-08-18)

Brought down PR A's two fixes: the scrolling console and the source-link
fallback. One textual conflict — both branches had appended a test section to
the end of `test/cramera_test/js/test_eql_panel.js`, so both were kept. The
harness merged additively on its own (A's `scrolledIntoView` counter beside this
branch's `recognizerClass()` / `speak()` / `mountPanel(overrides, recognizer)`),
as did `app.css` and `test_web_assets.py`.

The conflict that mattered was invisible to git. PR A added `showAnswer()` —
write the answer, then scroll to it — and routed `renderAnswer`'s three writes
through it, deliberately leaving the four unasked ones (load failure, hint,
entity description) alone. This branch had meanwhile added three answer writes
on the voice path (sorry reply, matcher error, capture failure) on different
lines, so they merged silently and kept writing straight to the element: a
spoken question's reply would have landed below the fold of a console that now
scrolls. All three now go through `showAnswer`, since a question asked aloud is
still asked; the comment's "Only a query" became "Only what was asked". The
matched path already went through `runQuery` → `renderAnswer`.

Worth remembering: this is the third silent conflict on this stack, after
`giskardpy/executor.py`'s dropped `Optional` twice. Same shape every time — one
side centralises something, the other adds a new use of the old way, no shared
line. After a merge, grep the call sites of whatever the base just centralised
and check the incoming side didn't add one that should have been converted.

Tests: 611 passed (full cramera suite, was 598); 221 node tests across 23 files.
The new test (`a spoken question nothing answers is scrolled to like any other`)
was run against the unfixed panel first and fails there.

### More questions, asked aloud (2026-08-18)

The matcher now recognizes four kinds of question beyond the preset buttons.
Live-only buttons: `what is your current goal?` (the shape being sorted, from a
new `ShapeUnderTest.is_current`), `what is your current action?` (the running
plan's innermost RUNNING node, via `progress.follow_plan` reading the plan while
it performs), and `what actions did you perform?` (a new `action` domain over
`PerformedAction`, whose plan-step counterpart gained `PlanStep.is_action`).
Written out per type, matched but never shown as buttons (new
`LiveQuerySource.unlisted_presets`, `PresetsPerType` in cramera): "give me all
pick up events" for every segmind event type a record is written for
(`SegmindEventRecord.recordable_event_types()`), and the same for actions
(`PerformedAction.performable_action_types()`).

The demo hands the plan over before `node.perform()` (new
`_perform_attempt_plan`), which is what makes the current-action answer live.
`MONTESSORI_PRESETS` is untouched, so the recorded bundle's presets.json needs
no submodule change.

Matching gained a tie-break: token_set_ratio gives a perfect score to any
wording that contains the asked words, so "give me all pick up actions" scored
100 against "give me all move and pick up actions" too and lost the tie by list
order. `_comparison` now pairs the score with how many words the wording added,
so the more specific wording wins; pinned in `TestAShorterWordingWinsATie`.
Caught only by running the full experiments suite — the matcher's inputs change
with what a run imports.

Tests: cramera 620; experiments 477 passed with 5 failures that all reproduce
at HEAD (`presets.json` drift with the upstream scenes submodule, two
results-recording ones, one event-monitoring one, two franka-panda-equipment
grasp-contact ones — see next).

Committed and pushed as 564c1f0fa; the PR description gained a "More
questions, asked aloud" section (gh's GraphQL edit path is broken by the
classic-Projects deprecation, so it went through the REST API). Still a draft.

### Reading a read-only results database (2026-08-18)

The developer hit `permission denied for schema public` while querying the
episodic database: `FRANKA_MONTESSORI_SORTING_DATABASE_URI` (set in `~/.bashrc`)
points at the shared results DB on localhost:5433 — an ssh tunnel to a remote
PostgreSQL 17 whose `semantic_digital_twin_readonly` role has USAGE only — and
`open_session` prepared the database before reading, issuing CREATE TABLE for
every table the generated schema knows of but the remote lacks. The record
path already degraded (`verify_writable` → `RecordsNothing`), only the query
path crashed. Fixed by giving `open_session` a `create_missing_tables` flag and
having the episodic-memory evaluation ask for sessions without it; both new
tests verified red without the fix. Committed and pushed as 22845f77b; the PR
description gained a "Reading a read-only results database" section. Still a
draft.

### Outstanding
- CI not checked on #167/#168.
- Pre-existing red in this checkout: `presets.json` in the scenes submodule
  (upstream cram2/cram-scenes, no fork to fix it from) is out of step with
  `MONTESSORI_PRESETS` ordering/scopes; `test_franka_panda_equipment`'s two
  grasp-contact tests call `apply_grasp_contact_parameters` without its new
  `friction` argument; two `test_montessori_results_recording` tests log
  nothing for an unreachable database here; one event-monitoring test raises
  `MissingReferenceFrameError`.
