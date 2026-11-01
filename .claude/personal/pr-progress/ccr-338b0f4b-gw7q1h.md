PR #537 (base main, ready), promoted as cram2#835; plan domain-models item spatial-math-move, first in the stack; #527 is stacked on it.

Plan:
- Get CI green and cram2#835 re-reviewed without re-exporting old modules.

Done:
- b89b4d72: semantic_digital_twin/spatial_types deleted; Derivatives/DerivativeMap -> semantic_digital_twin.world_description.derivatives.
- ed4b24cd: coraplex, giskardpy, robokudo, experiments, segmind declare krrood_spatial_math; gltf_loader's missed relative import fixed. Carried into #527.

Next:
- robokudo CI: robokudo team rewrites robokudo_test_data's old spatial-type names; then bump TestDataset.revision/checksum in robokudo/utils/data_downloader.py.
- Decide Derivatives' home with the owner (discussion open); fix its docstring ("on spatial positions") either way.
- LucaKro re-reviews cram2#835; 3 open threads wait on reviewers. #526 (preview) and #524 still conflict.
