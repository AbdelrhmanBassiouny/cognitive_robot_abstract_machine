PR #536 (draft, base `main`, label `bug`). Promotion link given to user (cram2 compare main...claude/docker-image-standard-library); upstream PR not yet opened.

Plan
- Drop the unused `typing_extensions` import from `.github/docker/setup_workspace.py` (runs on bare `ros:jazzy` Python); test that it imports only the standard library.

Done
- ec301e2d0: fix + `test_docker_workspace_setup.py` (fails before, passes after).

Next
- Image build unverified (no Docker daemon here): dispatch `update_docker` on this branch, or let it run after merge; then rerun #534's CI.
- User opens the upstream PR from the link and adds `bug-fix`.
