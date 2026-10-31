Plan (match-implicit-prediction / ellipsis-unconstrained-in-selective, draft PR #544, api-break):
- `...` is no constraint in selective queries; a collection with `...` constrains its size and stated elements.

Done:
- Implemented, tests rewritten and added, docs updated; test_eql and test_underspecified_knowledge pass; pushed; draft PR #544 labelled api-break.

Next:
- Await the user's answer: may Match._has_ellipsis_attributes_ (now used only by tests) be removed?
- Then infer-required-attributes, stacked on this branch.
