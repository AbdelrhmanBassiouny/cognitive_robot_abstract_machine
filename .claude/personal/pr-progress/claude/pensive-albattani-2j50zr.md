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

Next: waiting on the reviewer (Pygments approval, names, Framing box, test literals, SemDT naming).
