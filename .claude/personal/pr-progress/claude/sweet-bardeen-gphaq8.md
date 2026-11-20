## Plan
- Get #613 (namespace-package) green and through review; release (VERSION bump of every cram2 package) is a separate PR.

## Done
- fbcf3d8f3c: merged fork main 38804f6fff; merge-probe CLEAN; CI 37/37 green.
- e57fa625a: README, LICENSE, classifiers, setuptools>=77 per distribution; test_distribution_metadata.py; 13 builds and twine check clean.
- 20700ffe0: removed never-run .github/workflows/krrood/publish-to-test-pypi.yml; PR description updated.

## Next
- Read CI at 20700ffe0 when prompted.
- Release PR must publish random_events with krrood (krrood-probabilistic needs random_events>=26.10.0) and raise krrood lower bounds; register 12 PyPI pending publishers.
- Open threads waiting on the developer: EQL→rustworkx-utils optional, who uses `scripts/import_distribution_modules.py`, Naren/David emails.
