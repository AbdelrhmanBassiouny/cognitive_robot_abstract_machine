Plan
- Get cram2 #843 merged; unblock #67 so #98 onward can restack.

Done
- 2026-11-03: merged main into #64 (factory_and_kwargs.py import conflict), carried to #65 and #66 (plus extract_types import fix for the object_to_source rename).
- Upstream #843 approved by LucaKro and tomsch420, 29/29 checks green.

Next
- #67 conflicts with #66 in core/base_expressions.py: decide how the evaluation-context restructure meets #67's fix.
- Reviewers resolve the 4 outdated #843 threads; then clear the integration-conflict label.
