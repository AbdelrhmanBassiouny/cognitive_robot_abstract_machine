PR #515 (draft, on #503), item actions-budget/changed-library-matrix.

Plan
- Implemented as settled; see the PR description for the design and the decisions to check.

Done
- basstler.changed_libraries + tests (dataset workspace), run-time-exclude counting, ci.yml changed-libraries job, override kept at 16 (user-approved), packaging dependency (user-approved). Pushed 9c946ecb3.
- Full basstler suite: only the 18 failures #503's head has in this environment.

Next
- Watch the draft's first real CI run: confirm the run-time `exclude` expression works and that test_each_lib skips cleanly when every library is excluded.
- Retarget with #503 when it lands; converge with #284's classifier if it lands.
