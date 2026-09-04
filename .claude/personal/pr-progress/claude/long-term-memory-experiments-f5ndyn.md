## branch: claude/long-term-memory-experiments-f5ndyn

**No pull request, and none expected.** This session's work was a manifest
change to the `icra-experiments` plan, not code. The branch was re-cut from
`main` (it had descended from `integration`) only to clear the setup check;
nothing is committed on it.

**Done, 2026-09-04.**
- Answered where the long-term-memory items were: three exist in the
  `long-term-memory` track, plus `segmind-detectors-on-the-demo-branch`, which
  is `done` and so hidden by the dashboard's default toggle. What was missing
  was an experiment that scores any of it.
- Ran `/add-plan-item`. Setup first (dashboard deps installed, branch re-cut).
  Scope check found no in-flight branch owning this work.
- Added to `icra-experiments`: track `experiment-d`, and the items
  `episode-artifacts-recorded`, `cross-episode-question-set-and-ground-truth`,
  `episode-corpus-given-whole-to-the-vlm`, `experiment-d-in-simulation`.
  Amended `episodes-recorded-through-ormatic` (record how a failure was
  resolved) and `vlm-baseline-harness` (take an assembled context). Plan title
  and description now say four experiments. 28 items to 32.
- `save-plan.sh` pushed it; dashboard republished; the structural change is
  recorded on tracking issue #252.

**Open, for the developer.**
- `roadmap.md`'s twelve-day budget table still covers three experiments. The
  fourth is not in it, and re-budgeting is the developer's call.
- The open question about which VLM and provider now also has a second part:
  how many episodes fit one context once video frames are sampled, which is
  what sets Experiment D's cap.

**Next.** Nothing pending in this session. Work starts with
`/plan-item-kickoff icra-experiments episode-artifacts-recorded` once its two
dependencies are ready.

*Note: the artifact wake subscription for the dashboard failed to register
(the artifact service refused it for this session), so this session is not
watching it.*
