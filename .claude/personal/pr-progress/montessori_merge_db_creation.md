### Next
- `cramera/scenes` is a submodule: `Franka_Montessori/presets.json` needs its own
  commit in `cram2/cram-scenes`.
- Not done, deliberately: persisting the diagnosis (`ShapeInsertionAttempt` gains no
  fields; would need `scripts/regenerate_all_orm.py` + a migration). Live-only was
  the chosen scope.
- Flagged, not fixed: `target_horizontal_offset` is persisted and documented but
  `_action_plan` never reads it, so every attempt aims at the hole centre.
