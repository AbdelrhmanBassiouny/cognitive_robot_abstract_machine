# EQL performatives — roadmap

Narrative companion to `plan.yaml`. Structured facts (branch, PR, status,
dependencies) live there; this file carries the "why", the history, and the
standing conventions the items assume.

Per-branch review-round detail, where it exists, stays in
`.claude/personal/pr-progress/<branch>.md` — that mechanism is independent of this
plan and is not duplicated here.

## What this plan is

EQL can already describe things. This plan adds the layer that says what is being
*done* with a description — a speech act framing it. Asking for it (`Find`,
`Generate`, `Report`), asserting it (`Inform`, `Explain`, `Warn`), or executing it
(`Perform`) are different acts over the same underlying content, and each frames it
differently in language.

Two decisions shape the whole design:

- **The framing lives in a register, not in a central registry.** `Register`
  captures exactly the two choices that depend on what is being done with a
  description: which verb opens it, and which keyword binds its fields. The default
  query register opens with *"Find"*/*"Generate"* and binds with *"given that"*; an
  imperative register opens with a fixed verb and binds with *"such that"*. Each act
  derives its opener from its own class name — there is no table mapping act names to
  verbs to keep in sync.
- **Acts live in the layer that owns the behaviour they name.** `Perform` belongs in
  coraplex, because coraplex owns plan execution; `Achieve`/`Monitor` belong in
  giskardpy. Only the framework-agnostic interface lives in krrood. This is why the
  giskardpy acts are a separate item rather than something #14 could have carried.

The second half of the plan follows from the first. Once krrood has composition
combinators (`Sequential`/`Parallel`/`TryInOrder`/`TryAll`) that verbalize, and
coraplex has plan nodes that execute the same shapes, keeping them as two parallel
hierarchies means every structure exists twice. **Approach M** collapses them:
`PlanNode` *is-a* `Performable` — one class implements both, rather than an external
visitor walking one to produce the other. That requires `Performable` to be a
field-less pure-interface ABC (so it composes as a mixin under ormatic's joined-table
inheritance, matching the proven `DesignatorNode(PlanNode, ABC)` shape), and the
verbalization shapes to be free functions over already-built fragments
(`interleave`/`coordinate`/`concurrent`) so both hierarchies call the same builders.

## How this became a four-PR stack

The original #14 bundled several independent features. They were split out because
they were genuinely separable, not to make review easier:

- **Arithmetic** → #11, based directly on `main`, **merged 2026-07-14**. Pure EQL
  core, never depended on anything performative.
- **Agreement** → #55. Subject/verb concord is a sentence-level grammar fact; it has
  nothing to do with speech acts.
- **Cardinality** → #54. Scalar-vs-collection rendering in grouped reports, likewise.
- What remained in #14 is the performative layer proper, with #15 stacked on it for
  the coraplex unification.

That leaves the linear chain `main` → #55 → #54 → #14 → #15.

### The stack moved off #36, deliberately

The grammar slices originally sat on #36 (`eql-symbolic-function-remove-decorator`).
That base was abandoned on 2026-07-19 after the *third* `parts_of_speech.py` conflict
on #55 — two of them within the same hour — caused by #36's operand-view/symbolic-
function migration still moving underneath. The feature never functionally depended on
anything unique to that stack, and the shared files were byte-identical to `main` when
it was first ported, so #55 was re-authored fresh onto `main` rather than carrying the
restacking merge commits forward. #54, #14 and #15 followed it off #36.

## The 2026-07-24 conflict and its 2026-07-30 resolution

**Resolved on 2026-07-30 (merge `c6ab6db8` on #55).** When the `eql-verbalization`
plan's #86/#87 landed and the fork's `main` was fast-forwarded on 2026-07-24, three
files conflicted (P3's #475 landed on top before the resolution; the conflict set was
unchanged):

- `verbalization/rendering/coreference_processor.py`
- `verbalization/rendering/realization.py`
- `verbalization/vocabulary/parts_of_speech.py`

The root cause turned out to be sharper than "P2 rewrote the same region": **`main`'s
P2 redesign had independently grown its own subject/verb agreement mechanism** —
`apply_subject_verb_agreement` in `fragments/base.py`, logically identical to #55's
`agree_finite` but applied *eagerly* at build/coreference time, the exact architecture
#55 replaces with the `AgreementProcessor` pass. Two parallel agreement designs, not
just overlapping edits.

The resolution unified onto the pass design, preserving both plans' intents:
coreference and `clause()` keep making the number *decision* (as `concord_number`
stamps — including main's coordinated-subject feature, which became a build-time stamp
because the pass only infers number from a plain `NounPhrase` subject), and the pass
alone derives the agreement. Main's now caller-less eager helper and its
`_with_agreed_copula` were deleted; `agree_finite` in `agreement_processor.py` is the
single implementation. Full `test_eql` suite green after the merge (1139 passed, the 3
pre-existing skips).

Standing risk, unchanged: this stack keeps re-conflicting in the verbalization
rendering pipeline for as long as the `eql-verbalization` plan lands work there — and
any future `main`-side agreement logic should be checked against the pass design
before merging, now that the two have collided once.

Nothing above #55 can merge until the restack cascade runs; #54, #14 and #15's
`mergeable_state: clean` against their own bases says nothing about whether they
survive it now that #55 has moved.

## Deferred follow-ups

These were explicitly scoped out of the PRs that named them, and are tracked as items
rather than left in PR descriptions where they would be rediscovered by accident:

- **Action verbalization** — a concrete `Verbalizable` action's own fragment (e.g.
  `NavigateAction`) plus operand field-name aliasing. Deferred out of #14, which works
  with any EQL content today through the generic *"given that"*/*"such that"*
  rendering.
- **Giskardpy acts** — `Achieve`/`Monitor`, placed in giskardpy per the distributed-
  placement decision above.
- **Phases C–D** — `LanguageNodes` verbalizing through the shared shape functions, and
  the `PerformativeNode` bridge.
- **Phase E** — migrating the demo onto coraplex's combinators, the end-to-end proof
  that one tree both executes and verbalizes.

## Testing conventions for this stack

- krrood's verbalization work is validated against the full `test/krrood_test/test_eql/`
  suite; 3 skips there are pre-existing and unrelated.
- Coraplex plan suites and sdt-world fixtures need the ROS container, which sessions
  generally do not have. For items touching `coraplex/` — #15 and the later bridge/demo
  work — CI on the push is the authoritative check, not the local run.
