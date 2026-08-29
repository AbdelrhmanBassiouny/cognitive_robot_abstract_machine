# `/plan-item-resolve knowledge-directed-perception surfaces-from-world`

This session's branch carries no code of its own. The resolve found #205 healthy and put its
work on the two branches that actually own it.

## What was wrong

#205 was green (23/23 checks), `mergeable_state: clean`, dependency #202 `open_ready`. The one
unresolved review thread - "This is a very big file" on `test_montessori_perception.py` - was
answered by the developer with "ok it should be done on 202", so the work belonged to
`montessori_perception_on_main`, not here. `git ls-tree main` confirms: the file exists on no
branch but #202's.

## Done

- Recorded the real blockers on `surfaces-from-world` **before** doing anything, and republished
  the dashboard - the manifest had said `in_progress` with no blockers while the item sat.
- Split `test_montessori_perception.py` (1262 lines) into six subject modules on
  `montessori_perception_on_main`, `00721be7`, pushed. Every `# %%` section verbatim, all 77
  test functions accounted for, `91 passed` unchanged. Shared fixtures moved to
  `dataset/montessori_scene_fixtures.py`, registered as a pytest plugin.
- Merged the moved base into `perception_surfaces_from_world`, `d6673b48`, pushed.
- Replied on the #205 thread and resolved it; updated both pull request descriptions.
- Roadmap section, manifest and dashboard all updated.

## Deliberate calls

- **#202 left out of draft.** Re-drafting it would show `surfaces-from-world` and
  `perception-backend` as blocked, which is the exact state the recorded decision to open it
  ready exists to avoid.
- **The dead local `region`** in `test_rectified_plane_puts_a_known_point_back_where_it_came_from`
  was left as it is - a pure move should not edit a test body.

## Next, and not this session's

- The widest-face vs highest-face question on `WorkspaceSurface.of_body` is still unanswered.
- #202 has two review threads of its own from 2026-08-29 (empty `__init__.py`, `timedelta` on
  `node.py:134`) that belong to `montessori-perception-on-main`.
