# PR plan: montessori/why-demo — narrated demo (Montessori track, M2)

Not started. Base: `montessori/choice-policies` (M1) with
`eql/causal-verbalization` (W2) merged in.

## Goal

The demo loop asks `pick_policy` for each next shape and `hole_policy` per
insertion; after every choice/action it obtains the `WhyAnswer` and prints its
causal verbalization ("I picked the star first because … (rule R)").

## Scope

- Rework `experiments/montessori/montessori_demo.py`: policy-driven loop +
  narration.
- Headless mode (no ROS/Rerun): full sort purely in the world model, emitting
  the narration transcript — this is the CI test. Full sim path (HSRB /
  Multiverse scene) stays as on Tom's branch.
- README: run instructions + example transcript.

## Verification

- Headless CI test asserts each narrated answer names the actually-fired rule
  (compare against `ClassificationTrace`).
- End-to-end sim run locally.
