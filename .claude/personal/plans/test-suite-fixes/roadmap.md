# test-suite-fixes — standing rules

- Follow `.claude/personal/cram-notes.md` and this repository's `AGENTS.md`.
- TDD: failing test first, and no test is modified to make something pass.
- Never skip, disable or quarantine a test to get a run green.
- Stage by explicit path, never `git add -u`: a sweep regenerates `ormatic_interface.py`, `query_graph.pdf`, `drawer_explanation.pdf` and `verbalization_results.py`, and a dirty tree after a sweep is the normal state here rather than a signal to commit.
- A long parallel sweep and an interactive experiment must not share a checkout. Five contiguous "failures" in the 900-run sweep were a fixture-swap experiment running against the same working tree; the contiguity is what gave it away.
