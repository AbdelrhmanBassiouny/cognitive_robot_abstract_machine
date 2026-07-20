PR #89 — branch `conditions-root-drop-dead-parent-recovery`, off `main` (not the
session's designated `claude/ripple-down-rules-refactor-mivivh` branch, which never
got its own commits — this PR was a side-quest that came out of surveying that
branch's whole "ripple down rules refactor" stack).

## How this started
Asked to check the ripple-down-rules-refactor status and all related PRs. Found the
stack: query-class-refactor (#452) and eql-core-prep (#453) merged to main;
code-extraction (#58), code-generation-extract (#39), ripple-down-rules-refactor
(#53, replaces closed #40) open/clean/CI-green but unreviewed; rdr-backward-inference
(#41) blocked by a real merge conflict (an automated restacking bot flagged it
`needs-resolution`) in `base_expressions.py` over whether `_last_parent_of_type_`
should exist; D-core-aid (#63) through D-core-engine (#68) — the full re-split RDR
engine chain replacing closed #60 — open, stacked on #41, inheriting its staleness.

## What #89 actually does
Root-caused the #41 conflict: `_last_parent_of_type_` was `_conditions_root_`'s
fallback for a condition node reused across separate queries. Verified — first via
targeted probing, then exhaustively (instrumented the old method, ran the *entire*
test_eql/test_ormatic/test_class_diagrams/test_ripple_down_rules suite, 1275 tests,
with it reinstated: zero calls anywhere) — that it's genuinely dead, not just
redundant with `ActiveConditionsRoot` (the reasoning `rdr-backward-inference`'s own
deletion commit used, which doesn't actually hold — `ActiveConditionsRoot` solves a
different, evaluation-time problem). Traced its real origin: added for
`ConclusionSelector.insert_at` (the API `insert_refinement`/`insert_alternative` —
the RDR engine's live rule-growth calls) to patch a node-clobbering bug PR #47 later
fixed at the source; commit `84924e87` (already on `main`) already proved it dead
for `insert_at` specifically and removed it there. #89 finishes that cleanup for
`_conditions_root_`'s own remaining use.

Cross-checked against the real RDR engine, not just main: merged #89 into
`D-core-engine` (tip of the #63–68 chain, has the live `EQLSingleClassRDR.fit()`
machinery) and ran `test_eql_rdr` — 220 passed either way, same 8 pre-existing
unrelated failures (a NamedTuple-vs-tuple spy-test equality quirk) with or without
the change.

Four regression tests added (TDD, each confirmed passing before *and* after removal,
per a review comment asking for broader coverage than the first one alone gave):
condition shared directly by two Filters; a subexpression shared two hops down inside
AND compounds; a rule's condition reused as a different query's filter after its own
tree was built; and `Refinement.insert_at` called directly with an already-parented
condition (the literal clone-before-splice path `insert_refinement` uses).

## Status
Draft PR, CI green (18/18), `mergeable_state: clean`. One review thread (asking for
broader test coverage) replied-to and resolved. PR description updated with the full
history/verification. Subscribed to all PR activity; hourly check-ins scheduled via
`send_later` (re-arms itself silently when nothing's actionable).

## Next
- Keep watching #89 until merged — re-arm check-ins, act on any CI failure or comment.
- Once merged to `main`, the automated restacking bot should cascade this down
  through code-extraction (#58) → code-generation-extract (#39) →
  ripple-down-rules-refactor (#53) → rdr-backward-inference (#41), clearing #41's
  conflict for free since `rdr-backward-inference` already independently deleted the
  same method. Verify that actually happens after merge; nudge manually if the bot
  doesn't pick it up.
- After #89 lands, worth returning to the broader stack survey: #58/#39/#53 looked
  ready to merge (clean, CI-green, no open threads) but were never actually reviewed
  or merged as of this check — that's the next logical step in the larger
  ripple-down-rules-refactor effort once this unblocking piece is done.
