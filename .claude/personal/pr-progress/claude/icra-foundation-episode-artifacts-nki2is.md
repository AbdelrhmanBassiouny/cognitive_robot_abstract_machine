# PR #294 - episode-artifacts-recorded (icra-foundation, long-term-memory track)

Branch `claude/icra-foundation-episode-artifacts-nki2is`, based on #271
(`claude/icra-experiments-ormatic-episodes-ib9lr3`), where `Episode` lives.
Draft PR: https://github.com/AbdelrhmanBassiouny/cognitive_robot_abstract_machine/pull/294

## Plan

New module `experiments/src/experiments/episodes/artifacts.py`:

- `EpisodeArtifact` - StrEnum of the three names artifacts are kept under.
- `ArtifactDirectory` - where every episode's artifacts live; environment variable
  with a built-in default, mirroring how `ResultsDatabase` resolves where rows go.
- `EpisodeArtifacts` - one episode's directory, named by `Episode.identifier`;
  `keep_video` / `keep_file` / `keep_transcript` write, `video` / `run_files` /
  `transcript` read back.
- `Transcript` - episode plus trials, `render()` produces the readable document.
- A custom exception for reading an artifact that was never kept.

Plus `experiments/scripts/generate_orm.py`: ignore the new module (a place where
files are kept is machinery, not a record), the same reason `episodes.recording`
is ignored.

`episode.py` and `recording.py` are deliberately NOT touched - `Episode.identifier`
already documents itself as the address artifacts are kept under, and wiring a run
to write artifacts belongs to `episode-corpus-generated-at-scale`.

Tests in `test/experiments_test/test_episode_artifacts.py`, TDD: written first,
failing, then the module. Two-trial episode, all three artifacts read back.

## Done

- Setup: dashboard dependencies installed; branch re-cut from #271 (it had
  descended from `integration`).
- Context gathered: roadmap read in full, #271's code read, scope check run
  (stack, don't fold - a whole module remains once the parent's files are set aside).
- Branch, empty bootstrap commit, draft PR #294 opened.
- `plan.yaml` (branch/PR/status/session) and `roadmap.md` section saved to
  personal-notes.

## Next

1. Write the failing tests.
2. Write `artifacts.py`.
3. `generate_orm.py` ignore-list entry.
4. `scripts/format_docstrings.py` on every modified file.
5. Fill in the PR description; keep it a draft.

## Outstanding / flagged

- **Tooling bug, not fixed here**: `.claude/hooks/plan_item_bootstrap.py`'s
  `ITEM_FIELD_INDENT` is 4 spaces, but every `plan.yaml` indents item fields by 2.
  `open`/`record` therefore write fields one level too deep and `save-plan.sh`
  rejects the YAML. Worked around by writing the manifest directly. Blocks every
  kickoff/resolve bootstrap until fixed; out of scope for this PR.
- `generate_orm.py` is also appended to by #278 - a textual meeting, not a design one.
- Experiments tests are CI-only (ROS / `random_events` cannot run in a session
  container), so this branch is not verified until CI runs.
