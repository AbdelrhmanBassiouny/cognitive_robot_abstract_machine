# PR #33 — P4: migrate semantic_digital_twin predicates off the framework

Plan item `p4-sdt-migration` of plan `eql-verbalization`. Branch
`eql-symbolic-function-sdt` (base `main`), draft. This session resumed it after
P1/P2/P3 (#86/#87/#88) all merged to `main`.

## Plan (5 steps, from the approved plan-mode plan)

1. Merge `main` in, dropping the duplicated surface-verification framework. **done**
2. Rebuild the sdt snapshot on the generated-results pattern. **done**
3. Apply the review's wording decisions. **done**
4. Regenerate, format, run the suites. **done** (with one caveat, below)
5. Reply to and resolve the 36 review threads; refresh the PR description. **in progress**

## Done (3 commits, pushed)

- `29bba2c6` merge `main` (605 commits behind). 5 conflicts resolved as planned;
  reverted the branch's docformatter-only reflow of `exceptions.py`,
  `verbalizer.py` and coraplex `transporting.py` so the diff carries only P4.
  Replaced the branch's mid-method `SymbolicCallable` import in `ORMatic` with an
  `ignored_base_classes` parameter (+ 2 tests in
  `test/krrood_test/test_ormatic/test_base_class_exclusion.py`); sdt's
  `generate_orm.py` passes it and dropped its hand-written `ContainsType` entry.
- `c5d6ff12` snapshot: deleted the hand-written `SURFACES` tuple and its
  three-assert test, wired `regenerate_verbalization_results` into sdt's
  `conftest.py`, kept one non-vacuous test (every callable declares its own
  fragment — neither of the two framework asserts can see a fragment-less class).
- `16bca6d2` all wordings from the review + the no-abbreviation sweep. Added
  `phrase()` to krrood as the value counterpart of `clause()` (+ 4 tests) because
  several wordings name the value with a phrase of its own, which neither
  `FunctionVerbalizationTemplates` method covers, and raw fragments in domain code
  are what the reviewer rejected.

Suites: krrood 2046 passed / 2 failed (`test_object_diagram.py`, fails identically
without these changes). sdt `test_predicates.py` 8 passed / 10 fixture errors, all
needing ROS packages absent locally — same before and after.

## Open, needs the user

1. **"a Point3" → "a point"** (the type-name-vs-field-name thread and ~9 "same
   comment" repeats). P2 shipped the *opposite* precedence to what roadmap
   decision 1 records: `operand_head_noun` gives the type noun priority and reads
   the field name only when the type is uninformative (`object`), documented
   deliberately with a citation. So this needs a *type-level* display noun in
   krrood — new plan item — or accept "a Point3". Cannot be done in P4.
2. **`Pose` vs `HomogeneousTransformationMatrix`** (`Reachable.pose`,
   `BlockingBodies.pose`). Investigated: `Pose` is a *sibling* of
   `HomogeneousTransformationMatrix`, not a subclass, and
   `compute_inverse_kinematics(target=...)` is typed for the matrix. Switching the
   hint alone would misdeclare the contract; widening the IK chain is outside P4.
   Kept the matrix — the reviewer's expected sentence presumed the change.
3. **sdt `ormatic_interface.py` not regenerated.** `ignored_base_classes` removes
   10 predicate DAOs (`AboveDAO`, `LeftOfDAO`, the spatial-relation bases, …), but
   regenerating locally also *drops every ROS-derived DAO* because `rclpy` /
   `geometry_msgs` are absent, so the local output is wrong. CI regenerates it
   before tests, so nothing breaks; the committed copy stays stale until someone
   regenerates it with ROS available.

## Noticed, not P4's business

- Running krrood's suite on a clean `main` rewrites
  `test/krrood_test/.../verbalization_results.py` (import order + `tuple`→`Tuple`):
  the committed copy does not match a fresh generation.
- `AllClose` renders "a ndarray" — the determiner pass picks the article from
  spelling, so an initial-consonant-letter/vowel-sound noun gets "a".
- `VerbalizationResultsOfPackage`'s class docstring still says "the three
  ``assert_*`` methods"; there are two.

## Next

- Reply to and resolve the review threads (resolve only where genuinely done;
  reply-without-resolving on the two open questions above).
- Refresh #33's description, keep it draft, set `plan.yaml` status.
