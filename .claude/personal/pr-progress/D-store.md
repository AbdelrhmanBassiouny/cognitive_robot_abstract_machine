## D-store (#80) — RDRFileStore, resolved 2026-08-31

`/plan-item-resolve rdr-interface-and-decorator D-store`, auto mode.

### What was wrong

Head unmoved since 2026-07-19, on `D-ui`'s pre-rebuild tip `c50d2109`, so it
carried #78's `cfe32ad0`. Three maintenance passes hit ~39 conflicts and
skipped it; `needs-resolution` label. Last CI red. None of it on the item.

### Done

- Recorded the three blockers on the item before starting.
- Reset onto `D-ui` and replayed the slice; #80 is 417 additions / 5 files,
  down from 14,994 / 47. Restacked again onto `1045c6d5a` mid-session.
- `RDRFileStore` is a `ModelSaver`; `ModelFileMissing` replaces a bare
  `FileNotFoundError`; 16 tests, TDD.
- Two base-side defects the slice surfaced: template `if TYPE_CHECKING:` with
  no body (→ #226 off `main`, ported here) and `save_rdr_with_case`'s
  `base_class` (#66's line, applied here at the developer's direction).
- 548 passed / 2 skipped vs 532 / 2 on the base, Python 3.12.
- Manifest, roadmap sections 11-12, issue #94 comment, both PR descriptions.

### Next

Nothing owed on #80 by this session. Outstanding for whoever picks it up:

- **#226 needs review** and, once merged, its port here becomes a no-op.
- **`D-deco` (#77) still sits on `D-store`'s pre-rebuild history** and needs
  the same reset.
- **`validate_annotations` raises on Python 3.10/3.11** (`StrEnum` value
  containment); recorded in the roadmap's Open section, not fixed.
- **CI has still never run green on `D-store`** — all figures are local.
