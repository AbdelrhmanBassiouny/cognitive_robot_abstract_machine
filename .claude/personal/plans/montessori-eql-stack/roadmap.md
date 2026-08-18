# montessori-eql-stack — narrative

## What this stack is

Six stacked PRs on the fork, one strict chain (each branch based on the
previous), turning the Montessori demo into an interactive, queryable, spoken-to
system:

`main` → #169 `montessori_fast_inline_monitor` → #170 `cramera_eql_autocomplete`
→ #164 `montessori_eql_where_is_highlighting` → #165 `montessori_event_replay`
→ #167 `claude/cramera-verbalization-voice-ttwcza`
→ #168 `claude/cramera-voice-questions-ttwcza`

It is registered as native GitHub stack **#173** (created 2026-08-18). The two
`claude/…-ttwcza` branches carry auto-generated session slugs, so their plan
item ids are the readable `cramera-question-readback` / `cramera-voice-questions`
instead of the branch names.

## History that explains the current shape

- **2026-08-18: the stack was re-ordered.** Originally #164→#168 stacked
  directly on `montessori_fast_inline_monitor` (GitHub stack #166), and
  `cramera_eql_autocomplete` (#170) sat beside them in a separate stack (#171:
  #169→#170). The developer asked for the whole montessori chain to be rebased
  onto `cramera_eql_autocomplete`, inserting the autocomplete work underneath
  it. All four branches were rebased and force-pushed; all four tips passed the
  cramera suite (488/540/562/594 tests respectively).
- **The reparent of #164 required dissolving its native GitHub stack** (a base
  change on a stack member 422s): stack #166 was recorded, unstacked, #164
  retargeted, and the stack re-created — then, on the developer's request,
  merged with #171 into the single unified stack #173. The pre-dissolve records
  live in the creating session's scratchpad (`stacks-before-unstack.json`,
  `stacks-before-merge.json`); the procedure is the one in
  `.claude/skills/stacked-pr-maintenance/SKILL.md`.
- **#167 had been stale-stacked** (built on pre-rebase copies of #164/#165
  commits). The restack kept only its two real commits. One semantic conflict
  git could not see: its `test_eql_panel.js` harness binds the panel's free
  variables explicitly and needed an `EqlSuggestions` stub once the
  autocomplete feature sat below it — amended into the harness's own commit.
- **The scenes submodule pin conflict** in #167's "Pin the scenes submodule"
  commit was resolved by keeping the base line's `64b98eda` (public cram-scenes
  main, which already contains the `2230683` that commit originally pinned);
  that commit now only carries its test-skip change and its message is
  slightly stale about the pin.

## Standing conventions

- Per-branch working detail (test baselines, environment landmines, round
  notes) lives in `.claude/personal/pr-progress/<branch>.md` on the
  personal-notes branch — notably
  `pr-progress/cramera_eql_autocomplete.md`, which carries the full
  Round 1–4 history for #170 including the local-environment fixes (lark
  rename, semantic_digital_twin ORM duplicate table, costmaps inflation OOM,
  detector-test reference frames). That mechanism keeps working independently
  of this plan; it is not duplicated here.
- #169 and #170 are ready-for-review; #164–#168 are drafts, per the
  draft-until-told-otherwise convention in the personal notes.
- Landing order is the stack order; nothing here is parallelizable, which is
  why the plan is one wave / one track with a chained `depends_on`.
