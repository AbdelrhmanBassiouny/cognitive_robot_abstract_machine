# plan-size-limits — standing rules

- ~~`.claude/shared/plan_model.py` is not on `main`.~~ Settled by #207: the budget lives in `.claude/hooks/plan_size_budget.py`, a module of its own on `main`, rather than as a third copy of a file that exists only on #151 and #154 - the #106/#110 failure. Moving it into `.claude/shared/` once that module lands is a rename, not a merge.
- #185 (basstler-package) relocates the ground. It moves `plan_manifest_tools.py` to `basstler/plan_manifest_tools.py` and its tests to `test/basstler_test/`, and edits `save-plan.sh` plus the `add-plan-item`, `plan-item-kickoff` and `plan-item-resolve` skill documents. Whichever lands second rebases.
- #151, #154 and #156 all edit `plan-create/SKILL.md` and the kickoff/resolve skills. Overlap rather than ownership, but worth coordinating before `minimal-roadmap-writing` starts.
- The splits move live data every session reads. `branch-index.tsv` and `dashboard-urls.yaml` are keyed by plan id; both must be regenerated, or `session-start.sh` stops resolving branches to plans and `/plan-dashboard` publishes duplicate pages under the new ids.
