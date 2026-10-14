PR #508 (draft, base claude/brave-archimedes-nonocl = #501), with #506 merged in.
Plan item basstler-krrood-core-dependency in basstler-package.

Plan
- Keep in step with #506: merge claude/krrood-core-package after each change there.

Done
- krrood_core dependency + install wiring; classproperty/PathEnumeration/standard_streams
  from krrood_core; 43 exceptions in basstler/exceptions.py (exit_codes.py,
  plan_item_execution.py); board.json via serializer. 750 pass (CI job replayed).
- Live: fresh session start 2.8 s, 7 MB env, check-setup ok.

Next
- Await CI/review. Candidates left: 5 ExitCode enums, 3 run_git helpers, JSONModel.
