# PR #182 - correlate query-rooted attributes (plan `match-query-ergonomics`,
# item `where-query-rooted-attribute-no-filter`)

## Plan (session 2026-08-22, resolve round)

The fix itself is done and survived four review rounds (roadmap §8-§12). One
review thread is open and is the only thing stalling the item:
`discussion_r3828206197` on `mapped_variable.py:280`, asking whether the
`_rerooted_chains_` memo key needs `replaced_id` at all, since the dict is a
per-instance field. The ask is a verification, so the deliverable is a
measurement.

1. Instrument `MappedVariable._reroot_on_`, run the EQL suite, and collect
   `(node id, replaced id, root id)` triples.
2. If no node ever sees two `replaced_id`s under one `root_id`, key the memo by
   the root `UUID` and delete the `Rerooting` dataclass. Otherwise keep the pair
   and reply with the counterexample.
3. Reply inline on the thread; resolve only if the ask was actually carried out.
4. CI: the push re-runs it. The one red job is
   `semantic_digital_twin::test_world_sim_state_sync`, a MuJoCo wall-clock
   settle test, green on the PR's exact base and untouched by this diff.
5. Update `plan.yaml` + `roadmap.md` §14, `save-plan.sh`, republish dashboard.

## Done — the round is complete

- Branch checked out; `main` has not moved off the PR base `90c241168`, so no
  conflict and nothing to rebase.
- Container had no project dependencies at all - built a scratch venv
  (`scratchpad/venv`) on Python 3.12, since Debian's setuptools cannot build
  `antlr4-python3-runtime` and 3.11 is too old for
  `make_dataclass(module=...)`.
- Probe run: 27 `_reroot_on_` calls over 25 nodes, no node ever seeing two
  `replaced` expressions, and `replaced` always the node's chain root (25) or
  its first access-path step (2) - so it is fixed per node by construction.
- `b9825b9e`: `Rerooting` deleted, `_rerooted_chains_` keyed by the root's
  `uuid.UUID`. Full krrood suite identical to baseline (1868 passed; the two
  `test_object_diagram` failures are the missing Graphviz `dot`). Pushed.
- Thread `discussion_r3828206197` replied to with the measurement, then
  resolved - it asked for verification and got it, so resolving is earned.
- PR description updated (memo wording + a landing-order section), plan.yaml
  and roadmap §14 saved, dashboard republished, round recorded on issue #181.

## Next

- Nothing outstanding from this session. CI re-ran on the push; if
  `test_world_sim_state_sync` reproduces, it is not this PR's (see Notes).
- The PR is a draft with no open review threads, waiting on the developer.

## Notes

- Landing-order hazard, recorded not fixed: #186 makes `Index` abstract, and
  this PR's `Index._rebuild_on_` *constructs* `Index` directly. Both #186's
  description and roadmap §13 mention only the `isinstance(step, Index)` check,
  which does still match. Whichever lands second must move `_rebuild_on_` onto
  `IndexByValue` / `IndexByExpression`.
- `subscribe_pr_activity` on tracking issue #181 was denied by the auto-mode
  classifier; #181's comments were re-read directly before the manifest write.
