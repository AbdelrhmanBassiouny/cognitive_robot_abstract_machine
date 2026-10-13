PR B (not yet opened): basstler adopts krrood_core. Stacked on #501, with #506
(claude/krrood-core-package, krrood_core package) merged in.

Plan
- Exceptions -> DataclassException in one basstler/exceptions.py. User chose: tool exit
  codes move to basstler/exit_codes.py as PlanItemBootstrapExitCode/PlanItemModeExitCode;
  ExecutionMode to its own small module; ClassVar exit_code -> classproperty.
- board.json round-trip (BoardExport.as_json / stack.load_board) -> krrood_core serializer.
  Stdout reports stay hand-shaped (user: round-trips only).
- Live-verify a fresh session start (delete basstler/.venv), open draft PR (base #501's
  branch claude/brave-archimedes-nonocl), add both PRs as items in plan basstler-package.

Done
- Install wiring (BASSTLER_WORKSPACE_DEPENDENCIES etc.), classproperty/PathEnumeration
  from krrood_core. Suite: 751 pass (CI-like env: scratchpad cienv first on PATH).

Next
- exit_codes module, then exceptions.py.
