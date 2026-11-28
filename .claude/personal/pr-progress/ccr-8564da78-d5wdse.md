PR: AbdelrhmanBassiouny/cognitive_robot_abstract_machine#621 (draft, fork) - Release 26.11.0

Plan
- Release 26.11.0 so the krrood-* distributions and krrood_synchronization reach PyPI.

Done
- sync_version bounds optional sibling deps (54b0768ed); release bump + CHANGELOG + docs (c33fca027).
- requires-python >=3.12 for the 10 packages depending on ormatic/random_events, with test (41beb7aad).

Next
- User: PyPI pending trusted publishers for the 12 krrood-* names and krrood-synchronization.
- User: why random_events 26.10.0 never published.
- User decides: is the <3.13 cap of the domain_models packages deliberate (propagate or drop).
- Upstream PR to cram2 only once the user accepts.
