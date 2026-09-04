# expectations-from-events (#257, draft) - knowledge-directed-perception

Kicked off and built 2026-09-03 in `auto` mode; review round and re-base of 2026-09-04
resolved the same day. Branch `claude/plan-item-kickoff-expectations-2zvpmn`, now cut from
#255 (`claude/knowledge-directed-perception-imagination-g9hsnr`) with #246 merged in; the
pull request's base is #255. Full reasoning is in the plan's `roadmap.md` sections of the
same name.

## Done

- The re-base (2ea13b3c): the one conflict, `reasoning/predicates.py` against #244's
  numeric rewrite, resolved by carrying #244's fast paths into #229's classes.
- The rewrite (3dddd76e, 0fab8101): `Expectation.holds` is `StatedRelation`s of the twin's
  vocabulary; `contradicted_by` with one `SightingReading` per kind the look establishes;
  `Turned` in the twin; `Effect`/`EventWithEffect` on the Segmind events; `SceneRequest`
  seeds a fit from `believed_stretch()` on `believed_by`'s say-so; the sweep grid actually
  anchored (`placements_within`); `supporting_surface` as the entity.
- Replied on every thread the developer answered and on his review comment; resolved the
  five done as asked; `look_for` proposed on #222 (issuecomment-5546880894).
- Manifest, roadmap, new item `predicted-state-from-declared-effects`.

## Next

- Nothing on the branch. CI on 0fab8101 unread; the `probabilistic_model` check was red on
  the old base and `main`'s fix is under this base too.
- Whether `look` becomes `look_for` is decided on #222.
- The lid marks stay four; a history reaches two of them, and the rest is
  `competing-explanations`'.

## Watch out

- #236 and #239 edit `pipeline.py` and `piece_matcher.py` on the other stack and meet
  `believed_from`, `placements_within` and the request seeding when the merge reaches them.
- Every later merge of #246 into the #238 stack meets the same `predicates.py` conflict;
  take 2ea13b3c's resolution.
- `plan_item_bootstrap.py update` is not in this checkout; the manifest was edited in a
  worktree of the notes branch and saved with `save-plan.sh --manifest --roadmap`.
- Segmind's tests need the root `conftest.py` (apartment fixture); run them without
  `--noconftest`.
- Fetch the notes branch immediately before every save.
