# Probabilistic knowledge-guided perception

A follow-up to the `knowledge-directed-*` programme (tracking issue #201), created
2026-09-05 out of a discussion on #270. **Deliberately outside the ICRA budget**: nothing
here is needed for the 2026-09-15 deadline, and the demo items in the three grounding
plans do not depend on it. It is written down now because the question came up while the
evidence for it was in front of us, and because the answer is a different paper.

## The question

The programme's claim is that a robot which knows what it is looking at perceives better.
It is demonstrated, but the demonstration is qualitative: a belief either lets a piece be
found or it does not. The natural next question is *by how much* - and that needs the
belief and the picture to be on one scale.

## What the code actually does today, and why it cannot answer

`competing-explanations` (#270) settled the decision rule: what is reported must lead
every other account of its place - the board's own geometry, the next candidate the
belief allowed, and nothing being there. Knowledge reaches that rule through exactly one
channel, `PieceHypothesis.candidates`: a belief naming one piece leaves no runner-up to
lead, an unguided look over six does. A second channel, `BelievedPlace`, narrows where the
search runs.

Both are **admissibility**. A belief can delete a rival; it cannot make a candidate worth
more. `expectations-from-events` (#257) already hit the wall this leaves, in its own note:
two of its four lid captures do get a history-seeded fit, and it *loses to a ghost cylinder
at the same place*. The belief said "this piece, here", the picture scored the ghost
higher, and the rule gave the belief nothing to spend.

The obvious patch - add a bonus to `strength` when a piece is expected - is the tuning
this programme has refused three times. `strength` is the harmonic mean of two coverage
fractions: a fit score, not a probability of anything, and not even uniform along its own
range (a 0.075 lead near 0.5 is a large relative change; near 0.9 it is noise). There is
no defensible size for a bonus on it.

## The frame that does take a prior

For one place, with hypotheses `H_c` (known piece *c* at a pose), `H_board` (the board's
own geometry) and `H_0` (nothing there), report *c* when, against every rival *r*:

```
[ log p(E|H_c) - log p(E|H_r) ]      evidence  - what the picture says
+ [ log P(H_c|K) - log P(H_r|K) ]    prior     - what the robot knows
>= log lambda                        cost      - C(wrong report) / C(missed piece)
```

Three terms, three owners, and the property the current rule lacks: knowledge enters
**additively**, at a stated exchange rate. One nat of prior buys exactly one nat of missing
picture. Two consequences worth the work:

- `required_lead`'s docstring currently *says* it states a cost. In log-odds that becomes
  literally true. Today 0.075 had to be measured off six captures, which makes it a
  detector parameter wearing a cost's clothes - and it shows: the cube on
  `tracy_pickup_demo` clears its runner-up by 0.076 against a required 0.075, four parts
  in a thousand.
- The claim becomes a curve. Detection rate against log prior odds at fixed cost. Today
  the only x-axis available is candidate-set size, 1 against 6.

Standard names, so the follow-up paper can cite rather than reinvent: Neyman-Pearson (a
threshold on the likelihood ratio is *optimal* at a given error trade-off, which says
that #270's "a lead over rivals" structure is right and only its quantity is wrong);
Bayes factors and Bayesian model comparison, where Jeffreys' evidence scale is `required_lead`'s
ancestor; Bayes risk for the threshold; recursive Bayesian estimation for carrying a
belief across frames; MHT/JPDA data association for resolving competing claims on one
place jointly rather than in sequence, which would subsume both this and
`one-detection-per-thing`'s occupancy rule; MDL and pattern theory for the generative
version below. Dempster-Shafer, subjective logic and fuzzy scores are the alternatives and
are not recommended: no clean cost semantics, and the cost semantics is the whole gain.

## Where each term comes from here

**Prior.** `BelievedPlace` is already a uniform prior on a box (a radius and a yaw
interval) plus a 0/1 prior on category. `random_events`' `SimpleEvent` is a product of
variable domains - which is what a believed place *is*, in disguise - so the type has a
natural home. The propagation rule is `expectations-from-events`' own and is worth
defending in the paper as a modelling choice, not a shortcut: a belief decays when
something *acts* on the object, not with elapsed time, which makes it a jump process
rather than a diffusion.

**Likelihood.** The hard half, and the reason the item starts with a measurement.

- *Calibrate the score we have.* A monotone map (Platt, or isotonic) from `strength` to a
  log-likelihood ratio, fitted on labelled place-account pairs. Cheap and entirely
  standard. `test_montessori_detection_on_captures.py` already computes the confusion
  table it would be fitted on. The honest risk: six captures is not a calibration set, so
  it must be held out or it is only `required_lead` re-tuned.
- *Model the edges generatively.* The two-sided score is already a shadow of a coding
  argument - `outline_followed` is model support, `edges_accounted_for` is residual left
  unexplained. Give each edge pixel an explaining model or a background process at some
  rate, and `log p(E|H)` becomes a sum over pixels: report the account that shortest
  encodes the picture. Stronger, and "the board is one of the accounts" stops being a
  special case and falls out. Much more work, and not this item.

## What is already in the workspace

Verified 2026-09-05 by reading the source, not assumed:

- `random_events` - `Event`/`SimpleEvent` product algebra over intervals and sets.
- `probabilistic_model` - probabilistic circuits, JPT,
  `RelationalProbabilisticCircuit.ground(statement)`, causal circuits.
- `krrood.parametrization` - `Match` -> `UnderspecifiedParameters` -> `ModelRegistry` ->
  `ProbabilisticModel`, surfaced in the entity query language as `probability_of(...)`,
  `distribution_of(...)` and `average(...)`.

So "P(a cube is in this region | what the twin knows)" is expressible as a query against a
registered model rather than as a new probability layer inside the perception package. And
since `perception-backend` (#222) already makes looking a query backend, the prior and the
look end up in one language. That is the design that makes this coherent rather than a
bolt-on - and it is why this is a follow-up rather than a rewrite.

## Risks, to design against rather than discover

- **A prior can hurt.** A wrong belief - someone moved the piece - produces a *confident*
  wrong report. That is `expectations-from-events`' failure-detection story from the other
  side, so one experiment yields both the gain curve and the failure mode. Good material,
  if it is measured rather than avoided.
- **The exchange rate cuts both ways.** A strong enough prior reports a piece that is not
  visible at all. Either cap the prior term or keep the "nothing is there" account honest
  enough to win on an empty picture. This is a design decision the item must make
  explicitly, not a bug to find later.
- **Six captures.** Stated once more because it is the thing most likely to be waved
  through: the prototype's whole job is to say whether the data supports a calibrated
  likelihood. "It looked better on the six" is not that answer.

## Relationship to the plans it follows

- `knowledge-directed-grounding` #270 `competing-explanations` - the structure this
  replaces the quantity inside. It survives: the comparison, the board as an account, the
  rival list. Only what is compared changes.
- `knowledge-directed-expectation` #257 `expectations-from-events` - supplies the belief,
  and is the item currently blocked by not being able to spend it.
- `knowledge-directed-requests` #239 `detector-parameters-from-knowledge` - the nearest
  neighbour, and **not the same mechanism**. It makes the threshold situation-dependent by
  rule: knowledge moving the bar. This plan has knowledge moving the score. A rule tree
  can mimic a prior, but non-additively and with no exchange rate - it relearns per
  situation what this computes once.
- `icra-mechanism` `knowledge-ablations` - switches each knowledge source off entirely.
  That is the binary version of this plan's curve, and the two would read well together.

## Why it is not folded into #270

Run 2026-09-05, per the scope check in `.claude/skills/add-plan-item/scope-decision.md`.
`explanations.py` exists on no branch but #270's, which flags it. The fold test then
settles it: strip the edits to #270's files and there is still a calibration study, a
prior type over `random_events`, a log-odds decision rule and a gain curve - substantial
work standing on its own. #270 is complete, reviewed, and was taken out of draft by the
developer on 2026-09-05, so folding would mean reopening a finished branch to change the
quantity it was reviewed on. This builds on it instead.
