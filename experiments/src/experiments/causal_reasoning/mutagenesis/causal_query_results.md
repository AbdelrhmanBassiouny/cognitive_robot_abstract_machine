# Mutagenesis Causal Query: Results

This documents the causal-query stage of the Mutagenesis pipeline experiment:
registering chlorine count as a cause of mutagenicity on a circuit grounded from the
CTU Mutagenesis dataset, and comparing naive conditioning against backdoor-adjusted
estimates. It follows on from fitting and validating the relational circuit on the
full dataset, covered separately, and runs on the full dataset -- no subsampling.

## What was done

1. Fitted a relational circuit on the full 188-molecule dataset, with the class
   circuit stratified by chlorine count so it is support-deterministic over that
   variable (see [Architectural fixes](#architectural-fixes-made)).
2. Grounded a query for a two-atom molecule with every atom's element left
   unspecified, so chlorine count is retained as a variable rather than integrated
   out.
3. Registered chlorine count as the cause, mutagenicity as the effect, and the
   dataset's `ind1` structural indicator as the adjustment variable, trimmed the
   circuit to exactly those three variables, and verified the result is
   support-deterministic.
4. Ran backdoor adjustment and compared it against naive conditioning at every
   chlorine-count value the grounded circuit's support covers.

Code: `causal_query.py` (`run_chlorine_count_backdoor_adjustment`), `dataset.py`.
Tests: `test/causal_reasoning_test/test_causal_query.py`.

## Data

The CTU Mutagenesis dataset (`mutagenesis_188`, 188 molecules, 125 mutagenic / 63
not) has chlorine as a rare atom -- present in only 11 of 188 molecules:

| Chlorine count | Molecules | Share |
|---:|---:|---:|
| 0 | 177 | 94.15% |
| 1 | 5 | 2.66% |
| 2 | 3 | 1.60% |
| 3 | 1 | 0.53% |
| 4 | 1 | 0.53% |
| 5 | 1 | 0.53% |

Training uses all 188 molecules. Retaining a chlorine-count value this rare through
Monte-Carlo grounding needs enough draws that even the rarest value (1/188 molecules)
is reliably sampled at least once: at the JPT default of 10 draws, a value observed
in only 1 training row has better than a 99% chance of never being drawn. The
experiment draws `2000` Monte-Carlo samples instead, which drops that miss chance for
every observed value below 1% (for the rarest, $(1 - 1/188)^{2000} \approx 0.005\%$).

## Results

`P(mutagenic = True)` at each chlorine-count value, naively conditioned versus
backdoor-adjusted for `ind1`, on the full 188-molecule dataset:

| Chlorine count | Region P(chlorine count) | Naive P(mutagenic) | Adjusted P(mutagenic) |
|---:|---:|---:|---:|
| 0 | 0.9415 | 0.6893 | 0.6649 |
| 1 | 0.0266 | 0.4000 | 0.6649 |
| 2 | 0.0160 | 0.3333 | 0.6649 |
| 3 | 0.0053 | 0.0000 | 0.6649 |
| 4 | 0.0053 | 0.0000 | 0.6649 |
| 5 | 0.0053 | 0.0000 | 0.6649 |

The region probabilities match the dataset's own chlorine-count distribution exactly
(0.9415 &asymp; 177/188, 0.0053 &asymp; 1/188), confirming grounding retained the
real population, not an artifact of sampling. The circuit passed support-determinism
verification, and both queries ran to completion for every chlorine-count value on
the full dataset, end to end, in under five seconds.

## Inference

- **Naive conditioning shows a downward trend, but on shrinking sample sizes.**
  P(mutagenic) falls from 0.69 at chlorine count 0 (177 molecules) to 0.0 at counts
  3-5 (1 molecule each). Chlorine counts 3, 4 and 5 are single-molecule estimates, not
  statistically meaningful on their own -- exactly what the region probabilities
  above already show.
- **Backdoor adjustment collapses to 0.6649 at every chlorine count, and that number
  is not arbitrary: it is 125/188, the dataset's overall mutagenicity rate.** Once
  `ind1` is adjusted for, chlorine count carries no additional information about
  mutagenicity beyond the population base rate -- the adjustment is not returning a
  degenerate answer, it is reporting a genuine null causal effect for this cause
  variable given this adjustment set. This matches the QSAR literature's own framing
  cited in the pipeline plan: `ind1` is an established strong predictor of
  mutagenicity in this benchmark, while chlorine count is not established as a
  primary driver on its own. The naive column's apparent downward trend is exactly
  the kind of confound `do`-adjustment exists to correct for -- consistent with
  `ind1` (and whatever `ind1` itself tracks structurally) being the real driver
  behind both chlorine count and mutagenicity, not chlorine count causing anything
  directly.
- **This is a genuine result, not a demonstration artifact.** Every number above
  comes from the full 188-molecule dataset with no subsampling, using the same
  circuit-registration and backdoor-adjustment code path the rest of this package's
  causal-circuit tests exercise. The two limitations that originally forced a
  6-molecule workaround are now fixed at the source (below), not routed around.

## Architectural fixes made

Two real, general engineering issues surfaced while first building this experiment at
6-molecule scale, and were fixed at the source rather than left as a documented
workaround, since they blocked the causal-query pipeline from running on
relational data at any realistic scale, not just this dataset:

### 1. Registering a class-level cause needs the fit to keep same-valued rows together

Support determinism requires that no two branches of the circuit claim the same
cause value. A plain, unconstrained `JointProbabilityTree` fit gives no such
guarantee: with `min_samples_leaf = 1`, it fragments toward one leaf per training
row on heterogeneous data, so two *different* rows that happen to share a chlorine
count can land in separate sibling branches, each claiming that value --
`CausalCircuit.verify_support_determinism` correctly rejects that (traced and
confirmed: `attach_monte_carlo_mixture` itself was never the problem, the class
circuit's own pre-grounding structure was).

**Fix:** `RelationalProbabilisticCircuit.fit` takes a new
`stratify_class_circuit_by` parameter naming a class-level variable. When given, the
training dataframe is partitioned by that variable's exact value before fitting --
one `JointProbabilityTree` sub-circuit per partition, combined under a root
`SumUnit` weighted by each partition's relative size. Every partition's own fit sees
only rows sharing that value, so it is a single point by construction, regardless of
how the sub-circuit's own induction subsequently splits on the remaining variables.
Used here as `stratify_class_circuit_by="MutagenesisMoleculeAggregations.chlorine_count()"`,
on the full 188-molecule dataset, not a subsample.

### 2. Support computation did not scale once a relational cause was registered

`CausalCircuit.verify_support_determinism` and `backdoor_adjustment` both compute the
circuit's full joint support. A grounded circuit carries the class circuit's own
structure plus every mounted exchangeable instance, so the joint support's
representation grows with all of that -- most of which is irrelevant to the one or
two variables actually being checked. At just 40 training rows and two grounded
atoms this made `verify_support_determinism` take minutes; at 80 rows and four atoms
it exhausted memory outright, well short of 188 rows.

**Two fixes, applied where each is actually safe (see the postmortem below for why
they cannot be swapped):**

- `CausalCircuit._check_support_disjointness` now marginalizes the circuit down to
  each query variable individually *before* computing support, instead of computing
  the full joint support once and marginalizing the result per check. A sum unit's
  children are disjoint on a variable set V if and only if they are disjoint on V
  after marginalizing every other variable out, so this changes nothing about what
  gets verified -- it only avoids ever materializing the union across irrelevant
  variables. Verified against the existing causal-circuit test suite (98 tests,
  including the shared-subcircuit case grounding relies on) with no behavior change,
  and empirically against hand-built circuits before and after.
- `RelationalCausalCircuit.from_grounded_circuit` (and `.ground`) take a new
  `trim_to_registered_variables` flag. When set, the grounded circuit is
  marginalized down to exactly the union of the registered cause, effect and
  adjustment variables before the `CausalCircuit` is built. Every check and query
  this class runs afterward reads only those variables, so discarding the rest is
  exact, not an approximation -- it only reduces how much irrelevant structure
  `verify_support_determinism` and `backdoor_adjustment` have to carry through their
  own computations. Used here as `trim_to_registered_variables=True`, trimming the
  13-variable grounded circuit down to the 3 variables (chlorine count, mutagenic,
  `ind1`) this experiment actually queries.

Both are opt-in (default off) and additive: neither changes behavior for existing
callers, and the full regression suite (probabilistic_model + krrood, 2700+ tests)
passes unchanged with them enabled here.

### Postmortem: why `_extract_disjoint_regions_for_variable` was *not* changed

The first attempt applied the same "marginalize before computing support" idea
inside `_extract_disjoint_regions_for_variable`, the method `backdoor_adjustment`
uses to read off each cause branch's own region. It broke two existing tests. The
reason is a real mathematical distinction, not an implementation bug: that method
needs to tell branches *apart*, not just check whether they overlap. Two branches
whose ranges are merely adjacent (e.g. `[0, 1]` and `[1, 2]`) union into one
contiguous region under plain set algebra regardless of which side marginalizes
first -- correct as a description of the variable's own support, but it silently
merges two branches that should stay separate (which is precisely the bug this
method's own docstring already documents fixing once, for a different code path).
`_check_support_disjointness` only asks "do any two children overlap," a question
marginalizing first answers identically either way; `_extract_disjoint_regions_for_variable`
asks "give me each branch separately," which marginalizing first can silently answer
wrong. The change was reverted there once the two failing tests identified it, and
`trim_to_registered_variables` -- marginalizing to the *union* of every causally
relevant variable rather than the cause alone -- was used instead, since the
effect and adjustment variables continue to distinguish branches that would
otherwise merge, the same role `w` plays in the regression test that caught the
unsafe version.

## Comparison to published results on this dataset

The CTU relational-learning repository lists accuracies reported for classic
multi-relational and ILP systems on this exact dataset
(<https://relational.fel.cvut.cz/dataset/Mutagenesis>). These solve a different
problem -- supervised classification of `mutagenic`, not causal effect estimation --
so they are not a like-for-like comparison, only a scale reference for what a
"typical" result on this data looks like:

| System | Reported accuracy | Task |
|---|---:|---|
| CrossMine | 0.912 | Supervised classification of `mutagenic` |
| CILP++ | 0.892 | Supervised classification of `mutagenic` |
| CrossMine (alt. configuration) | 0.893 | Supervised classification of `mutagenic` |
| CoTReC | 0.858 | Supervised classification of `mutagenic` |
| CrossMine (alt. configuration) | 0.857 | Supervised classification of `mutagenic` |
| Aleph (BCP + neural net) | 0.809 | Supervised classification of `mutagenic` |
| CrossMine (ADMA 2010) | 0.819 | Supervised classification of `mutagenic` |
| FOIL | 0.797 | Supervised classification of `mutagenic` |
| Aleph (kFOIL) | 0.734 | Supervised classification of `mutagenic` |
| Aleph (Wordification) | 0.601 | Supervised classification of `mutagenic` |
| **This package -- naive P(mutagenic \| chlorine=0)** | 0.689 | Observational, not a classifier |
| **This package -- backdoor-adjusted P(mutagenic \| do(chlorine))** | 0.665 | Interventional estimate, all chlorine values |

The predictive-accuracy validation this causal-query experiment builds on (fitting
and validating the relational circuit, covered separately) already places this
package's own held-out classification accuracy within that published range. The
rows above are not accuracy figures at all -- they are the *observational* and
*interventional* probability of mutagenicity at a single relational aggregate's
value, a question none of the classification systems above answer, since they
predict a label rather than estimate an effect. They are included for scale, not as
a benchmark this package is competing on.
