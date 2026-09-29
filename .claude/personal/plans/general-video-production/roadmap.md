# General video production for experiments

## Why

The ICRA 2027 supplementary video (#429) built a complete video pipeline in
`experiments.video`: scenes on a timeline with dissolves, two-pass H.264 to a
byte budget, a narrator with subtitles, typesetting, footage framing. Only
about a third of it is specific to that paper, yet all of it sits on
`real-experiments-tracy-icra-2026`, 1,165 commits ahead of main, so no other
experiment can use it.

## Split (from the import audit of #429 at 04e898ea)

- General, no ICRA dependency: timeline, encoding, cache, canvas, narration,
  plus `experiments.paper.lettering` (fonts; canvas needs it).
- General after a split: footage (Framing, badges, Film protocol and full-bleed
  scenes are general; CameraFilm reads Montessori bags), slides (EndCard general,
  ResultsTable is ICRA), canvas's `Ink` (neutral vs backend colours), encoding's
  `SubmissionLimits.icra_2027()` preset.
- ICRA only: sources, perception, twin, grasp, rules, attribution,
  perturbations, long_term, script, icra_video, framework.typ.
- Deferred: stages.py and figure.py generalise only behind a figure abstraction.

## Decisions

- The package lands on main first and must already produce a video on its own
  (a minimal narrated video rendered in a test), per the request that started
  the plan.
- Scope check: the package's files are extracted from unlanded #429, but the
  package stands on its own (a usable library with its own tests), so it is a
  separate item rather than folded into #429; #429 shrinks instead.
