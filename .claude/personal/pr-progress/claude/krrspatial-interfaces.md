Plan
- Answer cram2#1019's reviews; the owner posts the replies and resolves the threads.
- Design doc (implemented): https://claude.ai/artifact/3aEJ5hBBxZ7GGBMNK6XXKq

Done
- Every code ask of the owner's cram2#1019 review is in the branch up to 7c0b1bda (cross product and axes on the frame kind, README pixel-space example, bool has_position). test/krrood_spatial_math_test: 733 passed; pre-commit clean; SemDT, giskard and coraplex not run locally (ROS).

Read 2026-11-20 at 7c0b1bda
- Merge probe against cram2 main 82707c74: clean.
- Fork CI: 45 of 46 pass. Only small_packages fails, at `krrood check --since HEAD^1`: rule violations in files the PR touches, set aside by the owner.
- Fork review threads: 60 of 64 read, all resolved.
- Not checked: cram2#1019's CI and threads (the Action answered 404, a helper session did not finish cloning).

Next
- Owner: post the replies in .claude/personal/review-replies/cram2-1019.md (notes branch).
- #524 needs its own resolve.
- Possible follow-up: a reusable law test for coordinate changes (inverse @ change is no change).
