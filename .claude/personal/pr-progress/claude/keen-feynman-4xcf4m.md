## Plan
- Answer the three open review questions on PR 546 once the owner decides.

## Done
- 8dcc61cb36: Role.is_same_semantic_entity; IsSameSemanticEntity calls it. EQL kept out of core (28 crossings). Tests + pre-commit green at 8dcc61cb36; merged into #547 (cb45de5c6d).
- 8 Nov review: 5 threads fixed in e5fa40ecd6 (krrood.source_analysis, renames, docstrings) and resolved; #547 merged to b2cf2c16b7.

## Next
- Open threads: move code_parsing_utils/source_extraction_utils (API break, own PR?); narrow core list to roadmap's four; runtime mode for the backstop.
- CI at e5fa40ecd6 unread.
