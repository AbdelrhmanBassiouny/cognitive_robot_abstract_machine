PR #537 (draft, base main), plan domain-models item spatial-math-move, first in the stack; #527 is stacked on it.

Plan:
- On main: package skeleton + [casadi] extra, CartesianFrame3D(HasName, HasID) declaring express, resolver/reference on krrood's ObjectReference (WorldEntityReference too), move with only necessary edits; old module is the package spatial_types/spatial_types/ re-exporting (GitHub shows rename).

Done:
- Rebuilt on main (6c0ea740, force-pushed with the user's go-ahead), base main. #537 merged into #527's branch (74b550ab), #527 base -> this branch. Plan reordered + adopt folded into planar-point-interface; #525 comment.
- Local: krrood_spatial_math_test 16, test_object_reference 8, SemDT test_spatial_types 373, test_json_parsing 44 (ROS fixtures left to CI).

Next:
- CI on #537; user review; api-break talk with SemDT/krrood code owners.
- #524 still needs its own restack (krrspatial rename, Color/ORM conflicts with main).
