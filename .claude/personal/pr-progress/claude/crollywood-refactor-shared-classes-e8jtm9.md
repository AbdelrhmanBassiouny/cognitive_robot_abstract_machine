## Plan
- Merge #527's head 1392bb20 into #524; resolve its 7 conflicts (ci.yml, cramph styles, domain_models README, experiments + root pyproject, graph_node, version test).
- Check krrood_image against #527's EmbeddedPlane 2D-frame change; run krrood_image, spatial-math, version tests; push via maintenance push.

## Done
- CI green at 81506f8a (14/14); no review threads.

## Next
- #527 itself conflicts with main 8fdae4a2 (8 SemDT files) - its owner's resolve.
- Open to cram2 once #527 merges there.
