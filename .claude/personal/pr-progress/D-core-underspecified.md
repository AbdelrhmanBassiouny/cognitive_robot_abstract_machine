# D-core-underspecified (#64) — progress

## State (2026-10-31)
- Merged latest `main` (`da32d106e`, clean).
- `b4c15b9e8` answers the three 2026-10-31 review questions (`86b4c92c3` then renamed `is_unspecified` to `is_underspecified_single_value`, per review): `AttributeMatch.is_underspecified_single_value` replaces `is_ellipsis_target`, and `WrappedField.holds_collection`/`collection_types` replace the parser's own collection check (looked up via `get_wrapped_field`). Two threads resolved. The `holds_collection` thread stays open: it asks whether non-dataclass case types (no longer guarded) matter.
- Tests: 172 in the touched suites, 1434 across eql/symbol_graph/class_diagrams.
- Squashed on request into one commit `59ff6d560` on main `acad75674` (tree identical to `86b4c92c3`; local backup branch `backup/D-core-underspecified-pre-squash`). #65 re-merged it as `d6551c038` (tree unchanged, 61 passed), so its diff shows only its own 3 files.
- Labelled `new-feature` (AGENTS.md labels rule).
- The PR stays ready (promoted as cram2 #658).

## Next
- The user answers the open `holds_collection` thread.
- Fork CI on `59ff6d560` green, then drop `integration-conflict`.
- #66, #67, #98, #159, #210 still need restacking onto main.
