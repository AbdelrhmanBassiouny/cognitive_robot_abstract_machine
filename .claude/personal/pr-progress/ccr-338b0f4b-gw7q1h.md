PR #537 (base main, ready), promoted as cram2#835; plan domain-models item spatial-math-move, first in the stack; #527 is stacked on it.

Plan:
- Resolve LucaKro's requested changes on cram2#835 (8 threads) without a re-export of the old module.

Done:
- c36afc73: old module and moved re-exports deleted, ~360 files' imports migrated; express -> express_in_own_frame bound to ValueInCartesianFrame3D; HasName[NameT]; tracker get/_get_untracked take name; resolve() documented; exception suggestions SemDT-free. #537 description rewritten.
- Merged into #527 (181d11bf; CoordinateSystem bases reordered for MRO).
- Local: krrood_spatial_math_test 19, krrood utils/patterns/symbolic_math 540, SemDT spatial_types + json 398, worlds/adapters/connections/geometry 893 (ROS-only failures).

Next:
- Owner posts the drafted inline replies on cram2#835's 8 threads, copies #537's description to cram2#835, asks LucaKro to re-review.
- #526 (preview) and #524 still conflict, as before this resolve.
