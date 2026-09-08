# Mutagenesis Causal Query: Results

This is an experiment carried out using relational causal circuit for  the Mutagenesis dataset: we take the CTU
Mutagenesis dataset, register chlorine count as a cause of mutagenicity on a circuit
grounded from it, and ask what backdoor adjustment says once we control for the
dataset's known `ind1` indicator. It follows on from fitting and validating the
relational circuit on the full dataset (covered separately), and runs on the whole
188-molecule dataset.

## What we did

1. Fit a relational circuit on all 188 molecules, with the class circuit divided by
   chlorine count so it's support-deterministic over that variable.
2. Grounded a query for a two-atom molecule with every atom's element left
   unspecified, so chlorine count stays a variable instead of being integrated out.
3. Registered chlorine count as the cause, mutagenicity as the effect, and `ind1` as
   the adjustment variable, trimmed the circuit to just those three, and verified the
   result is support-deterministic.
4. Ran backdoor adjustment and compared it against naive conditioning at every
   chlorine-count value the grounded circuit's support covers.

Code: `causal_query.py` (`ChlorineCountCausalQuery.run`), `dataset.py`.
Tests: `test/causal_reasoning_test/test_causal_query.py`.


## The data

Chlorine really is rare in this dataset (188 molecules, 125 mutagenic):

| Chlorine count | Molecules | Share |
|---:|---:|---:|
| 0 | 177 | 94.15% |
| 1 | 5 | 2.66% |
| 2 | 3 | 1.60% |
| 3 | 1 | 0.53% |
| 4 | 1 | 0.53% |
| 5 | 1 | 0.53% |

This table earns its place here for two reasons, not just as color: it's the reason
grounding needs `2000` Monte-Carlo samples rather than the JPT default of 10, a value
seen in only 1 of 188 molecules has better than a 99% chance of never being drawn at
that default, and 2000 draws pushes that miss chance under 1% even for the rarest value
($(1 - 1/188)^{2000} \approx 0.005\%$) and it's the reason to read the chlorine
counts 3-5 rows below as single-molecule anecdotes rather than statistics.

## Why chlorine count, and not something more common?

Not because chlorine is expected to be the main driver of mutagenicity here -- the
QSAR literature this dataset comes from already points to `ind1` as the established
predictor, and nothing below overturns that. Chlorine count is the interesting choice
for a different reason: it doesn't exist as a variable until a query is grounded. It's
an aggregate on "how many chlorine atoms does this molecule have" which is computed over each
molecule's `atoms`, the exchangeable relation `RelationalProbabilisticCircuit` grounds
per query. A flat `CausalCircuit` can register any variable that's already sitting in
its data as a cause; this experiment is here to check whether the same pipeline works
once the cause has to be *assembled* from a relation first.

Chlorine being present in only 11 of 188 molecules understandably reads as an odd pick
for that demonstration, so before writing this we actually tried registering something
more common instead: oxygen count (every molecule has 2-9 oxygens, and it splits by
mutagenicity more sharply than chlorine does -- mean 2.70 for non-mutagenic molecules
versus 3.34 for mutagenic ones), nitrogen count (also present everywhere), and the two
existing bond aggregates, `double_bond_count` and `aromatic_bond_count` (every molecule
has both, and `aromatic_bond_count` splits by mutagenicity even more sharply than
oxygen -- mean 9.08 versus 15.28 -- which lines up with aromatic ring systems being a
textbook genotoxicity alert).

Every one of those four alternatives fails
`CausalCircuit.verify_support_determinism` on the grounded circuit -- not a fallback
warning, an outright exception, the same way it would if we tried to ship a genuinely
broken registration. Chlorine is not a stylistic choice among equals; it is, empirically,
the only one of the five aggregates this dataset offers that the current grounding
pipeline can register as a cause at all. The likely mechanism: `GroundingMode.SAMPLED`
mounts one mixture branch per Monte-Carlo draw rather than deduplicating draws that land
on the same value, so once enough draws exist to see a variable's less common values at
all (the `2000` samples explained above), two branches can end up reporting the exact
same retained value and are then, correctly, flagged as not pairwise disjoint.
Chlorine's distribution -- one dominant value at 94% and a long, individually-rare tail
-- happens not to trigger this with the fixed seed this experiment uses; oxygen,
nitrogen, and both bond aggregates, with their real spread across a large share of the
188 molecules, do. This reads like a genuine gap in `GroundingMode.SAMPLED`'s
disjointness guarantee rather than anything about chlorine specifically, and is worth a
follow-up in `probabilistic_model` rather than papering over here by picking whichever
variable happens to survive it.

