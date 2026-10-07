## #472 video-core: folding in Naren's template features (2026-10-07)

Plan item: general-video-production / video-core. Write-up:
https://claude.ai/artifact/TiTcfZbU2wQnNasrodhFZ5

Done (pushed 455968e9, 100 tests pass locally with --noconftest):
- 1ca3a28a Line.pace, Voice.speaks(text, pace), Line.spoken_by; KokoroVoice
  trims silence (BREATH_BEFORE/AFTER) and levels to SPEECH_PEAK, both in the key.
- e0847672 VideoTheme (colours + Typeface) replaces Ink/CODE_INK; NEUTRAL_THEME
  default, DARK_THEME from Naren's palette; slides/CodeTypesetting take a theme;
  footage uses FOOTAGE_TEXT/FOOTAGE_BADGE; Face is a role.
- 2f9a2495 timeline.Overlay + Timeline.overlays; overlays.ProgressBar;
  CaptionStyle (BandCaption, BoxedCaption) on Subtitled; VideoProduction takes
  captions= and overlays=, picture_of names what is encoded. README updated.
- 455968e9 renamed Theme -> VideoTheme (sdt has a class Theme; the ORM
  generator resolves hints in one namespace of all scanned classes).
PR description updated; PR still draft.

Decisions: neutral theme stays default; Naren writes manim-scenes on top of
this branch.

Next: watch CI on 455968e9 (ORM generation step is the known risk); nothing
else planned for this PR unless review asks.
