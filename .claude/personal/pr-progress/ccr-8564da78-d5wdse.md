PR: AbdelrhmanBassiouny/cognitive_robot_abstract_machine#621 (draft, fork) - Release 26.11.0

Plan
- Release 26.11.0 so the krrood-* distributions and krrood_synchronization reach PyPI.

Done
- Optional-dep bounds, release bump + CHANGELOG + docs, requires-python >=3.12 (54b0768ed..41beb7aad).
- Publish job per distribution from environment pypi-<distribution> (e0a4b26d7): PyPI allows one pending publisher per repo/workflow/environment.

Next
- User: pending publishers per new krrood-* project (env pypi-<project>); add pypi-krrood publisher to krrood; krrood-synchronization pending (env pypi).
- User: why random_events 26.10.0 never published.
- User decides: is the <3.13 cap of the domain_models packages deliberate.
- Upstream PR to cram2 only once the user accepts.
