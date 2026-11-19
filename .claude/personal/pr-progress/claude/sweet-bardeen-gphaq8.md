# PR #613 — namespace-package (krrood-light-core), krrood-distributions folded in

## Plan
krrood is a namespace package split into 12 krrood-* distributions at krrood/<distribution>/src/krrood/<part>, plus the krrood meta distribution; per-distribution install-alone CI on Linux and Windows.

## Done (head 52a48209e9, clean against cram2 main 113e87ec)
- CI's 35 krrood failures fixed (import root steps over a namespace portion).
- EQL no longer imports ORMatic; split, == pins, core boundary, rename-aware `krrood check`.
- Install-alone CI at 3a91395240 failed (Windows checkout: long paths; PyPI probabilistic_model chosen over local wheel). Fixed: core.longpaths, constraints to local wheels, krrood_compute_resources -> krrood-core. Replayed locally for probabilistic and core. CI at 31c0e7bb17: all Linux jobs green; Windows failed compiling random_events (MSVC rejects `and`/`or`) -> setup.py passes /permissive- on Windows. CI at 3e9ca83b5c: Linux green; Windows failed at bindings.cpp:105 (&open ambiguous with the CRT's POSIX open) -> bound via py::overload_cast (0e9b784a83). CI at 0e9b784a83: 23/24 green; krrood-probabilistic on Windows missed anytree (now declared by probabilistic_model) and then jpt (pyjpt is Linux-only) -> that job excluded on Windows (52a48209e9). Replayed locally without pyjpt.

## Next
- Read the Windows install-alone jobs at 52a48209e9.
- Developer decisions in the PR's "Assumptions and open points".
