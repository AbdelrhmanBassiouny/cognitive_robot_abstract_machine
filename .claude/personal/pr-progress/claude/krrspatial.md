PR #526 (ready, user-approved; reworked on user's request, base main): krrspatial holds SemDT's casadi spatial types. Plan: domain-models.

Plan
- One set of spatial types in krrspatial; SemDT module re-exports; ReferenceFrame/ReferenceFrameResolver interfaces; krrood ObjectReference shared.

Done
- Pushed dfb6b4964; #526 description rewritten, #526 and #524 retargeted to main; plan.yaml updated (symbolic-spatial-types folded in, krrimage unblocked).
- Local: krrspatial, krrood utils/patterns, version pass; SemDT 1332 pass, rest is missing ROS/robot packages.

Next
- Read CI, especially SemDT's ORM build (can't generate locally: MetaData needs ROS) and giskardpy.
- User re-clicks the updated Promote link; #524 then merges domain_models/README.md with this PR's.
