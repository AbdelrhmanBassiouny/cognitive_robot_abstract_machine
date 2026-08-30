## PR #151 — manifest-currency-first (plan `stack-maintenance`)

**Where it stands (2026-08-30).** Unblocked. The branch had been conflicted
against `main` since 2026-08-12 and skipped by eight maintenance passes; the
merge is resolved and pushed as `fb1a5a4a`, and GitHub now reports the pull
request `unstable` rather than `dirty`. Back in draft.

**Done this round**
- Resolved seven conflict hunks in six files. The reasoning per file is in the
  pull request's *Update 2026-08-30* section — read it there rather than
  restating it here.
- Added `add-plan-item`'s currency-rule citation. This was the line the
  description recorded as deferred until #135 landed; #135 merged on 08-22, so
  the merge brought the skill in and this branch's own contract test failed for
  it. 599 dev-tooling tests pass, was 598.
- Recorded the real blocker on the item before resolving it, then cleared it and
  set `status: in_progress`; added the label-skips-a-branch rule to the roadmap
  and republished the dashboard.

**Next, and what is not mine to decide**
- CI on `fb1a5a4a` was still running when this session ended. It was green on
  the previous head across all 21 checks and the merge is `.claude/`-only, so a
  failure would be a surprise rather than an expectation.
- Four review threads stay open on purpose, each answered and waiting on the
  user: the wire-format test literals, the `classproperty` reversal, the
  `render_common.py` filter-name question, and the blocker-ownership one.
- `update` writes item fields at the wrong depth against every real plan.
  #160 fixes half of it from `main`; the half this branch introduces
  (`render_sequence_entry`, the block-body indent) is out of #160's reach. Which
  pull request takes it is an ordering call for the user — see the pull request's
  own section. Do not duplicate `ItemIndentation` across both.
- The `needs-resolution` label is left on deliberately; the next maintenance pass
  clears it now that GitHub reports no conflict.
