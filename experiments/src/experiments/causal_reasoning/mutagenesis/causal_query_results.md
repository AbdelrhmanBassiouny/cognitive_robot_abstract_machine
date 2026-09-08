# Mutagenesis Causal Query: Results

This experiment uses a relational causal circuit on the CTU Mutagenesis dataset. We
take the 188-molecule dataset, register aromatic-bond count as a cause of
mutagenicity on a circuit grounded from it, and ask what backdoor adjustment says
once we control for the dataset's known `ind1` indicator. It follows on from fitting
and validating the relational circuit on the full dataset (covered separately), and
it runs on the whole dataset without subsampling.

## What we did

1. Fit a relational circuit on all 188 molecules, with the class circuit stratified by
   aromatic-bond count so it is support-deterministic over that variable.
2. Grounded a query for a two-atom molecule with every atom's element left
   unspecified, so aromatic-bond count stays a variable instead of being integrated
   out.
3. Registered aromatic-bond count as the cause, mutagenicity as the effect, and
   `ind1` as the adjustment variable, trimmed the circuit to just those three, and
   verified the result is support-deterministic.
4. Ran backdoor adjustment and compared it against naive conditioning at every
   aromatic-bond-count value the grounded circuit's support covers.

Code: `causal_query.py` (`AromaticBondCountCausalQuery.run`), `dataset.py`.
Tests: `test/causal_reasoning_test/test_causal_query.py`.

## The data

Every one of the 188 molecules has at least one aromatic bond, and the count spans a
wide range:

| Aromatic bonds | Molecules | Share |
|---:|---:|---:|
| 5 | 1 | 0.5% |
| 6 | 32 | 17.0% |
| 10 | 11 | 5.9% |
| 11 | 17 | 9.0% |
| 12 | 60 | 31.9% |
| 14 | 3 | 1.6% |
| 15 | 4 | 2.1% |
| 16 | 7 | 3.7% |
| 17 | 16 | 8.5% |
| 18 | 1 | 0.5% |
| 19 | 21 | 11.2% |
| 21 | 1 | 0.5% |
| 22 | 1 | 0.5% |
| 24 | 10 | 5.3% |
| 26 | 2 | 1.1% |
| 30 | 1 | 0.5% |

## Why aromatic-bond count?

Aromatic-bond count is present in every molecule and ranges from 5 to 30 across the
dataset, so grounding retains a variable with real spread rather than one that is
mostly a single dominant value. It also splits cleanly by mutagenicity: molecules
that go on to test mutagenic average 15.3 aromatic bonds, non-mutagenic ones average
9.1. Aromatic ring systems, especially fused polycyclic ones, are a textbook
structural alert for genotoxicity in the mutagenesis QSAR literature, so this is not
just a number that happens to correlate. The results below back that up: naive
P(mutagenic) climbs steadily from 0 at the lowest aromatic counts to 1 at the
highest.

## Why not ground this analytically instead?

`GroundingMode.EXACT` grounds by enumerating the fitted circuit's own exact partition
over the cause variable instead of Monte Carlo sampling, but only when that partition
is already disjoint on its own; otherwise it logs a warning and falls back to
`GroundingMode.SAMPLED`. That precondition does not hold for aromatic-bond count on
this dataset: it is not, today, a split the induced tree makes on its own. `EXACT`
grounding is not reachable yet for this experiment. `SAMPLED` grounding is not a
fallback chosen over a working alternative; it is the mode that runs to completion
here.

## Results

`P(mutagenic = True)` at each aromatic-bond-count value, naive versus
backdoor-adjusted for `ind1`, on the full dataset:

| Aromatic bonds | Region P(aromatic bonds) | Naive P(mutagenic) | Adjusted P(mutagenic) |
|---:|---:|---:|---:|
| 5 | 0.0053 | 0.0000 | 0.0000 |
| 6 | 0.1702 | 0.2188 | 0.2188 |
| 10 | 0.0585 | 0.2727 | 0.2727 |
| 11 | 0.0904 | 0.3529 | 0.6684 |
| 12 | 0.3191 | 0.7000 | 0.6921 |
| 14 | 0.0160 | 1.0000 | 1.0000 |
| 15 | 0.0213 | 1.0000 | 1.0000 |
| 16 | 0.0372 | 1.0000 | 1.0000 |
| 17 | 0.0851 | 1.0000 | 1.0000 |
| 18 | 0.0053 | 1.0000 | 1.0000 |
| 19 | 0.1117 | 1.0000 | 1.0000 |
| 21 | 0.0053 | 1.0000 | 1.0000 |
| 22 | 0.0053 | 1.0000 | 1.0000 |
| 24 | 0.0532 | 1.0000 | 1.0000 |
| 26 | 0.0106 | 1.0000 | 1.0000 |
| 30 | 0.0053 | 1.0000 | 1.0000 |

The region probabilities match the dataset's own aromatic-bond-count distribution
exactly, so grounding is retaining the real population, not something a Monte Carlo
artifact would produce. The circuit passes support-determinism verification, and the
whole thing runs end to end in well under a minute.

## Inference

* **Naive P(mutagenic) rises steadily with aromatic-bond count, and it is not a small
  effect.** It starts at 0 for the one molecule with just 5 aromatic bonds, sits
  around 0.22 to 0.35 through the low-to-middle range, crosses 0.5 at 12 bonds, and
  reaches a flat 1.0 for every value of 14 or above. This tracks real chemistry: more
  aromatic ring structure is a known driver of mutagenic activity in this dataset's
  literature, and the circuit picked that signal up directly from the data.
* **Adjusting for `ind1` barely moves most values, but it matters where it does.** At
  6, 10, 14 and up, naive and adjusted probabilities agree almost exactly, meaning
  `ind1` is not doing much confounding work there. At 11 aromatic bonds the picture
  changes: naive says 0.35 but adjusted says 0.67, because the low-`ind1` molecules at
  that count are pulling the naive number down, and adjustment corrects for that.
* **The values at 14 and above are a flat wall of 1.0, and that deserves a caution,
  not a headline.** Several of those aromatic-bond-count values are supported by only
  one or two molecules in this dataset (18, 21, 22 and 30 all have exactly one), so a
  flat 1.0 there is a small sample reporting itself accurately, not a discovered law.
  The steady climb from 5 through 12, backed by much larger groups (32, 60, 21
  molecules respectively), is the part of this result worth trusting.
* **This does not prove aromatic-bond count causes mutagenicity.** The backdoor
  criterion only tells you the adjustment is arithmetically sound given `ind1` as the
  full confounder set; it cannot tell you whether `ind1` actually is the full
  confounder set for aromatic-bond count in this domain, because nothing here
  constructs or checks the underlying causal graph, and that is an assumption we are
  bringing in, not one the circuit verifies. Read this as the causal-circuit machinery
  running correctly on real, structured relational data and turning up a real,
  chemically plausible signal, not as a finished causal claim.

## What would make this more interesting

The next natural step is to register `ind1` itself as the cause, run the same
backdoor machinery, and see whether the analytic answer to "why is a molecule
mutagenic" lines up with what the literature already says about `ind1`, ideally
alongside a comparison against a plain classifier's held-out accuracy on the same
data. We are not doing that here: `ind1` is a flat field on the molecule, not an
aggregate that grounding has to assemble from a relation, so registering it as the
cause would not exercise the relational-grounding pipeline this experiment exists to
validate. That is a different, also useful, experiment, and it deserves to be built
and judged on its own terms rather than folded into this one.
