PR #536 (draft, base `main`, label `bug`). Not promoted upstream yet.

Plan
- Drop the unused `typing_extensions` import from `.github/docker/setup_workspace.py` (runs on bare `ros:jazzy` Python); test that it imports only the standard library.

Done
- ec301e2d0: fix + `test_docker_workspace_setup.py` (fails before, passes after).

Next
- Image build unverified (no Docker daemon here): dispatch `update_docker` on this branch, or let it run after merge; then rerun #534's CI.
- Same bug upstream: promote to cram2 when the user accepts.
