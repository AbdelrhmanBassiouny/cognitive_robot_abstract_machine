# PR #294 - episode-artifacts-recorded (icra-foundation, long-term-memory track)

Branch `claude/icra-foundation-episode-artifacts-nki2is`, based on #271
(`claude/icra-experiments-ormatic-episodes-ib9lr3`), where `Episode` lives.
Draft PR: https://github.com/AbdelrhmanBassiouny/cognitive_robot_abstract_machine/pull/294

## Done

- Setup: dashboard dependencies installed; branch re-cut from #271 (it had
  descended from `integration`).
- Context gathered: roadmap read in full, #271's code read, scope check run
  (stack, don't fold - a whole module remains once the parent's files are set aside).
- Branch, draft PR #294, `plan.yaml` and `roadmap.md` recorded, dashboard republished.
- Tests written first: `test/experiments_test/test_episode_artifacts.py`.
- `experiments/src/experiments/episodes/artifacts.py`: `EpisodeArtifact`,
  `ArtifactDirectory`, `EpisodeArtifacts`, `Transcript`, `ArtifactNotKept`.
- `experiments/scripts/generate_orm.py`: new module added to `ignored_classes`.
- `scripts/format_docstrings.py` run on all three changed files.
- Committed (`6ef556ae5`) and pushed; PR description filled in, still a draft.

## Decisions taken (all recorded in the PR description and roadmap.md)

- `episode.py` NOT touched - `Episode.identifier` already documents itself as the
  address artifacts are kept under, so the parent built the reference.
- `recording.py` NOT touched - wiring a run to write artifacts belongs to
  `episode-corpus-generated-at-scale`.
- The store keeps the run's *files*; it does not serialize a `World` (that call is
  recorded on #271 as the developer's).
- `RecordedVideo` imported under `TYPE_CHECKING` only, so the module works without MuJoCo.
- `run_files` returns `[]` rather than raising; `video`/`transcript` raise `ArtifactNotKept`.

## Next

Nothing outstanding on this branch. Waiting on CI, and on the developer's review.

## Outstanding / flagged

- **Tooling bug, not fixed here**: `.claude/hooks/plan_item_bootstrap.py`'s
  `ITEM_FIELD_INDENT` is 4 spaces, but every `plan.yaml` indents item fields by 2.
  `open`/`record` therefore write `branch`/`pull_request_number`/`status`/`session`
  one level too deep - inside the preceding folded scalar or list - and
  `save-plan.sh` rejects the result as unparseable YAML. Worked around by writing
  the manifest directly. Blocks every kickoff/resolve bootstrap until fixed;
  out of scope for this PR.
- Tests are CI-only (nothing in this workspace installs in a session container),
  so this branch is not verified until CI runs. The module's logic WAS executed
  locally against stand-ins - 12 behaviours, all passing - but not as pytest.
- `generate_orm.py` is also appended to by #278: a textual meeting, not a design one.
