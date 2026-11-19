# PR #613 — namespace-package (krrood-light-core), krrood-distributions folded in

## Plan
krrood is a namespace package split into 12 krrood-* distributions at krrood/<distribution>/src/krrood/<part>, plus the krrood meta distribution; per-distribution install-alone CI on Linux and Windows.

## Done (head 3a91395240, clean against cram2 main 113e87ec)
- CI's 35 krrood failures fixed (import root steps over a namespace portion).
- EQL no longer imports ORMatic; property_return_statement in EQL; templates in their parts.
- Split, sync_version == pins, core boundary in krrood-core, rename-aware `krrood check`, serializer distance in core, frame check over every portion.
- Local: 3594 passed; only main's environment failures remain. All 12 install alone and import on Linux.

## Next
- Read CI at the head (main now skips CI on drafts) and the Windows install-alone job once it runs.
- Developer decisions listed in the PR's "Assumptions and open points": leftover meta deps, newly declared deps, ruff pin for all installs, probabilistic_model cycle, PyPI trusted publishers, the dead test-PyPI workflow.
