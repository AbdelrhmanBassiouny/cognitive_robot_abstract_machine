Plan
- Answer cram2#1019's reviews; the owner posts the replies and decides the two proposals.

Done
- 8f214196 merges main 113e87ec (VectorPair/ScrewAxis under the Dimensional names; velocity limit tasks removed); probe clean at e859218f.
- 47f984f6: type variables named Generic<Bound> (ichumuh, coordinate_system.py:18).
- e859218f: 2D types and EmbeddedPlaneProjection moved to spatial_types_2_dimensional, every import migrated (ichumuh, spatial_types.py:2040).
- Earlier: coplanar EmbeddedPlanes equal (3fc103c0), EmbeddedPlaneRelation, casadi-free LineSegment (5fe60be8).

Next
- Owner: post the replies below; decide the two proposals; read CI on e859218f; discuss the fork's MetricPoint/Vector thread.
- krrood check (1128 findings on touched lines): set aside by the owner.
- #524: conflicts with main in its own files; needs its own resolve.

Proposals (owner decides)
- New space too costly (spatial_types.py:1755): Point/Vector implement +, −, × and the same-frame check over coordinates via an abstract from_coordinates; README walk-through of an image plane. Cuts the mimic's ~135 lines to ~30; interfaces stay.
- Explicit normal (embedded_plane.py:21): keep the frame's z-axis as the normal (a plane needs in-plane axes too); say so in the docstring; normal already explicit as OrthogonalProjection.plane_normal.

Replies for cram2#1019
- coordinate_system.py:18: Renamed in 47f984f6 to Generic<Bound> (GenericSpace, GenericPoint, …), like GenericSpatialType and SemDT's GenericWorldEntity.
- spatial_types.py:2040: Done in e859218f: the 2D types and EmbeddedPlaneProjection are in krrood_spatial_math.spatial_types_2_dimensional; every import moved.
- spatial_types.py:1755 / embedded_plane.py:21: drafts in the proposal file of session 01JxHGiLRgwm8kRFq7Zyxhbg.
