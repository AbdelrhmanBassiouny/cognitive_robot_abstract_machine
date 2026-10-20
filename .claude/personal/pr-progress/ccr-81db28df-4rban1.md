CRAM #515 is closed: split into basstler#55 (package half, draft on basstler#10) and this branch's ci.yml half, kept at 9c946ecb3.

Plan
- basstler#55 lands after basstler#10; the ci.yml half comes back via basstler-package/cram-basstler-removal.

Done
- basstler#55: changed_libraries with --project-root/--tooling, run-time-exclude counting, 21 tests; full basstler suite 914 passed.

Next
- When cram-basstler-removal lands: re-apply 9c946ecb3's ci.yml/actions_budget.py onto CRAM main, passing the plugin's flags, and confirm the run-time exclude on a real draft run.
