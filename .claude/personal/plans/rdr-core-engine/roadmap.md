# rdr-core-engine — standing rules

- CI is wedged on #98, #159 and #210's own merge refs. All three read `mergeable_state: unknown` and queue no runs however many times they are pushed; `ci.yml`'s trigger is unfiltered and the merges are trivial fast-forwards, so the wedge is GitHub-side. A base move followed by a push cleared it once and has since failed twice.
- The cascade did not stall uniformly. Measure how far behind each branch is before planning a steward pass rather than assuming stack order tracks it.
- Two generated files, not one, were conflicting on #67 — cleared 2026-08-31. `test/krrood_test/dataset/ormatic_interface.py` was tracked only here and is now removed from the index, with `main`'s `/ormatic_interface.py` ignore rule arriving in the same merge.
- `open_ready` means open plus non-draft, and deliberately not more. It answers *"can a dependent safely start stacking on this?"*, which stayed true of #67 throughout the six days it was unmergeable against its own base. Folding `mergeable_state` in would buy a visibility problem with a false negative; the visibility belongs in a per-item mergeable chip instead.
- `scripts/format_docstrings.py` regresses ```:return: ``x``` ``` to ```:return:``x``` and rewrites unrelated docstrings wholesale — fourteen recorded instances. Every round reverts its churn by hand and keeps its output only where the file is being rewritten anyway. It wants a package-wide pass of its own, which nobody has taken.
- Follow `.claude/personal/notes.md` and this repository's `AGENTS.md`.
- SOLID is a review gate: a new capability enters as an abstraction plus small dataclass implementations, and strategies stay substitutable without touching the engine.
- TDD: failing test first, and no test is modified to make something pass.
- `krrood` stays self-contained; world-like scenarios are mimicked in `test/krrood_test/dataset`.
- `plan_item_bootstrap.py` writes item fields at four-space indentation while these manifests sit at two, so `open`/`record`/`update`/`block` produce YAML that does not parse, and `save-plan.sh`'s error is swallowed by `capture_output`. Edit the manifest directly and say so. The fix is `plan-tracking-skills`' `plan-item-bootstrap-yaml-indent` (#160), unlanded.
- Subscribing to tracking issue #94 has been refused by the permission classifier in every container that has tried it, nine times. A skill relying on it for concurrent-change awareness should assume it will not work.
