# D-ui-rendering (PR #79) — `rdr-refactor` item `D-ui-rendering`

## What this branch is

`rdr/case_table.py` plus the seven shell-free RDR test modules — the presentation and
serialization coverage of the D-ui slice that needs no IPython shell. It is the middle of
the D-ui stack: `D-core-backend` (#210) → **#79** → #76 (`D-ui`).

## What was wrong, and what the resolution did

`/plan-item-resolve rdr-refactor D-ui-rendering`, 2026-08-30. The branch was based on
`D-ui-splice-fix`, whose PR #78 was closed unmerged on 2026-07-31, so it had no base that
could reach `main`. The re-target its manifest note prescribed — onto `D-core-engine`
(#68) — was itself dead, #68 being deferred.

Done:

- Rebuilt the branch on `D-core-backend` (#210), the live tip of the RDR core stack and
  the first base carrying every `rdr/` module these tests import. A branch reset rather
  than a merge, so #78's production commit (`_last_parent_of_type_`, superseded by #118
  and forbidden by `dag-facade-hardening`'s Wave-1 guard) does not ride into #79.
  Pre-rebuild tip, if it is ever wanted back: `0a305c68`.
- Brought the ported tests up to three interfaces that had moved: `RecordedCall` instead
  of tuples in `SpyProgressReporter`, `answer_function` instead of `answer_fn`, and
  `EQLSingleClassRDR.save_path` replaced by the `ModelSaver` strategy — the two
  `save_path` test classes are dropped, their replacement already covered by
  `test_fit_convergence.py` and `test_serialization.py`.
- Section headers moved to `# %%`; `scripts/format_docstrings.py` run over all eight files.
- PR re-targeted at `D-core-backend`, description rewritten, left a draft.

Verified: `test/krrood_test/test_eql_rdr/` 341 passed (264 on the base, 77 added here).

## Next

- Nothing outstanding on this branch. CI has not run on the rebuilt head yet; its last run
  was 2026-07-19 against the old base.
- Not this branch's to do, recorded so it is not lost: **#76 (`D-ui`) still sits on this
  branch's old tip and still carries #78's production commit**, so it needs the same
  restack before it can land. `D-ui-splice-fix`'s own regression test
  (`TestAttributeReusedInEarlierSiblingBranch`) still lives on that branch and is still
  that (deferred) item's follow-up — roadmap §10.
