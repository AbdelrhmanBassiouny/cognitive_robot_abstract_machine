PR #537 (base main, ready), promoted as cram2#835; plan domain-models item spatial-math-move, first in the stack; #527 is stacked on it.

Plan:
- Resolve review on cram2#835 (LucaKro, 8 threads) and #537 (owner, 2 threads) without re-exporting old modules.

Done:
- c36afc73: old module deleted, ~360 files' imports migrated, smaller cram2#835 threads addressed.
- b89b4d72: semantic_digital_twin/spatial_types deleted; MissingReferenceFrameError -> krrood_spatial_math.exceptions; inverse_frame -> HomogeneousTransformationMatrix.invert_numeric_matrix; Derivatives/DerivativeMap -> semantic_digital_twin.world_description.derivatives. #537's 2 new threads replied and resolved; description updated.
- Merged into #527 (b2863044).

Next:
- Owner posts the drafted inline replies on cram2#835's 8 threads, copies #537's description to cram2#835, asks LucaKro to re-review.
- #526 (preview) and #524 still conflict, as before this resolve.
