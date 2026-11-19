## Plan
- Get #613 (namespace-package) green and through review.

## Done
- ea4e4846a2: review round 1 (authors, trimesh to rustworkx-utils extra, general declared-dependency test).
- 1eda7b423c: CI fix. Blocker uses an import finder plus path cleanup (SciPy torch probe, pdbpp pdb hijack); docstrings `krrood check --since HEAD^1` wanted.

## Next
- Read CI at 1eda7b423c when prompted (ea4e4846a2: install-alone 23/23 green; krrood and small_packages jobs failed, fixed here).
- Open threads waiting on the developer: EQL→rustworkx-utils optional, who uses `scripts/import_distribution_modules.py`, Naren/David emails.
