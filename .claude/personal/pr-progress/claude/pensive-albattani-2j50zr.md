## #472 video-core: review round (2026-10-12)

Plan item: general-video-production / video-core.

Done (e6447b6af, 127 tests pass locally with --noconftest; cram2/main merged in bab5c6c98):
- Frame dataclass with drawing methods; SemDT Color/Point2/PlanarBoundingBox; timedelta
  everywhere; NarratedTimeline = Role[Timeline]; FootageFrame = Role[Frame];
  exceptions.py; constants -> fields/enums; narration/canvas/footage split <400 lines.
- 43 threads replied and resolved; 7 left open for the reviewer (Pygments, presentation
  library, Framing as a box, InsetStill name, test literals, SemDT depth/width naming,
  code-formatting parts).
- PR description updated; PR is a draft.

Next: nothing planned; waiting on the reviewer for the open threads. CI risk: ORM
generation for experiments (Role classes, Color fields) could not be run locally (needs ROS).
