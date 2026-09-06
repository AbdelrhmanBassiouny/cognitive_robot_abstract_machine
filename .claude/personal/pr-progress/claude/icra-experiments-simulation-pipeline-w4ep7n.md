# #265 - icra-foundation / integrated-simulation-pipeline

Resolving why the branch was red, via /plan-item-resolve (auto mode).

## What was wrong

CI had never been green. Ten of twenty-three checks failed on one root cause,
all of it this branch's own - main is green at the same base f6a53cf9. Every
job that builds the workspace ORM interfaces died in generation:
`CouldNotResolveType` on `experiments.montessori.perception.detector_choice.SurfacePass`,
"type 'Sequence' is not subscriptable", before any test ran. The jobs that
passed are the ones whose conftest never builds an interface.

Cause: `WrappedField._build_initial_namespace` offers every class in the class
diagram by bare name as a *local* scope, and a local scope beats the module the
annotation was written in - so giskardpy's `Sequence` goal replaced the typing
alias `detector_choice.py` imports.

## Done

- Reproduced the generator's failure locally over three classes and no ROS, as
  a krrood test (`test_type_resolution_with_a_colliding_class_name.py`, with two
  dataset mimics). Fails on the parent with CI's exact error.
- Fixed `krrood.class_diagrams.utils.get_type_hints_of_object`: the offered
  namespace now fills only the gaps the defining modules leave.
  `names_bound_by_the_defining_modules` is what it filters against.
- Pushed as f5c383a8. PR description updated (new "domain class named like a
  typing alias" paragraph, and Verification now says CI has never got past the
  generation). PR stays a draft.
- Recorded in the plan: the CI blocker (found state, then the fix), the
  appended item note, the roadmap section "The generator's name collision,
  2026-09-06", and a standing hazard bullet.

## Next

- Watch the CI run on f5c383a8. The generation aborted before collection every
  time so far, so whatever the suites say about the convergence is unproven -
  expect further failures behind this wall, and they will be real.
- Nothing in this container can run the ORM generation (`random_events` needs a
  C++ library, the generator walks giskardpy/ROS), so CI is the only proof.
- Still open on the item, untouched here: the unbounded
  `SimulationTimePacer.sleep()`, and the two calls #265 leaves to the developer
  (the stale hole-direction measurements in `test_montessori_search_narrowing.py`,
  and whether `EdgeFitDetector`/`ColorBlobDetector` collapse into one).
