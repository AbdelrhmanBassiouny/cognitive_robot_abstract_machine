# D-core-underspecified (#64) — progress

## Plan
- Answer the cram2 #843 review round (LucaKro, tomsch420: changes requested, 4 threads).

## Done
- `bb4cccbad`: `RippleDownRulesMatchParser`, `is_assigned_to_ellipsis`, `CollectionKind` enum (`list_like_classes` = element sequences incl. frozenset; `holds_collection` reads every kind), one-line `__post_init__` comment. 266 + 1811 krrood tests pass.
- PR stays ready (promoted, cram2 #843 open).

## Next
- Post inline replies on cram2 #843's 4 threads and to LucaKro's tutorial request (tutorial deferred to D-core-engine); session cannot write upstream.
- Carried into #65 (`9af25eb70`) and #66 (`e9368d0e8`). #67 `D-core-support` conflicts in `core/base_expressions.py`: its pre-installed-context active-root fix and test vs main's context restructure (9a4230055a); handed back to the user. #98 and above wait on it; #159/#210 then need the `RDRMatchParser` rename.
- Fork CI on `bb4cccbad`: cramph failed on runner disk (infra). Green CI, then drop `integration-conflict` (its #192 cause is resolved).
