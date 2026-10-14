## Plan
- #504: typed size limits enforced on save; finished branches' progress notes pruned; session start loads one item.
## Done
- Tooling, tests (798 pass), skill docs; notes data migrated (prior state 37831be62); #207/#273/#279 closed.
- Review round 1 (c32c12512): 16 of 19 threads fixed and resolved; 3 left open.
- Review round 2 (8f04cb74a): Violation is an Exception; parsed argument names are StrEnums; both threads resolved.
## Next
- Open for the user: test-side definitions of hook-only names (markers, save-plan flags, hook filenames) in constants.py - threads on test_plan_size_limits.py:76 and test_session_start_sh.py:325/327.
- #277 needs retargeting to Measure.ITEM_COUNT; retarget #504 to main once #501 lands.
