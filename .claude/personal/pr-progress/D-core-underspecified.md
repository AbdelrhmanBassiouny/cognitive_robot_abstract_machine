# D-core-underspecified (#64) — progress

## State (2026-10-31)
- One commit, `0edfbb883`, on main `acad75674` (pre-squash backup: local `backup/D-core-underspecified-pre-squash`).
- All review threads resolved. The last one asked what to do when `get_wrapped_field` returns `None`; answered by raising the new `UndeclaredInferenceTarget(case_type, attribute_name)`, with two tests (non-dataclass case type, property target). The guard passes the stack tip's 265 RDR tests.
- #65 merged it as `e98327a13` (63 passed); its diff still shows only its own 3 files.
- Fork CI on `59ff6d560`: only `version` (runner out of disk) and robokudo `test_query` (ROS action timing) failed, neither touching krrood. Upstream cram2 #658: no reviews, no threads; a stale giskardpy failure.
- Labelled `new-feature`. The PR stays ready (promoted as cram2 #658).

## Next
- Fork CI on `0edfbb883` green (rerun the two infra jobs if they repeat), then drop `integration-conflict`.
- #66, #67, #98, #159, #210 still need restacking onto main.
