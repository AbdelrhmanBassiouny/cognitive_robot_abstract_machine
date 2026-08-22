# D-core-aid (#63) — resolve round, 2026-08-22

## Done (round 1)
- **#161 widened** — finishes the two renames it had missed, incl. two production-source
  readers (`condition_resolver.py:11`, `:230`). Retitled, body rewritten.
- **#63 narrowed to `aid.py` alone** (`df20e7d9`) — 1 file, 49 lines.
- **#189 opened** — the `test_rdr_alchemy.py` flaky skip off main.
- Threads: 3 rename threads replied + left open; `test_aid.py` thread replied + resolved.
- Manifest notes, roadmap §23, dashboard, #94 comment `5379912760`.

## Done (round 2 — the follow-up review)
- **New `# %%` thread** (`r3835877307`): replied. The file on this branch is byte-identical
  to main, so it is not in #63's diff at all; what looks like a regression is only visible in
  `df20e7d9`'s own commit diff. #161 lands the conversion with corrected names and merges
  clean here. Left open, with an explicit offer to move it back if wanted.
- **Flaky-skip thread**: the developer asked then self-answered ("not flaky anymore") and
  resolved it. No action.
- **CI was red on `test_each_lib (semantic_digital_twin)`** — `test_multi_sim.py::
  test_world_sim_state_sync`, a physics-settling assertion #63's 49 krrood lines cannot
  reach. Root cause: this branch was **10 commits behind main** and predated `a7c21ffe6`
  ("[FlakySync] add flaky to test_world_sim_state_sync"). Merged main into both #63
  (`8c041a10`) and #161 (`d0df7534`); both re-verified locally (test_eql_rdr 45/45,
  test_eql 1179 passed / 3 skipped / 0 failed) and pushed. CI re-running.

## Outstanding (developer's)
- **`@pytest.mark.flaky` looks inert.** It appears exactly once in the repo, is not
  registered in `pytest.ini`'s `markers`, no rerun plugin is declared anywhere, and CI runs
  bare `pytest -n auto` with no `--reruns`. Under either `pytest-rerunfailures` or `flaky`,
  a bare marker with no reruns configured does nothing. If it is meant to suppress this
  failure, it needs the plugin declared, the marker registered, and `--reruns N`.
- **#189**: marked ready by the developer, so this session's job on it ended. Note it uses
  `@unittest.skip`, which disables the test; the repo's own newer idiom is
  `@pytest.mark.flaky`, which keeps coverage — worth considering if that marker is fixed.
- 3 open rename threads on #63 are yours to close.
- The dashboard's `D-ui-rendering` deferred-dependency drift rule exists in published output
  but not in `build_dashboard.py` on main.

## Next
Nothing for this session. CI in flight on #63 and #161; no check-in armed.
