# PR #196 - aggregate signature reads a missing attribute

Plan item `match-query-ergonomics / aggregate-signature-reads-a-missing-attribute`.
This session ran `/plan-item-resolve` for it - the item's own designated branch
`claude/plan-item-kickoff-match-query-npzr78` (PR #196), not the session's
originally-assigned scratch branch, which was cut from `integration` and has no
item of its own. All work below happened on npzr78, checked out locally.

## Plan

The item was already fully implemented and pushed by a prior session
(roadmap section 21) - PR #196, green, out of blockers, `mergeable_state: clean`.
This session's job was to gather live state (per `plan-item-resolve`) and act on
what it found: one unresolved review thread the developer left on the PR since
the prior session ended.

## Done

- Gathered live state: PR #196 clean/green (23 checks passing), one open review
  thread on `test_set_of_ranking.py:337` (closing assert of
  `test_ranking_names_the_ordered_by_aggregate_not_the_first_selected`),
  proposing the trailing "the sum" be spelled out in full instead of reduced.
- Built an isolated Python 3.12 venv (`pip install -e krrood -e random_events
  -e probabilistic_model`, plus `objgraph`) and ran the file with
  `--confcutdir=test/krrood_test` to skip the workspace-root `conftest.py` -
  17/17 pass, this test included. Confirmed by reading the code
  (`AggregatorRule.build` in `verbalization/grammar/aggregation/rules.py`)
  that the reduction is correct by identity (`referent_id=node._id_`): `tax`
  is the literal same object in both the order key and the selection, so the
  trailing "the sum" resolves back to it, exactly as `_highest_aggregate_
  modifier`'s docstring says it should.
- Concluded the comment is still onto something real, just not a code bug in
  #196: to a reader, proximity resolves "the sum" to the just-mentioned net,
  not the frame's tax three clauses back. Fixing that is a second root cause
  in `AggregatorRule.build`'s identity-only reduction, not a one-line change
  to this PR - the same "one root cause per PR" split #196 already made for
  its sibling issue (`chain-signature-reads-attribute-only-names`).
- Replied on the thread with the measurement and the question (change the
  assert here, or carve out a new item) rather than resolving it -
  unresolved until that answer lands.
  https://github.com/AbdelrhmanBassiouny/cognitive_robot_abstract_machine/pull/196#discussion_r3908782904
- Recorded the finding in `plan.yaml`'s item notes and roadmap section 24 (via
  `save-plan.sh --manifest/--roadmap`, since this branch has no plan-manifest
  markers in `CLAUDE.local.md`), then republished the plan dashboard.

## Next

- Nothing to do until the developer answers the reply. No code change was
  made to #196 - PR left exactly as found (draft, green, one open thread).
- Per the review-comment convention, do not resolve that thread until the
  chosen direction is actually implemented.

## Decisions

- Did not touch the test/code to match the comment's literal suggested text,
  since it would make the file's own tests fail and contradicts the design
  the existing docstrings state - flagged instead of guessed at.

## Round 2 (2026-09-02) - "handle latest review on 196"

The developer replied on the thread: "ok make fixing it an item of its own,
I am unsure though if this should be in match-query-ergonomics or another
plan or a new plan." PR #196 had also been flipped from draft to
ready-for-review by the developer themselves in the meantime (their own
"PR's job ends" signal per personal notes) - proceeded anyway since this
round was an explicit ask in-session, and left the PR's ready state alone
(did not re-draft it, per the stated exception for a PR the developer
marked ready themselves).

- Ran `/add-plan-item` to decide placement rather than guessing: scope check
  (`check_scope_overlap.py`, base `origin/main`) against every open PR that
  could plausibly touch `verbalization/grammar/aggregation/rules.py`,
  `verbalization/rendering/coreference_processor.py`, or
  `verbalization/microplanning/referring.py` (#192, #248, #33) found no
  shared paths and no duplicate intent.
- Put the three-way choice (match-query-ergonomics / eql-verbalization / new
  plan) to the developer via `AskUserQuestion` with the evidence for each -
  they picked `eql-verbalization`: the ambiguous reduction lives in
  `CoreferenceProcessor`/`DistinguisherIndex`, the same "same-noun-group
  disambiguation" machinery that plan's P2 built, and
  `p5-first-mention-type-annotation` already sits in that exact track for an
  analogous refinement of the same machinery.
- New item `aggregate-repeat-reduction-ignores-same-kind-siblings` recorded
  on `eql-verbalization`'s `plan.yaml` (track `framework-migration`,
  `depends_on: [p2-operand-naming]`, `not_started`) and its own roadmap
  section, via `save-plan.sh --manifest/--roadmap` (hand-edited scratch
  files, this session doesn't steward that plan). Structural-change comment
  posted on its tracking issue (#104), matching the convention. Dashboard
  republished: https://claude.ai/code/artifact/44efa6b1-3a07-4423-a3eb-9809b9c5d6cd
- Replied on PR #196's thread with the outcome and resolved it - the
  developer's ask ("make fixing it an item of its own") is done, and no code
  touched #196 itself for this.
