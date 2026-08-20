## claude/fix-ci-failing-tests-202965 -> PR #183 (draft, `bug`)

**Shipped.** krrood's import-scope builder aborted the whole scope when one
from-import named an unimportable module, while already tolerating a missing
*name*. Two commits:
- `a4990cfe` fix + unit test (`test_get_scope_from_imports.py`)
- `a2385ec0` full-recovery regression test
  (`test_type_resolution_with_unimportable_import.py`)

**Full chain (verified by code, not guessed).** Every mapped datastructure
descends from `Symbol`, whose `_inference_explanation_` is annotated with a
TYPE_CHECKING-only `InferenceExplanation` -> resolving any of them raises
NameError -> hierarchy search builds each module's scope -> SDT's
`world_synchronizer.py` / `procthor_parser.py` hold *function-local*
`from semantic_digital_twin.orm.ormatic_interface import WorldMappingDAO`,
which `ast.walk` visits like any other import -> module absent during
generation -> search died before reaching `Symbol`. All 10 red jobs on #169
share this one cause.

**Verified.** Whole collectible krrood suite: zero newly broken, 9 newly
passing. Local-only failures are env: robotics deps, and
`make_dataclass(module=...)` needing 3.12 (container has 3.11).

## ORM interface design: evidence gathered (awaiting user's decision)

Ran real-git experiments in scratchpad (`orm_experiment/`). Findings:

- **Design A (tracked-empty, main) fails every branch switch that moves the
  interface path**: to a branch that ignores it, to one with different content,
  to one adding a mapped package. **skip-worktree does not help** - it only
  hides the file from `git status`/`git add`, so the checkout still fails but
  now nothing explains why. Worst failure mode of the lot.
- Design A without skip-worktree: dirty tree, `git add -A` stages generated
  content, and `git stash` *loses* it.
- **Design B (ignored, #169) passes all of them**, keeps generated content.
- Import diagnostics are poor under both: A gives `ImportError: cannot import
  name ...` (reads like a typo), B gives `ModuleNotFoundError`. Neither names
  the generator.
- Tested a package `__getattr__` shim to make B self-explaining: **only
  intercepts `from pkg.orm import ormatic_interface`**, not the dotted form the
  codebase actually uses. So prettifying the failure does not work; bootstrap
  before running is the real answer.
- Both designs silently keep a **stale** interface across a branch switch;
  `are_generated` checks existence only. Shared hole, unsolved by either.
- #169 deletes 113 lines of guard machinery (empty_generated 41 +
  protect_generated 60 + pre-commit 12) and a whole AGENTS.md rule paragraph.

**Recommendation given to user:** adopt B, plus (1) #183 (done), (2) wire
`ensure_generated()` into `test/conftest.py` - #169 wires it into
`run_montessori_demo.sh` and docs but *not* pytest, (3) add a freshness check
so a stale interface is rebuilt rather than silently used.

**Next.** Waiting on the user's choice before implementing (2) and (3). Not
subscribed to any PR; no check-ins armed.
