## Branch: claude/orm-interface-deduplication-uczwj4

**Goal**: `scripts/regenerate_all_orm.py` spawned one subprocess per package, so every
package in the dependency chain was imported once per generator. Run all generators in
one interpreter instead, so each import is paid for once.

**Plan / status**
- [x] Run each generator with `runpy` in the current interpreter instead of `subprocess`.
- [x] Reload a freshly generated interface module: scanning a package imports the empty
      placeholder, which the next generator would otherwise read.
- [x] Keep a generator's root-logger configuration from leaking into the next one.
- [x] Reorder to sdt -> giskardpy -> segmind -> coraplex -> experiments: ORMatic collects
      alternative mappings from all imported subclasses, so segmind (which declares no
      interface dependency) must be generated before coraplex/experiments define theirs.
- [x] Declare each package's ORM dependencies as data on `OrmPackage`.
- [x] Tests in `test/orm_generation_test` (new `lib: orm_generation` CI matrix entry).

**Measured**: CI's "Build ORM" step (four jobs, each running the whole script) went from
a mean of 104.5 s on main (run 32138086038: 108/107/99/104 s) to 74.3 s on the PR
(run 32500231779: 67/65/73/92 s) - about 30 s, ~29 %, per invocation. One CI run per
side, four samples of the same workload each; the new spread is wide (65-92 s), and the
runs are three days apart on the same image tag.

**Not verified here**: the container has none of the workspace dependencies installed, so
the regeneration could not be run locally and its output could not be diffed. CI's
giskardpy/coraplex/sdt/experiments jobs regenerate and then exercise the interfaces, and
all pass on this branch.

**PR**: #187 (draft) - https://github.com/AbdelrhmanBassiouny/cognitive_robot_abstract_machine/pull/187

**Next**: nothing outstanding. Not subscribed to PR activity (per notes).
