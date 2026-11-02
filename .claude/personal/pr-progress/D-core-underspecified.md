# D-core-underspecified (#64) — progress

## Plan
- Answer the cram2 #843 review round (LucaKro, tomsch420: changes requested, 4 threads).

## Done
- `bb4cccbad`: `RippleDownRulesMatchParser`, `is_assigned_to_ellipsis`, `CollectionKind` enum (`list_like_classes` = element sequences incl. frozenset; `holds_collection` reads every kind), one-line `__post_init__` comment. 266 + 1811 krrood tests pass.
- PR stays ready (promoted, cram2 #843 open).

## Next
- Post inline replies on cram2 #843's 4 threads and to LucaKro's tutorial request (tutorial deferred to D-core-engine); session cannot write upstream.
- Carry `bb4cccbad` into #65 → #66 → #67 → #98 → #159 → #210; #159/#210 need the `RDRMatchParser` rename. Session's restack was denied by the permission classifier.
- Green fork CI on `bb4cccbad` (incl. semantic_digital_twin), then drop `integration-conflict` (its #192 cause is resolved).
