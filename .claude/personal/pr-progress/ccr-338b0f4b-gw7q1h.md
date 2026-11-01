PR #537 (base main), promoted as cram2#835; plan domain-models item spatial-math-move, first in the stack; #527 is stacked on it.

Plan (resolving LucaKro's requested changes on cram2#835):
- No re-export: delete semantic_digital_twin/spatial_types/spatial_types, drop moved names from semantic_digital_twin.spatial_types and .exceptions, migrate every import (code, tests, docs) to krrood_spatial_math; drop former-module tests; JSON/ORM naming the old module stops loading (owner's call).
- CartesianFrame3D.express -> express_in_own_frame, ValueT bound to the spatial-type base; HasName generic in its name type.
- Document CartesianFrame3DReference.resolve params; remove KnownFrames.get override need; exception suggestions free of SemDT and create_kwargs.

Done:
- Upstream review read; plan + roadmap rule updated (d0686e5d9a).

Next:
- Implement, test, push; merge into #527's branch; draft inline replies for the 8 cram2#835 threads for the user to post.
