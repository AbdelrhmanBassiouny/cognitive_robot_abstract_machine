Plan
- Keep the branch mergeable with cram2 main and answer cram2#1019's reviews; the owner posts the replies.
- Design doc (implemented): https://claude.ai/artifact/3aEJ5hBBxZ7GGBMNK6XXKq

Done
- 9f5540e0: merges cram2 main 44e1f109 (#795, #1043); merge probe clean.
- 44c4f534 and f0712a33 answer ichumuh's 2026-11-23 review: unknown plane relations raise; MathematicalOperation replaces the operation string; cross_product returns its operands' type; has_position replaces "weight"; a kind of frame keeps only inner_product and cross_product (norm and distance moved onto the values). test/krrood_spatial_math_test: 739 passed; krrood symbolic math: 312 passed. SemDT and RoboKudo tests not run (need ROS).

Next
- Owner: post the 12 drafted replies in .claude/personal/review-replies/cram2-1019-2026-11-23.md (notes branch).
- Read the CI of f0712a33 on both PRs.
- #524 conflicts with this branch in 20 files; it needs its own resolve.
