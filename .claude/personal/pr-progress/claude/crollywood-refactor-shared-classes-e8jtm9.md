## Plan
- krrood_image ported onto #527; HSV Color moved keyword-only, every caller migrated.

## Done
- Merged #527 (6f2bd2c4); pushed 81506f8a, merge probe clean.
- Local tests green except ROS/graphviz/PyQt5-only ones; PR description rewritten.

## Next
- Read CI at 81506f8a (SemDT ORM generation, ROS, RoboKudo, giskardpy are first checked there).
- Labels to set: api-break, new-feature.
- Open to cram2 once #527 merges there.
