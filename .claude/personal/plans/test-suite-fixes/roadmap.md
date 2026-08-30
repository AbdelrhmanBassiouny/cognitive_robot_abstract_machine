# Test-suite defects found while landing the RDR stack — Roadmap

Narrative half of `test-suite-fixes`. One of seven plans the oversized
`rdr-refactor` was split into on 2026-08-30; the predecessor's full 3,259-line
roadmap remains in the personal-notes branch's history immediately before that
split commit.

## Why this is its own plan

These three items are repository-wide test-suite work. The RDR stack surfaced
them — a 49-line `krrood` diff went red on a physics simulation test, and a
skipped MCRDR test had been riding the bottom of the stack for six weeks — but
none of them is RDR work, none touches `rdr/`, and each lands on `main`
independently of the stack. Keeping them with the engine would have put three
unrelated items in a plan already at the size budget.

## What each item found

**`flaky-marker-rerun-plugin` (#190, merged 2026-08-24).**
`@pytest.mark.flaky` was added to `test_world_sim_state_sync` to make it survive
a settling failure. `pytest-rerunfailures` was in no requirements file and not
in the `dev` extra CI installs, so pytest treated the mark as unknown and ran
the test exactly once — failing the very run the mark was added to survive. One
line in `pyproject.toml`.

**`mcrdr-stop-only-flaky-skip` (#189, closed unmerged 2026-08-22).** It proposed
extending a skip that should never have existed.

**`pytest-conversion-sweep`.** The `unittest` modules outside `test_eql_rdr`.
The modules *inside* it are being converted on the stack slices that own them,
which is where the reviewer asked for them.

## Decisions that still bind

**1. A guard test asserts the property this repository owns, not a third
party's.** The first version of #190's test asserted the *rerun behaviour*, by
failing on the first attempt and passing on the second through a session-scoped
counter. It passed on plugin 16.1 and failed on 10.3, with the rerun happening
in both, because older versions tear the session fixture down between attempts —
so it was really asserting the plugin's fixture-teardown semantics. Trimmed to
assert only that the plugin is loaded, which is what actually regressed and what
this repository controls. A test whose mechanism depends on a third party's
internals looks like coverage and is really a version probe.

**2. A bare mark needs nothing else.** Measured on the pinned pytest 7.4.4: with
the plugin installed a bare `@pytest.mark.flaky` gives one pass and one rerun;
without it, one failure and an unknown-mark warning. So neither a rerun count,
nor `--reruns`, nor a `pytest.ini` `markers` entry was ever missing — only the
dependency. This corrected an earlier reading in this same programme that said
all three were needed.

**3. A dependency or configuration fix on a fork needs the upstream check
*before* it is opened.** Checked after the developer asked: upstream `cram2`'s
main was at the same commit, its `dev` extra byte-identical, no rerun plugin
anywhere in its requirements or workflows. So the defect is upstream's own, the
fix is not a duplicate, and it belongs promoted upstream. Had it already been
fixed there, #190 would have been a duplicate that conflicts on the next sync.

## The finding worth keeping

**The "flaky" MCRDR test was never flaky, and the label spread before anyone
checked.** A skip was applied on 2026-07-10 blaming a nondeterministic
interaction count. A 900-run sweep over `PYTHONHASHSEED` — both siblings
individually, plus whole-class runs — passed every time. The real cause was in
the history: on 2026-07-15 a commit fixed every `.py` fixture's answer
delimiter, which used double quotes while the expert loader has always split on
single ones, so the loader silently returned one answer instead of eighteen and
the run fell through to a live prompt. Reproduced by restoring the pre-fix
fixture: the exact CI symptom. The failure was deterministic, and it was fixed
five days after the skip went in.

Both skips are now gone. The propagation is the part worth remembering: a
resolve session dutifully carried the skip to a sibling, because an unreproduced
"flaky" label reads as a landed decision rather than an open question. **A skip
whose cause was never reproduced should carry an expiry, or at least a pointer
to the run that justified it.**

One fact carried forward: the MCRDR test consumes exactly all eighteen recorded
answers, so it runs with zero margin by construction. Any change to
`MultiClassRDR`'s interaction count breaks it with a cannot-prompt error rather
than a useful one.

## Open

- **`pytest-conversion-sweep` has not started** and has no branch. Its scope is
  the `unittest` modules outside `test_eql_rdr`; the seven inside it belong to
  the stack slices that own those files.
- **#189's branch is kept rather than deleted**, so nothing has to be redone if
  the question is ever revisited. Its status is `deferred` rather than `done`
  because that is the one terminal status the dashboard does not flag as drift
  against a closed-unmerged pull request.

## Standing conventions

- Follow `.claude/personal/cram-notes.md` and this repository's `AGENTS.md`.
- TDD: failing test first, and no test is modified to make something pass.
- Never skip, disable or quarantine a test to get a run green.
- Stage by explicit path, never `git add -u`: a sweep regenerates
  `ormatic_interface.py`, `query_graph.pdf`, `drawer_explanation.pdf` and
  `verbalization_results.py`, and a dirty tree after a sweep is the normal state
  here rather than a signal to commit.
- A long parallel sweep and an interactive experiment must not share a checkout.
  Five contiguous "failures" in the 900-run sweep were a fixture-swap experiment
  running against the same working tree; the contiguity is what gave it away.
