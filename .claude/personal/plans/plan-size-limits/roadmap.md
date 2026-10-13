# plan-size-limits — standing rules

- The limits live in basstler/src/basstler/plan_size_limits.py (Measure) and are enforced by save-plan.sh and save-pr-progress.sh; raising one is the user's call.
- branch-index.tsv and dashboard-urls.yaml are keyed by plan id; any split or removal of a plan regenerates both, or session-start.sh stops resolving branches and /plan-dashboard mints duplicate pages.
- This plan's pull requests stack on #501 (basstler src layout): new modules go under basstler/src/basstler/ and hooks run them with "${BASSTLER_PYTHON}".
