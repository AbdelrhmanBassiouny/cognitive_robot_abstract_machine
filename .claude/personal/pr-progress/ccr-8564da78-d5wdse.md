PR: AbdelrhmanBassiouny/cognitive_robot_abstract_machine#621 (draft, fork) - Release 26.11.0

Plan
- Release 26.11.0 so the krrood-* distributions and krrood_synchronization reach PyPI.

Done
- Optional-dep bounds, release + CHANGELOG + docs, requires-python >=3.12 (54b0768ed..41beb7aad).
- Publish job per distribution, env pypi-<distribution> (e0a4b26d7); krrood meta publishes after all krrood-* (e715bd24d).
- CI: same 5 test jobs fail on main 595eb237c; segmind cause is missing iai_objects ROS package (#986, old CI image).

Next
- User: publish in rounds of 3 pending publishers (PyPI limit), re-run failed jobs; order in PR body.
- User: add pypi-krrood publisher to existing krrood project.
- User: why random_events 26.10.0 never published; is the <3.13 cap deliberate.
- Upstream PR to cram2 only once the user accepts.
