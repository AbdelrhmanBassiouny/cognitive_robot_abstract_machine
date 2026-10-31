# D-core-underspecified (#64) — progress

## State (2026-10-31)
- Merged latest `main` (`da32d106e`, clean).
- `b4c15b9e8` answers the three 2026-10-31 review questions: `AttributeMatch.is_unspecified` replaces `is_ellipsis_target`, and `WrappedField.holds_collection`/`collection_types` replace the parser's own collection check (looked up via `get_wrapped_field`). Two threads resolved. The `holds_collection` thread stays open: it asks whether non-dataclass case types (no longer guarded) matter.
- Tests: 172 in the touched suites, 1434 across eql/symbol_graph/class_diagrams.
- Carried into #65 (`71ae66c55`; `rdr/exceptions.py` import conflict resolved, 61 passed).
- The PR stays ready (promoted as cram2 #658).

## Next
- The user answers the open `holds_collection` thread.
- Fork CI on `b4c15b9e8` green, then drop `integration-conflict`.
- #66, #67, #98, #159, #210 still need restacking onto main.
