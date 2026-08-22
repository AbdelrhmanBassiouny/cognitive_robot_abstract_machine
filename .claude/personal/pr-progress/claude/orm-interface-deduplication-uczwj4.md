## Branch: claude/orm-interface-deduplication-uczwj4

**Goal**: the ORM build started one subprocess per generator, so every package of the
dependency chain was imported once per generator. Build them all in one interpreter.

**Base**: first written on the fork's main (90c24116), which is 86 commits behind
cram2/main and predates the ORM build rework. Rebuilt on cram2/main (3f643cff) after
the user pointed this out. Lesson: check the upstream remote before starting, not only
`origin`.

**Plan / status**
- [x] Run all generators in ONE child process (`cognitive_robot_abstract_machine/
      orm_generation.py`, `python -P -m ...`), not one per generator. A child rather
      than the caller's interpreter, because the conftests build interfaces and
      importing every package into the pytest process would change what tests see.
- [x] `importlib.invalidate_caches()` after each generator (interfaces are deleted
      before a build, so each writes a file its folder was scanned without).
- [x] Restore root logging around each generator.
- [x] Reorder to sdt -> giskardpy -> segmind -> coraplex -> experiments.
- [x] Declare each interface's dependencies as data on `OrmInterface`.
- [x] Failure names the package whose interface is missing (fixes --debug blame).
- [x] Tests in `test/cognitive_robot_abstract_machine_test` (existing CI matrix entry,
      no new job). 36 pass locally.

**Local test loop**: `PYTHONPATH="$PWD/krrood/src:$PWD" python -m pytest
test/cognitive_robot_abstract_machine_test --confcutdir=test/cognitive_robot_abstract_machine_test`
(the root test/conftest.py needs the full workspace, which the container lacks).

**Measurement** (clean, same base commit both sides, n=7, 13 min apart): the
examples-and-demos "Build ORM" step went 102.0 s -> 68.3 s mean (main run 32567616992
vs PR run 32567072596), about 34 s / 33 %. Spread narrowed from 80-120 s to 64-79 s.

**PR**: #187 (draft), base main = cram2/main (3f643cff), 2 commits / 7 files.
GitHub kept a stale merge base after the fast-forward (showed 88 commits) until the
PR's base was re-set to main via the API, which forced it to recompute.

**Review round 1** (commit 783a62ab): import-at-top RESOLVED; return docstrings
RESOLVED; "can't this be done by importing?" for alternative-mapping detection LEFT
OPEN (answered differently - replied with the cost of importing all five packages plus
a ~70 s build, improved the AST reading instead, offered to switch).

**Review round 2** (commit ed9f4984):
- [x] clearer names in alternative_mapping_class_names (was alternative_mappings):
      base_class_name, base_class_names_by_class_name, known_mapping_names,
      newly_found_mapping_names. RESOLVED.
- [x] split the compound if into named subconditions (is_known_mapping /
      inherits_a_mapping) and seeded the search with ALTERNATIVE_MAPPING itself.
      RESOLVED.
- [ ] "discuss with me the cleanest option" for the shared_dependency import in the
      dataset generator - DISCUSSION, no code pushed. Posted four options; recommended
      dropping the shared module and recording os.getpid() instead (one process implies
      one sys.modules, so it is sufficient evidence and removes the sys.path line, the
      extra dataset file and the per-package copy). Runner-up: revert to the deferred
      import with one copy at the checkout root. Waiting on the user's pick.

**Note**: test_generation_order's ast.parse needs 3.12 - coraplex/robot_plans/actions/
base.py uses PEP 695 `type X[T] = ...`. Local container is 3.11, so a local run only
passes because `and` short-circuits before coraplex is scanned. CI is 3.12.

**Next**: two threads waiting on the user - the AST-vs-importing question (round 1)
and the shared_dependency import discussion (round 2, recommendation posted).
Not subscribed to PR activity (per notes).
