## Plan
- Answer tomsch420's remaining cram2 #843 threads: drop the `list_like_classes` alias, give `leaf_types` an enum, de-abbreviate `single_target`.

## Done
- 20cf059d5: `list_like_classes` removed (all krrood and semantic_digital_twin readers use `CollectionKind.ELEMENT_SEQUENCE.value`); `LeafKind.JSON_SCALAR` replaces `leaf_types`; `t` renamed `target`. Carried into #65 and #66.
- Local: 1602 krrood tests pass; failures are only missing matplotlib / jpt in the sandbox. Fork CI red only on an unrelated experiments timeout.

## Next
- Post inline replies upstream (cannot from here) and ask tomsch420 to re-review.
- #67 conflicts with main in base_expressions.py: resolve, then restack #98, #159, #210 and the engine.
- Drop `integration-conflict` on #64; suggest `api-break`.
