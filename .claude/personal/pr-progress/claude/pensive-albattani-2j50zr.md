## #472 video-core: review rounds (2026-10-12)

Plan item: general-video-production / video-core.

Round 1 (e6447b6af): Frame dataclass, SemDT types, timedelta, Role[Timeline], split modules.

Round 2 (d7a86bdf7, cc1b7b499), on the user's request:
- Package moved out of experiments into its own workspace member `cramcorder`
  (authors Abdelrhman Bassiouny, Naren Vasantakumaar; LGPL; `narrator` extra for kokoro-onnx;
  CI matrix lib: cramcorder; tests in test/cramcorder_test; experiments/pyproject back to main).
- 9 new threads: Pixel/PixelBox, WordCuts, muxer Tracks, Voice/Film abstract dataclasses,
  SoundLevel dBFS + sample_rate, PixelFormat/EncoderPreset StrEnums, no ClassVar, FootageScene.
  6 resolved; open: cache ClassVars (answered via StrEnum/parameter/classproperty), FootageScene
  name, Pygments (recommended, waiting for dependency approval).
- 143 tests pass locally (--noconftest). PR title/body updated; draft.

Round 3 (223c6d706): Pygments lexer colours code (KEYWORD, COMMENT added); units.py
(DataSize, generic Rate, BitRate) for every size/bit rate; muxer Language StrEnum;
PixelBox is SemDT Bounds[Pixel]; PixelColor replaces Frame.bytes_of; video.Video base of
Scene/Timeline/VideoFile (Film, VideoFilm gone); EvenCuts replaces nested even_cuts loops;
cache "directory"; test voices SoundLevel + model_path/voices_path. 154 tests pass.
Replies NOT posted: the user's own pending review (id 5500054903) blocks every reply under
their account. Drafts noted in the session scratchpad round3-replies.md; post them once the
user submits their pending review, then resolve the 8 done threads.

Next: post round-3 replies; then waiting on the reviewer (units in krrood?, AxisAlignedBox as
Bounds?, remaining tuples, names, Framing box, test literals, SemDT naming).
