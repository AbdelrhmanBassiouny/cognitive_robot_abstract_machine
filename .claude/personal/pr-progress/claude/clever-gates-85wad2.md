Plan (match-implicit-prediction / ellipsis-unconstrained-in-selective):
- `...` is no constraint in selective queries; a list with `...` constrains its length and stated elements.
- Drop SelectiveBackend's guard and SelectiveBackendCannotResolveEllipsisMatch.

Done:
- Rewrote the rejection tests to assert matches; Match._query_conditions_ and AttributeMatch._conditions_on_stated_elements_; docs updated.

Next:
- Run test_eql, test_underspecified_knowledge, test_verbalization; format; commit; push; open draft PR (api-break).
- Ask the user whether Match._has_ellipsis_attributes_ (now used only by tests) can go.
