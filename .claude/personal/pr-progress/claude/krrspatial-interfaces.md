Plan
- Answer cram2#1019's reviews; the owner posts the replies below and resolves the threads.

Done
- 8f214196 merges main 113e87ec; probe clean at 14519d1f.
- 47f984f6: type variables named Generic<Bound>. e859218f: 2D types in spatial_types_2_dimensional.
- 504770533a: krrood SubClassSafeGeneric.binds_generic_parameter.
- 14519d1f: StoredPoint/StoredVector (fields are coordinates; arithmetic and frame checks in the base; PointAndVectorFramesDifferError at definition); Point[frame, vector, coordinate=float]; MetricPoint/Vector → CartesianPoint/Vector; casadi value and change bases carry SymbolicMathType and JSON; z_axis on 3D frames, EmbeddedPlane.normal; README walk-through.

Next
- Owner: post the replies below; read CI on 14519d1f; discuss the fork's MetricPoint/Vector thread (answered by the CartesianPoint/Vector rename).
- krrood check (findings on touched lines): set aside by the owner.
- #524: conflicts with main in its own files; needs its own resolve.

Replies for cram2#1019
- spatial_types.py:1755: Done in 14519d1f: a new space's point and vector only declare fields (StoredPoint[PixelFrame, PixelVector]); the base does arithmetic and frame checks; casadi types have 3 parents instead of 5; README walk-through.
- embedded_plane.py:21: Done in 14519d1f: EmbeddedPlane.normal is the frame's z_axis; another normal means a frame whose z-axis it is.
- coordinate_system.py:18: Renamed in 47f984f6 to Generic<Bound>.
- spatial_types.py:2040: Done in e859218f: spatial_types_2_dimensional.