## Why not ground this analytically instead?

`GroundingMode.EXACT` sidesteps Monte-Carlo sampling entirely by enumerating the fitted
circuit's own exact partition over the aggregate -- but only when
`ExchangeablePartGrounder._undetermined_latents_partition_disjointly` finds that
partition already disjoint; otherwise it logs a warning and falls back to `SAMPLED`
(see `rspn.py`). We checked that precondition directly against the fitted circuit for
chlorine count and both bond aggregates: it comes back `False` for every one of them,
stratified by that same variable or not. None of the aggregates we tried are, today, a
natural split feature the induced tree separates cleanly on their own, so `EXACT` is
not actually reachable here yet -- `SAMPLED` is not a fallback we chose over a working
alternative, it is the only grounding mode that runs to completion for this
experiment.

## Results

`P(mutagenic = True)` at each chlorine-count value, naive versus backdoor-adjusted for
`ind1`, on the full dataset:

| Chlorine count | Region P(chlorine count) | Naive P(mutagenic) | Adjusted P(mutagenic) |
|---:|---:|---:|---:|
| 0 | 0.9415 | 0.6893 | 0.6854 |
| 1 | 0.0266 | 0.4000 | 0.6609 |
| 2 | 0.0160 | 0.3333 | 0.5479 |
| 3 | 0.0053 | 0.0000 | 0.0000 |
| 4 | 0.0053 | 0.0000 | 0.0000 |
| 5 | 0.0053 | 0.0000 | 0.0000 |

The region probabilities match the dataset's own chlorine-count distribution exactly
(0.9415 &asymp; 177/188, 0.0053 &asymp; 1/188), so grounding is retaining the real
population, not something a Monte-Carlo artifact would produce. The circuit passes
support-determinism verification, and the whole thing runs end to end in a few seconds.

## Inference

- **Naive conditioning looks like a downward trend, but it's mostly sample size
  talking.** P(mutagenic) drops from 0.69 at chlorine count 0 (177 molecules) to 0.0 at
  counts 3-5 (1 molecule each, and that one molecule happens not to be mutagenic).
  Nothing about a sample of one supports a trend.
- **Adjusting for `ind1` moves counts 1 and 2 up, not down, which is the opposite of
  what a naive read of the drop above would suggest.** At chlorine=1, naive says 0.40
  but adjusted says 0.66; at chlorine=2, naive says 0.33 but adjusted says 0.55. Both
  chlorine=1 and chlorine=2 molecules happen to move towards `ind1=False`, which pulls
  their naive mutagenicity rate down since `ind1=False` molecules are less often
  mutagenic overall, once that's accounted for, the picture looks more like chlorine
  count 0's own rate than the naive numbers let on. Chlorine counts 3-5 stay at exactly
  0.0 either way: their one molecule is `ind1=True`, and the adjustment formula has
  nothing else to average in for the missing `ind1=False` cell, so it just reports what
  that one molecule says.
- **This doesn't tell chlorine count a real cause of mutagenicity.** The backdoor
  criterion only tells you the adjustment is arithmetically sound given `ind1` as the
  full confounder set; it can't tell you whether `ind1` actually *is* the full
  confounder set for chlorine count in this domain, because nothing here constructs or
  checks the underlying causal graph and that's an assumption we're bringing in, not one
  the circuit verifies. Read this as "the tractable-circuit backdoor machinery ran
  correctly on real, awkward, sparse relational data," not as a chemistry finding.

## What would make this more interesting

The genuinely interesting version of this experiment registers `ind1` itself (or
whatever the fitted circuit's own aggregates suggest) as the cause, runs the same
backdoor machinery, and checks whether the analytic answer for "why is a molecule
mutagenic" agrees with what the literature already says about `ind1` -- and, further
out, whether a circuit built this way is competitive with a plain classifier on
held-out accuracy rather than only self-consistent. Both are real next steps, not
implemented here: `ind1` is a flat `MutagenesisMolecule` field, not an aggregate
grounding assembles, so registering it as a cause doesn't exercise the same
relational-grounding pipeline this experiment is validating, and a held-out-accuracy
comparison is a separate benchmark this dataset-and-pipeline check wasn't set up to
run. Both are worth their own follow-up rather than folding into this one.


