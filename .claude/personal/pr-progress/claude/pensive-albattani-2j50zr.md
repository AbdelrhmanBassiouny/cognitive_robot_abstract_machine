## #472 video-core: folding in Naren's template features (2026-10-07)

Plan item: general-video-production / video-core. Write-up:
https://claude.ai/artifact/TiTcfZbU2wQnNasrodhFZ5

Plan (TDD, one commit per feature):
1. Line.pace (multiplies the voice's speed, part of the speech cache key);
   Voice.speaks(text, pace).
2. Speech trimmed of silence and levelled to one peak in KokoroVoice.
3. Timeline overlays + ProgressBar overlay across the whole video.
4. CaptionStyle: BandCaption (current) and BoxedCaption (dark box over picture).
5. Theme (colours + Typeface) replacing Ink; NEUTRAL_THEME default, DARK_THEME
   from Naren's palette; slides and captions drawn in a theme.
6. VideoProduction takes overlays and a caption style; README updated.

Decision taken: neutral theme stays the default (no change for ICRA video);
DARK_THEME available. Naren writes manim-scenes on top of #472.

Done: -
Next: tests first for 1.
