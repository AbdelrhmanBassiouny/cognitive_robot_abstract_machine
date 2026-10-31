Plan (match-implicit-prediction / ellipsis-unconstrained-in-selective, draft PR #544, api-break):
- `...` is no constraint in selective queries; a collection with `...` constrains its size and stated elements.

Done:
- Implemented and pushed; CI green so far. Review asked whether this breaks `...` = "predict"; options A/B/C posted on the PR (B recommended: close, keep rejection).

Next:
- Await the decision. If B, close #544 and base infer-required-attributes on main, rechecking its "no query conditions" rule.
- Still open: may Match._has_ellipsis_attributes_ (test-only) be removed?
