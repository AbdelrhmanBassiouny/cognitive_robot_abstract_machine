<!-- BEGIN-PR-PROGRESS -->
## Plan
- Land D-core-support (#67) on `main`: merge `main` into the branch, resolve the directory-rename conflicts, push, return to draft.
- Carry the fix into the descendants (#98, #159, #210, #68, #81), which are still in the old `krrood/src` layout.

## Done (2026-11-23)
- Retargeted #67 from `D-core-serialization` to `main`.
- Merged `main` (`2f2f5aafc`) as `adb130ec2`: the seven `rdr/` modules this branch adds were relocated to `krrood/krrood-eql/src`, content unchanged. Pushed; #67 back to draft.
- CI fix pushed as `0ebbbccb4`: tqdm and colorama declared in krrood-eql (clean-venv import of every module passes); `krrood check --since origin/main` has no findings (was 144); keyword-only dataclasses and methods, docstrings.
- Read at `0ebbbccb4`: `test_eql_rdr` + `test_rules.py` 123 passed / 25 skipped; dependency and metadata tests 57 passed.

## Next
- CI at `0ebbbccb4` not read yet. The first run on `adb130ec2` failed `krrood-eql` (tqdm) and `small_packages` (krrood check); others were still running.
- 25 `test_eql_rdr` tests skip here ("Failed to load zoo dataset": no network to UCI); not checked locally, so CI is their check.
- Descendant restack not carried: `maintenance restack --stacked-on D-core-support` stopped at `D-core-engine` (git-command-failed, checkout refused). Each descendant meets the same `krrood/src` -> `krrood-eql/src` rename; run `/plan-item-resolve` on them. They also call methods and constructors that are now keyword-only.
- Open threads: `rule_tree_view.py:255` (answered, redesign not taken), `test_conclusion_domain.py` (left for the developer).
<!-- END-PR-PROGRESS -->
