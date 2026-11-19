# PR #613 — namespace-package (krrood-light-core), krrood-distributions folded in

## Plan
krrood is a namespace package split into 12 krrood-* distributions at krrood/<distribution>/src/krrood/<part>, plus the krrood meta distribution; per-distribution install-alone CI on Linux and Windows.

## Done (head 3e9ca83b5c, clean against cram2 main 113e87ec)
- CI's 35 krrood failures fixed (import root steps over a namespace portion).
- EQL no longer imports ORMatic; split, == pins, core boundary, rename-aware `krrood check`.
- Install-alone CI at 3a91395240 failed (Windows checkout: long paths; PyPI probabilistic_model chosen over local wheel). Fixed: core.longpaths, constraints to local wheels, krrood_compute_resources -> krrood-core. Replayed locally for probabilistic and core. CI at 31c0e7bb17: all Linux jobs green; Windows failed compiling random_events (MSVC rejects `and`/`or`) -> setup.py passes /permissive- on Windows.

## Next
- Read the Windows install-alone jobs at 3e9ca83b5c.
- Developer decisions in the PR's "Assumptions and open points".
