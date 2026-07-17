# PR plan: D-store — RDRFileStore (Wave 0, S2a)

Storage half of the @rdr decorator path, split out of the original D-deco
so each concern reviews on its own. Base: `D-ui` (#76). PR: #80 (draft).

## Scope

- `rdr/file_store.py` — RDRFileStore: path resolution (`_rdr_models/` for
  relative names, absolute used as-is) + model-file lifecycle
  (exists / load_case_type / save), delegating to save_rdr_with_case and
  load_module_from_path.
- `test_rdr_file_store.py` — path resolution, existence, save, and the
  load_case_type + classify round-trip via FunctionCaseGenerator +
  EQLSingleClassRDR. No decorator dependency (genuinely standalone).

## Stack

main … D-core-engine (#68) → D-ui (#76) → **D-store (#80)** → D-deco (#77)

## Status

- DONE: cut off origin/D-ui (a7eb3703), commit 0c4938d3, pushed, draft
  PR #80 open with session link, subscribed to activity.
- test_rdr_file_store.py: 21 passed on this branch.

## Next

- Babysit #80 until merged/closed. Merges before #77.
