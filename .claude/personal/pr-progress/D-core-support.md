<!-- BEGIN-PR-PROGRESS -->
## Plan
- Land D-core-support (#67) on `main`: merge `main` into the branch, resolve the directory-rename conflicts, push, return to draft.
- Carry the fix into the descendants (#98, #159, #210, #68, #81), which are still in the old `krrood/src` layout.

## Done (2026-11-23)
- Retargeted #67 from `D-core-serialization` to `main`.
- Merged `main` (`2f2f5aafc`) as `adb130ec2`: the seven `rdr/` modules this branch adds were relocated to `krrood/krrood-eql/src`, content unchanged. Pushed; #67 back to draft.
- Read at `adb130ec2`: `test_eql` 1604 passed / 4 skipped; `test_eql_rdr` 95 passed / 25 skipped.

## Next
- CI at `adb130ec2` not read; last read (2026-11-17, older head) had `test_each_lib (krrood)` failing, cause not read.
- 25 `test_eql_rdr` tests skip here ("Failed to load zoo dataset": no network to UCI); not checked locally, so CI is their check.
- Descendant restack not carried: `maintenance restack --stacked-on D-core-support` stopped at `D-core-engine` (git-command-failed, checkout refused). Each descendant meets the same `krrood/src` -> `krrood-eql/src` rename; run `/plan-item-resolve` on them.
- Open threads: `rule_tree_view.py:255` (answered, redesign not taken), `test_conclusion_domain.py` (left for the developer).
<!-- END-PR-PROGRESS -->
