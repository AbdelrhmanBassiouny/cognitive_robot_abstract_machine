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

**2026-08-30 (later):** a fresh `/plan-item-resolve` session found a review round the
rebuild above had drawn minutes after it pushed — 11 threads, never recorded here since
nothing had re-read the PR before reporting the round finished. All mechanical: missing
function/method docstrings and `:param:`/`:return:` docs, missing dataclass field
docstrings, four abbreviated names (`_val`/`attr`, `ser`, `_animal_var`,
`_mixed_alt_then_ref_query`), and one box-drawing divider. Applied and pushed as
`8dc1a7c8`:

- Every function, method and dataclass field across all eight files this PR adds now has
  its own docstring — the fourth thread's *"check the whole PR"* ask was taken literally,
  so the same gap found and fixed in `test_case_table_side_by_side.py`,
  `test_corner_case_store.py` and `test_variable_completion.py` too, not only the four
  files a reviewer's attention had reached.
- The four flagged abbreviations are spelled out, cascaded to every other abbreviated
  local name in the same function (so `render_cases_side_by_side` is not half-renamed),
  but not swept across the rest of the PR — `av`, `sp`, `test_progress_bar.py`'s own
  dividers are left alone since no thread named them.
- All eleven threads replied to individually (naming the commit) and resolved.

Verified again: `test/krrood_test/test_eql_rdr/` still 341 passed, 0 failed — unchanged,
since the round touched only names and docstrings. `scripts/format_docstrings.py`
reproduced its recurring `:return:` space regression three more times; reverted by hand,
kept the rest. Draft was already `true`, so no restore-to-draft was needed.

## Next

- Nothing outstanding on this branch. CI has not queued since the rebuild's first push
  (`mergeable_state` reads `unknown`, the same wedged-merge-ref signature §29/§30/§32 of
  the roadmap record for #98/#159/#210) — worth a push-after-base-move retry per §21's
  remedy if picked up again, though §29/§32 both found that remedy insufficient on its
  own for a pull request already wedged.
- Not this branch's to do, recorded so it is not lost: **#76 (`D-ui`) still sits on this
  branch's old tip and still carries #78's production commit**, so it needs the same
  restack before it can land. `D-ui-splice-fix`'s own regression test
  (`TestAttributeReusedInEarlierSiblingBranch`) still lives on that branch and is still
  that (deferred) item's follow-up — roadmap §10.
- Found in passing, not this round's to fix: `test_progress_bar.py`'s
  `TestIPythonProgressBar` methods type-hint `mock_tqdm: pytest.MagicMock`, which does not
  exist on `pytest` (only the first method correctly uses the imported `MagicMock`). Kept
  inert by `from __future__ import annotations`, but worth a real fix if that file is
  touched again.
