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
Replies posted after the user submitted their pending review (it had blocked them):
8 resolved (Pygments x3, cache directory, Language, bytes, EvenCuts, SoundLevel); 7 left open
(tuples left, PixelBox/Bounds x2, units home, LICENSE, voices str, Video vs Film).

Follow-up (24208b31c): PixelColor removed, SemDT Color.to_rgb_bytes added (to_hex uses it);
Color thread resolved. Discussion replies left open: Scene as Role[Video] (Timeline/VideoFile
stay kinds of Video), Quantity[T] generic magnitude instead of Role[int].

Next: waiting on the reviewer (Scene as Role[Video]?, Quantity[T]?, units in krrood?, AxisAlignedBox as
Bounds?, remaining tuples, names, Framing box, test literals, SemDT naming).
