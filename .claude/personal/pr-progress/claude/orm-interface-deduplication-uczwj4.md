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

**Not verified here**: the container has none of the workspace dependencies installed, so
the real regeneration could not be run. CI's giskardpy/coraplex/sdt/experiments jobs run
`regenerate_all_orm.py` and then exercise the generated interfaces, which is the check.

**Next**: nothing outstanding; no PR opened (not requested).
