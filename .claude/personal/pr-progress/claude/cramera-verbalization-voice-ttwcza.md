## PR A — verbalization display (draft #167, branch `claude/cramera-verbalization-voice-ttwcza`)

Stacked on PR #165 (`montessori_event_replay`). Status: **implemented, tested,
pushed, draft PR open**. The EQL panel's textarea + Run button are replaced by
a big verbalized-question display; presets travel worded (recorded scene per
its runner, live bridge per declared scope); `EqlQueryRunner.build()`/
`verbalize()` added. Full cramera suite: 472 passed.

Follow-up work continues in PR B (#168, branch
`claude/cramera-voice-questions-ttwcza`, stacked on this one): voice capture +
question matching. Both PRs are drafts; see that branch's progress note.

### Outstanding
- CI not checked on #167 (session ended before CI ran).
