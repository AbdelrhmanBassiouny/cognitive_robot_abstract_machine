# `surface-finish-annotation` — PR #216 (draft), branch `sdt_surface_finish_annotation`

Plan item `surface-finish-annotation` of `knowledge-directed-perception`
(tracking issue #201). Kicked off in `auto` mode; branch is off `main`, no
dependencies. Full reasoning is in the plan's `roadmap.md` section of the same
name — this note is the live state.

## The plan

1. `SurfaceFinish(StrEnum)` — `MATTE` / `GLOSSY` / `MIRROR` — in
   `semantic_digital_twin/src/semantic_digital_twin/world_description/geometry.py`,
   beside `Color` and `Texture`.
2. `Shape.finish: Optional[SurfaceFinish] = None`. `None` means *not stated*,
   deliberately distinct from `MATTE`.
3. `Shape.to_json` writes it; `Shape.arguments_from_json` reads the fields
   `Shape` itself declares once, so `Sphere` / `Cylinder` / `Box` stop repeating
   the `origin` / `color` / `texture` read a fourth time.
4. `Mesh.from_trimesh` gains a `finish` parameter and `Mesh._from_json` passes it
   through — a mesh has no other carrier for it, unlike colour (vertex colours)
   and texture (trimesh visual), both of which stay unrestored as they are today.
5. Tests first, in `test/semantic_digital_twin_test/test_geometry/test_shape.py`,
   parametrized over all four shape classes.
6. Regenerate the ORM interfaces and report honestly whether that runs here.

## Done

- Branch cut off `main`, pushed; draft PR #216 opened with the `Deliberately not
  here` exclusions written into its description.
- Manifest: `branch`, `session`, `pull_request_number`, `status: in_progress`.
- Roadmap section recorded.

## Next

- Write the failing tests, then the implementation, then re-run.
- Keep #216 a draft and its description matching the work.

## Decisions already recorded (do not re-litigate)

- No adapter infers a finish from MuJoCo `specular`/`shininess`/`reflectance` —
  that means inventing thresholds against hardware nobody here can inspect.
- A derived supporting-surface `Region` does not inherit its body's finish;
  `calculate_supporting_surface` works off the *combined* mesh, so there is no
  one shape to take it from. Flagged for `detect-per-supporting-surface`.
