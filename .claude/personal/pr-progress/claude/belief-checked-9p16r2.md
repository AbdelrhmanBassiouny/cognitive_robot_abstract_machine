# claude/belief-checked-9p16r2 - "Do your eyes and your belief agree?"

Based off `claude/claude/icra-experiments-simulation-pipeline-w4ep7n` (#265), which
already carries the episode observer.

## What this answers

The paper's belief/perception cross-check, spelled with the expectation machinery that
already exists (`segmind.expectations`, `experiments.montessori.perception.expectations`)
rather than with a router or a cross-check class of its own.

## Design calls I made (asked, told "what do you recommend")

1. **Belief timing.** The belief is taken when the scene has come to rest
   (`LetTheSceneSettle`) and checked at the look (`LookAtTheScene`), not derived inside
   the look step. In simulation `PieceShoved.apply` writes the shove into the twin, so a
   belief read at the top of the look step already agrees with it and nothing could be
   violated. All four perturbations therefore strike at the LOOK step.
2. **Scene.** A scenario of its own, whose script is settle -> look -> answer. The look
   needs a `SimulatedCamera`, so it cannot go on `TheSceneStandsStill` (which runs on the
   robot), and `PiecePushedWhileTheRobotIsIdle` moves a piece in its own script, which
   would break the belief with no perturbation applied. `SupportedBy` is derived from
   whichever surface the twin has each piece resting on.
3. **Scoring.** `BeliefAgreesWithPerception` answers `bool`. A tuple of relations cannot
   be compared against a ground truth derived from *whether* a piece was perturbed, and
   `DetectionRelabelled` violates no relation at all while still disagreeing (it finds
   nothing). The relations that were checked stay on the question, so the record keeps
   them.
4. **Pairing a sighting with a belief.** By shape and nearest to where the piece was
   believed. Colour cannot do it: the cube and the cylinder are drawn in one colour and
   the two prisms in another, so a relabelled cube keeps its colour. A simulated look also
   reports the odd spurious piece, which is what "nearest" is for.

## Plan

1. `Expectations.standing_on` and `Expectation.believed_place` in segmind.
2. `MontessoriScene.shape_nearest_to`.
3. `BeliefAgreesWithPerception` in `experiments/questions/working_memory.py`.
4. The settle/look wiring, the new scenario, and the observer recording.
5. `record_episode` choice, one episode per perturbation, the bucket table.

## Done so far

- Branch cut off #265's tip.
- Read the whole path: segmind + montessori expectations, the perception backend, the
  scenarios, the observer, the question set, the paper figures.
- Got the suite runnable in this session: `uv sync --extra dev`, plus a throwaway
  `sitecustomize.py` on PYTHONPATH standing in for the ROS packages this container has
  none of (the ORM build resolves a type hint that imports them). Scratchpad only,
  nothing in the repo.
- Probed the risky assumptions: a simulated look finds all four pieces within ~1e-5 m of
  the twin and names `montessori/table` as their surface; `is_supported_by` separates the
  table from the board; `Point3` from `global_transform.to_position()` is a snapshot; and
  relations round-trip as JSON.

## Next

Step 1: the failing segmind test for `standing_on`.

## Outstanding

- Nothing yet.
