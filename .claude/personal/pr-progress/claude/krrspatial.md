PR #526 (ready, user-approved; reworked on user's request): domain_models/krrspatial holds SemDT's casadi spatial types. Plan: domain-models.

Plan
- Drop numeric Point2[C] types. Move spatial_types.py to krrspatial.spatial_types; SemDT module re-exports (old JSON type names keep resolving).
- ReferenceFrame interface (id, name); KinematicStructureEntity implements it. ReferenceFrameResolver interface found in from_json kwargs; SemDT's tracker implements it.
- Spatial exceptions move to krrspatial.exceptions; SemDT re-exports. test_KinematicStructureEntityNotInKwargs expects MissingReferenceFrameResolver (user-approved).
- krrspatial deps: krrood, casadi, numpy. Tests in test/krrspatial_test with mimic frames; SemDT tests stay.

Done
- Fork main fast-forwarded to cram2 main; merged into branch.

Next
- Implement, test, push; retarget #526 and #524 to main; rewrite #526 description; update plan.yaml (fold symbolic-spatial-types, unblock krrimage).
