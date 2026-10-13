Task: GitHub disabled Actions on the fork for wasted compute. Tracked as plan `actions-budget`
(tracking issue #502, dashboard https://claude.ai/artifact/8gxSNM8Rbp4tuLpxCJwQ4W).
Done: audit (300 runs Oct 2-8), user decisions (draft PRs: changed libs + dependents; integration event-only;
plan in basstler; monitors + warnings), plan created, branch re-cut from main.
Next: user re-enables Actions with only CI + Upstream reviews on; this branch implements item
`budget-manifest` (basstler/actions_budget.toml + module + conformance test + trigger changes on main).
