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

## What this branch is
`rdr/case_table.py` plus the seven shell-free RDR test modules — the presentation and
serialization coverage of the D-ui slice that needs no IPython shell. It is the middle of
the D-ui stack: `D-core-backend` (#210) → **#79** → #76 (`D-ui`).
