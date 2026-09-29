# claude/pensive-albattani-2j50zr — draft PR #472 (plan general-video-production, item video-core)

Goal: a general, already-usable `experiments.video` package on main, extracted from the
ICRA video PR #429 (branch claude/the-icra-video-shows-the-plan-being-answered, base
real-experiments-tracy-icra-2026), proven by a test that renders a minimal video.

Done (86dcf114):
- Branch re-cut from main (it had descended from `integration`).
- Package: timeline (+HeldScene), narration (wave I/O via stdlib, isinstance instead of
  hasattr), encoding (no icra_2027; byte_budget_for), cache, canvas (neutral inks),
  lettering (Face/font only), footage (general half + VideoFilm), slides (TextCard,
  ResultsTable/ResultRow), production (VideoProduction, Subtitling, EncoderPreset), README.
- pyproject: imageio-ffmpeg, matplotlib, numpy, opencv-python, pillow; `video` extra = kokoro-onnx.
- 75 tests pass locally (--noconftest, minimal venv); minimal 720p video rendered and inspected.

Next / open:
- CI on #472 not yet seen.
- icra-video-on-core (#429 rebuilt on this package) once this reaches the ICRA base branch;
  #429 will need: Ink backend colours as its own enum, icra_2027 as a constant,
  EndCard -> TextCard, Still/held_for kw-only, ResultRow from slides, paper.lettering Face from video.lettering.
