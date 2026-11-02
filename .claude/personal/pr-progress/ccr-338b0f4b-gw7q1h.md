PR #537 (base main, ready), promoted as cram2#835; plan domain-models item spatial-math-move, first in the stack; #527 is stacked on it.

Plan:
- Get cram2#835 green and re-reviewed without re-exporting old modules.

Done:
- b89b4d72: semantic_digital_twin/spatial_types deleted; Derivatives/DerivativeMap -> semantic_digital_twin.world_description.derivatives.
- ed4b24cd: coraplex, giskardpy, robokudo, experiments, segmind declare krrood_spatial_math; gltf_loader's missed relative import fixed.
- 92d5a3d2: robokudo_test_data moved into test/robokudo_test/dataset; data_downloader, pooch, filelock removed.
- 8a436f49: RecordedFrame.acquired_at is a numpy datetime64[ns] (written timestamp unchanged); express_in_own_frame's value param reads "A value in the same space as this frame" (ichumuh, cram2#835).

Next:
- Find why cram2#835's experiments job fails (log holds only exit code 1; fork run passed).
- Carry 8a436f49 into #527 with the next restack.
- LucaKro re-reviews cram2#835; the reexport and frames.py threads are outdated and await resolving on the upstream. #526 and #524 still conflict.
