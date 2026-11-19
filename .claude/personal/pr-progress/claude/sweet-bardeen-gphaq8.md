## Plan
- Get #613 (namespace-package) green and through review.

## Done
- ea4e4846a2: review round 1 (authors, trimesh to rustworkx-utils extra, general declared-dependency test).
- 1eda7b423c: CI fix. Blocker uses an import finder plus path cleanup (SciPy torch probe, pdbpp pdb hijack); docstrings `krrood check --since HEAD^1` wanted.
- fbcf3d8f3c: merged fork main 38804f6fff (no conflicts; mixin.py change followed into krrood-core); merge-probe CLEAN.

## Next
- Read CI at fbcf3d8f3c when prompted (ea4e4846a2: install-alone 23/23 green; krrood and small_packages failures fixed in 1eda7b423c).
- Open threads waiting on the developer: EQL→rustworkx-utils optional, who uses `scripts/import_distribution_modules.py`, Naren/David emails.
