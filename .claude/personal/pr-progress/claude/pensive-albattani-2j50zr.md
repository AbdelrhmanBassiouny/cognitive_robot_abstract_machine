## #472 video-core (plan general-video-production / video-core)

Plan:
- Answer each review round inline, resolve only what is done. Upstream PR is cram2#742.

Done:
- Package is crollywood (renamed from cramcorder, ee1e7bdad), answering upstream round 1:
  renames, SoundChannel, crollywood.submission + VideoFile.check_within, Kokoro StrEnums,
  NDArray, full_view. 150 crollywood + 10 krrood unit tests pass (--noconftest).
- #471 lists what #429 and manim-scenes must follow; fork PR labelled in-review.

Next:
- tomsch420 re-review on cram2#742; open there: timeline-scene modelling.
- Fork threads await the user: AxisAlignedBox as Bounds, tuples, presentation library,
  Framing box, InsetStill/FootageScene names, test literals, SemDT depth/width, cache
  constants, LICENSE, voices str, Video vs Film.
