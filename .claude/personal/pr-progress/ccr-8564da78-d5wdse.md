PR: AbdelrhmanBassiouny/cognitive_robot_abstract_machine#621 (draft, fork) - Release 26.11.0

Plan
- Release 26.11.0 so the krrood-* distributions and krrood_synchronization reach PyPI.

Done
- sync_version bounds optional sibling dependencies (54b0768ed, tested).
- Version 26.11.0 everywhere, CHANGELOG 26.11.0 with the pip upgrade warning, docs use krrood-development-tools (c33fca027).

Next
- User: PyPI pending trusted publishers for the 12 krrood-* names and krrood-synchronization.
- User: why random_events 26.10.0 never published.
- User decides: krrood meta requires-python >=3.12, since krrood-ormatic needs it.
- Upstream PR to cram2 only once the user accepts.
