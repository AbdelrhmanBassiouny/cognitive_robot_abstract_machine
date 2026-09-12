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

- Nothing outstanding on the branch itself. Both commits pushed, PR #325 description
  brought up to date, left as a draft. Awaiting review.

## Outstanding

- Tracy's own description cannot be built here, so
  `record_episode.py --scenario robot-looks-at-the-scene` is exercised only as far as the
  choice resolving to `TracyLooksAtTheScene`; the run itself was verified on the
  synthetic grasping robot.
