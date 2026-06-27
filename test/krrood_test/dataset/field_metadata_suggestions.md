# Field metadata — suggestions

> **Provenance:** this is a small **hand-authored seed** demonstrating the format. Regenerate it
> (and the runtime `field_metadata.json`) with
> `python -m krrood.entity_query_language.verbalization.tools.generate_field_metadata`
> (requires `ANTHROPIC_API_KEY`); review the resulting diff before committing.

The `display_name` column feeds the runtime artifact (`field_metadata.json`); `suggested_rename`
is **advisory** — adopt it in the source or not.

## GraspConfig

| field | display_name | suggested_rename | confidence | rationale |
|---|---|---|---|---|
| `rotate_gripper` | gripper rotation | `gripper_rotation` | medium | Verb-phrase field name reads as an action; the value is a rotation amount, so a noun phrase verbalizes better. |
| `approach_direction` | approach direction | — | high | Snake_case expanded to spaced words. |
| `manipulation_offset` | manipulation offset | — | high | Snake_case expanded to spaced words. |

## MoveAction

| field | display_name | suggested_rename | confidence | rationale |
|---|---|---|---|---|
| `grasp_config` | grasp configuration | `grasp_configuration` | medium | Abbreviation expanded for readable prose. |
| `hip_rotation` | hip rotation | — | high | Snake_case expanded to spaced words. |
| `robot_x` | robot x | — | low | Coordinate field; minimal spacing only. |
| `robot_y` | robot y | — | low | Coordinate field; minimal spacing only. |
