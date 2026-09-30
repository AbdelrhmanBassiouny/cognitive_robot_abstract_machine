# rdr-world saved-model fixture (PR #251, `bug`, `in-review` as cram2#653)

Branch `claude/rdr-world-saved-model-fixture` off `main`. Not a plan item: the second root
cause found while diagnosing `match-query-ergonomics`' CI red on #248; referenced as the fix
in `match-query-ergonomics` and `knowledge-directed-requests` (perception-backend blockers).

## The bug
`test_draw_evaluated_tree_for_drawer_cabinet_rdr` loaded the model
`test_save_and_load_drawer_cabinet_rdr` writes; that output is untracked, so under CI's
`pytest -n auto` the reader can run before the writer.

## Done
1. Reproduced on `main` from a clean state (`RDRLoadError`).
2. `saved_drawer_cabinet_rdr` fixture writes into a directory named after the requesting
   test; both tests read it; the reader stops naming `"world_rdr"`.
3. Promoted upstream as cram2#653. LucaKro approved; tomsch420 requested changes with one
   thread on `conftest.py:189` (`directory: str`), text: "path".
4. 2026-09-30 (session_01AeV6SN95muCLAZKJTRWHNH): answered it in a2b48c4d8 -
   `SavedRDRModel.directory` is a `pathlib.Path`, built with pathlib, `str()` only at
   `GeneralRDR.save`/`load` (which concatenate `save_dir + "/__init__.py"`). Read as "make
   it a Path"; the one-word comment could also mean rename to `path` or use pytest's
   `tmp_path` - not asked back, since upstream replies are the developer's.
   `test_rdr_world` under `-n 4` from clean: 8 passed, 1 skipped, 3/3.

## Outstanding
- Reply on cram2#653's thread (developer only - AGENTS.md forbids us posting upstream)
  and re-request tomsch420.
- krrood red on d27c920 was a casadi segfault in main's `test_thread_safety.py`
  (cram2#603's test); also hit integration-20260930-014913; 30/30 locally. Not ours.
- `integration-conflict` label (2026-09-30 16:36 refresh) is a misattribution: this
  branch was in none of that refresh's builds, and the tooling suite it runs passes with
  the branch merged. Left in place for the developer; four other branches (64, 65, 226,
  248) were blocked the same way in that run.
