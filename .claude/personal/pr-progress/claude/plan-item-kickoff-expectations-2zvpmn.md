# expectations-from-events (#257, draft) - knowledge-directed-perception

Kicked off and built 2026-09-03 in `auto` mode; review round of 2026-09-04 resolved the
same day. Branch `claude/plan-item-kickoff-expectations-2zvpmn`, cut from #232 with #222
and #246 merged in. Full reasoning is in the plan's `roadmap.md` sections of the same
name.

## Done

- The build: `perception/expectations.py`, `SceneRequest.expected`, `pipeline.detect`
  evaluating it, `piece_matcher.offsets_within`, the re-pointed lid marks.
- The review round (4c1a1bb7): world entities instead of `PrefixedName` throughout this
  item's own types; a pick-up means held rather than supported (Segmind builds it with no
  `with_object`); event effects declared on the Segmind event classes
  (`SupportEffect`, `EventWithSupportEffect`); `segmind` declared as an `experiments`
  dependency (the red `version` check); docstrings, helper rename, type hints, article.
- Replied on all nineteen threads; resolved the ones done exactly as asked.

## Next

- **The developer's call, asked on the threads and in the session:** re-base this item on
  #255 so an expectation is stated in the twin's own relation vocabulary (#229, #238) over
  a sighting that has a body (#255), which answers the five threads that reach past this
  base. Nothing here should be built a second way before that is answered.
- If yes: re-cut onto #255's tip, merge #246 (conflicts in `predicates.py` and its test,
  #244 against #229), re-apply the three commits, then rewrite `Expectation` as relations
  and `SceneRequest.expected` as the same relations in the statement.
- `probabilistic_model` is red on the base too (`test_jpt`, `Unsupported datatype: str`);
  not this branch's, said once on the pull request.

## Watch out

- `plan_item_bootstrap.py update` works from a checkout that has it (the tooling
  worktree); this branch's own copy predates it.
- The tracking-issue subscription and the artifact watch are both refused for this
  session; read #201 directly.
- `segmind/datastructures/events.py` is now edited on this branch beside #244's changes
  to the same file (different regions).
- Fetch the notes branch immediately before every save.
