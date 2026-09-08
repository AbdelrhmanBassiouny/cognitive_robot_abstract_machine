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

Code: `causal_query.py` (`run_chlorine_count_backdoor_adjustment`), `dataset.py`.
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

## Why chlorine count?

Not because chlorine is expected to be the main driver of mutagenicity here -- the
QSAR literature this dataset comes from already points to `ind1` as the established
predictor, and nothing below overturns that. Chlorine count is the interesting choice
for a different reason: it doesn't exist as a variable until a query is grounded. It's
an aggregate on "how many chlorine atoms does this molecule have" which is computed over each
molecule's `atoms`, the exchangeable relation `RelationalProbabilisticCircuit` grounds
per query. A flat `CausalCircuit` can register any variable that's already sitting in
its data as a cause; this experiment is here to check whether the same pipeline works
once the cause has to be *assembled* from a relation first. Chlorine happens to also be
rare enough (11 of 188 molecules have any) to stress-test that assembly at the edges,
where most of the interesting failure modes live.

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


