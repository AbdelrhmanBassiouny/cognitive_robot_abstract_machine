# claude/belief-checked-9p16r2 - "Do your eyes and your belief agree?" (PR #325)

Draft PR: AbdelrhmanBassiouny/cognitive_robot_abstract_machine#325, targeting
`claude/icra-experiments-simulation-pipeline-w4ep7n` (#265), which already carries the
episode observer.

## What this answers

The paper's belief/perception cross-check, spelled with the expectation machinery that
already exists (`segmind.expectations`, `experiments.montessori.perception.expectations`)
rather than with a router or a cross-check class of its own.

## Design calls I made (asked, told "what do you recommend")

1. **Belief timing.** The belief is taken by a step of its own,
   `BelieveWhatTheSceneShows`, once the scene has come to rest, and checked at the look.
   In simulation `PieceShoved.apply` writes the shove into the twin, so a belief read at
   the top of the look step already agrees with it and nothing could be violated. All
   four perturbations therefore strike at the LOOK step.
2. **Scene.** `RobotLooksAtTheScene` (settle -> believe -> look -> answer), a scenario of
   its own. The look needs a `SimulatedCamera`, so it cannot go on `TheSceneStandsStill`
   (which runs on the robot), and `PiecePushedWhileTheRobotIsIdle` moves a piece in its
   own script, which would break the belief with no perturbation applied.
3. **Scoring.** `BeliefAgreesWithPerception` answers `bool`. A tuple of relations cannot
   be compared against a ground truth derived from *whether* a piece was perturbed, and
   `DetectionRelabelled` violates no relation at all while still disagreeing (it leaves
   the look reporting none of that shape).
4. **Pairing a sighting with a belief.** By shape and nearest to where the piece was
   believed (`MontessoriScene.shape_nearest_to`). Colour cannot do it: the cube and the
   cylinder are drawn in one colour and the two prisms in another. A simulated look also
   reports the odd spurious piece, which is what "nearest" is for.
5. **The question carries relation *kinds*, not relations.** A relation names the place it
   is read against by the frame that place was measured in, and the world holding that
   frame is gone by the time a recorded query is read back - carrying the relations makes
   `RecordedTrialDAO.from_dao` raise `MissingWorldError`. Confirmed against the database
   before settling on the kinds.
6. **`DetectionRelabelled.pieces_acted_on` names only the piece that is really there**,
   not the shape it is reported as: the robot's account of that other shape is of its own
   piece standing where it stands, and a second sighting elsewhere leaves it as true as
   it was.

## Done

1. `Expectations.standing_on`, `Expectation.believed_place`, `NothingSaysWhereItStands`.
2. `MontessoriScene.shape_nearest_to`.
3. `BeliefAgreesWithPerception` in `experiments/questions/working_memory.py`.
4. `SortingStep.BELIEVE`, `BelieveWhatTheSceneShows`, `LookAtTheScene.reports`,
   `SortingScene.surface_under` + `table`, `NothingHoldsThePieceUp`,
   `SortingPerturbation.pieces_acted_on`, `RobotLooksAtTheScene`/`TracyLooksAtTheScene`,
   and `WatchedSortingRun.belief_questions` recording each report through the observer.
5. `record_episode`'s `robot-looks-at-the-scene` choice.
6. Verified the "done when": four episodes recorded to sqlite (none, piece-shoved,
   perceived-pose-offset, detection-relabelled) and `generate_paper_figures.py` run over
   them. Support-and-spatial-relations went from 12 measurements to 28 - the extra 16 are
   4 pieces x 4 episodes of belief checks, all scored correct. Ran on the test dataset's
   grasping robot rather than Tracy, whose description is a ROS package this container
   has none of.

## Environment notes for a later session

- `uv sync --extra dev` (needs a newer uv than the image's: `pip install -U uv`, then
  `python3 -m uv sync --extra dev`).
- The ORM build resolves a type hint that imports ROS packages, so it needs a stand-in:
  a `sitecustomize.py` on PYTHONPATH installing a permissive meta-path finder for
  `rclpy`, `*_msgs`, `*_srvs`, `*_interfaces` and friends. Scratchpad only.
- Run pytest with `--orm-build=never` once the interfaces are built.

## Next

- **Merged.** PR #325 is merged into `claude/icra-experiments-simulation-pipeline-w4ep7n`
  (#265) as `3e41b69e29`, after CI came back green: the re-run of
  `test_each_lib (experiments)` passed (16:48-17:14), so the earlier crashed xdist worker
  was non-deterministic resource pressure rather than a deterministic failure. Marked
  ready and merged through the API, as chosen. Nothing left for this session.

## Outstanding

- **The experiments CI crash was a flake, now resolved.** It cleared on a re-run of the
  same commit with nothing changed, which rules out the deterministic-failure reading.
  The resource-pressure hypothesis below stands unproven but is now moot for this branch;
  worth remembering if that module starts crashing more often, since this branch does add
  ~5 MuJoCo camera renders to the experiments suite. Original analysis kept: nothing in
  `test_tracy_pickup_demo_mujoco.py` or `pickup_demo_mujoco.py` reaches any symbol this
  branch changed (grepped). The base branch's own last CI run was red on the *same
  module*, but with 4 assertion failures about camera pose and believed places, and that
  run is 15 commits stale - including "Stand the simulated camera where the captures say
  the real one stood" and "Say which description the camera constant is calibrated
  against", which plainly address those very assertions. So the 4 assertions were most
  likely fixed on the base and what remains on this PR is a *different* symptom, which I
  cannot call pre-existing. The plausible mechanism by which it could be this branch's
  doing is resource pressure: the new tests add ~5 MuJoCo camera renders to the
  experiments suite, running under xdist beside a heavy MuJoCo demo, and the crash hit
  `gw0` while `gw1` was mid-test. Cannot be reproduced locally - that module needs
  Tracy's description, a ROS package this container lacks.
- Tracy's own description cannot be built here, so
  `record_episode.py --scenario robot-looks-at-the-scene` is exercised only as far as the
  choice resolving to `TracyLooksAtTheScene`; the run itself was verified on the
  synthetic grasping robot.
