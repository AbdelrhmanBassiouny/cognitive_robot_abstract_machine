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

## Reconciling with Naren's Manim explainer reference (2026-10-07)

Naren built a video template from the same starting point and then went a
different way: Manim draws every scene, narration is a list of beats per scene
(`(caption, spoken, speed)`), `make_voice.py` writes a `timing.json` of speech
lengths that paces each beat's animation, and `assemble.py` joins the scene
renders, pads the audio and writes the SRT. The reference code carries an
unpublished paper under double-blind review, so only its machinery is used.

The two duplicate narration, Kokoro speech, subtitle splitting, SRT output,
joining and encoding; #472's versions are kept. Neither replaces the other's
renderer: #472 builds frames itself (footage, slides, dissolves), Manim animates
diagrams and cannot play recorded footage well. So #472 stays the single
pipeline and Manim becomes one more kind of Scene, timed by the storyboard.

Scope check: the per-line speed, speech trimming and levelling, boxed
subtitles, the video-wide progress bar and the Theme all change files #472
adds (none exist on main), and stripped of those edits there would be nothing
left, so they are folded into `video-core`. The Manim module is new work that
stands on its own, so it is its own item (`manim-scenes`), stacked on #472.
Naren's own video is rebuilt on the package outside this repository.

Shareable write-up: https://claude.ai/artifact/TiTcfZbU2wQnNasrodhFZ5

