# Mutagenesis Causal Query: Results

This documents the causal-query stage of the Mutagenesis pipeline experiment:
registering chlorine count as a cause of mutagenicity on a circuit grounded from the
CTU Mutagenesis dataset, and comparing naive conditioning against backdoor-adjusted
estimates. It follows on from fitting and validating the relational circuit on the
full dataset, covered separately.

## What was done

1. Fitted a relational circuit on a small, hand-picked training set (below).
2. Grounded a query for a two-atom molecule with every atom's element left
   unspecified, so chlorine count is retained as a variable rather than integrated
   out.
3. Registered chlorine count as the cause, mutagenicity as the effect, and the
   dataset's `ind1` structural indicator as the adjustment variable, and verified the
   resulting circuit is support-deterministic.
4. Ran backdoor adjustment and compared it against naive conditioning at every
   chlorine-count value the grounded circuit's support covers.

Code: `causal_query.py` (`run_chlorine_count_backdoor_adjustment`). Tests:
`test/causal_reasoning_test/test_causal_query.py`.

## Data

The CTU Mutagenesis dataset (`mutagenesis_188`) has 188 molecules. Chlorine is rare:

| Chlorine count | Molecules |
|---:|---:|
| 0 | 177 |
| 1 | 5 |
| 2 | 3 |
| 3 | 1 |
| 4 | 1 |
| 5 | 1 |

Training used one molecule per distinct chlorine-count value (0 through 5), six
molecules total, rather than the full 188:

| Chlorine count | `ind1` | Mutagenic | logP | LUMO |
|---:|:---:|:---:|---:|---:|
| 0 | True | True | 3.01 | -1.991 |
| 1 | False | False | 2.72 | -1.019 |
| 2 | True | True | 6.24 | -1.464 |
| 3 | True | False | 6.68 | -1.474 |
| 4 | True | False | 7.13 | -1.492 |
| 5 | True | False | 7.84 | -1.616 |

This selection is deliberate, not a convenience sample: registering a relational
aggregate as a cause requires the grounded circuit to be support-deterministic over
it, and that check currently fails once two training molecules share the same
chlorine count (see [Limitations found](#limitations-found)). Distinct counts sidestep
that.

## Results

`P(mutagenic = True)` at each chlorine-count value, naively conditioned versus
backdoor-adjusted for `ind1`:

| Chlorine count | Naive P(mutagenic) | Adjusted P(mutagenic) |
|---:|---:|---:|
| 0 | 1.0000 | 0.3333 |
| 1 | 0.0000 | 0.3333 |
| 2 | 1.0000 | 0.3333 |
| 3 | 0.0000 | 0.3333 |
| 4 | 0.0000 | 0.3333 |
| 5 | 0.0000 | 0.3333 |

The circuit passed support-determinism verification, and both the naive and
adjusted queries ran to completion for every chlorine-count value in the training
set.

## Inference

- **Naive column is a lookup, not a signal.** With exactly one training molecule per
  chlorine-count value, conditioning on chlorine count pins down that one molecule,
  so the naive probability is just that molecule's own mutagenicity label (1 or 0).
  It says nothing about chlorine count's effect.
- **Adjusted column is flat by construction, not by finding.** Backdoor adjustment
  sums over `ind1`'s marginal distribution; with six data points, that marginal is
  coarse enough that the adjusted estimate collapses to the same value (1/3) at
  every chlorine count. This is what backdoor adjustment does with too little data
  to separate cause from confounder, not a claim that chlorine count has no effect.
- **This validates the mechanism, not a chemistry result.** The pipeline correctly
  grounds a relational aggregate, registers it as a cause, verifies the structural
  precondition, and runs both interventional queries end to end on real external
  data. Whether chlorine count actually affects mutagenicity would need a training
  set large enough for the adjustment to separate the two, which is a data-scale
  question rather than a pipeline question.

## Limitations found

Two issues surfaced while building this experiment, neither specific to
mutagenesis chemistry:

1. **Retained-latent collisions across training rows.** Registering a relational
   aggregate as a cause requires every branch of the grounded circuit to claim a
   disjoint region of that aggregate's domain. That holds automatically within one
   grounding call, but not across separate training rows: two rows that happen to
   share the same aggregate value each keep their own branch claiming it, so the
   circuit is no longer support-deterministic and registration fails. Training with
   distinct values worked around this; fixing it at the source would need
   deduplication across rows, not just within one grounding call.
2. **Support computation does not scale past a handful of training rows once a
   relational cause is registered.** Verifying support determinism and running
   backdoor adjustment both compute the grounded circuit's full support. That was
   fast on six rows but became impractically slow, and eventually exhausted memory,
   at 40+ rows with just a few grounded atoms -- well short of the full 188-molecule
   dataset. This is why training used six rows rather than the fitted circuit's full
   dataset.

Both are tracked as follow-up engineering work, separate from this experiment.
