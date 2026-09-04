### icra-experiments / integrated-simulation-pipeline — PR #265 (draft)

**Done.** Branch cut off `main`, six of nine merge steps in: #244, #256, #262, #229,
#238, #236, plus #223's `RectifiedFootprint` rename applied directly. Draft PR #265 open
and its description matches. Manifest and roadmap written.

**Resolutions taken** (all in roadmap.md and the PR body):
- #262's recording trio beats #256's (dangling refs already repointed).
- `predicates.py` is rewritten by *three* branches; #238's is a superset of #229's, so it
  takes the structure and #244's numeric fast paths are re-expressed over #238's
  redesigned view machinery via a new `unit_axis_of`. #244's four tests hold it in place.
- The perception lineage's montessori `world`/`semantics`/`hole_geometry` beat #256's.
  Cost: `sorting_progress.py` removed (reads four members only the losing copy had).
- `Footprint` → `RectifiedFootprint`, #223's exact identifier, because #262's
  `__init__.py` + the perception package would give ORMatic two `FootprintDAO`s.

**Next, and the one real blocker.** #231 and #223 both fork *before* #236 rewrote
`BoardDetector`, so neither is a text merge. #231 is a design synthesis: its
capability-declaring `EdgeFitDetector`/`ColorBlobDetector` and rule-based
`detectors_for(...)` pipeline vs the perception tip's expectation/colour-narrowed search
with `Occupancy` — ~200 conflicted lines through the core perception loop. Needs a
deliberate pass. #239's cherry-pick (`3a493be9`) waits on #231. Then ORM regeneration and
the branch's own headless integration test.

**Known limit.** Nothing here has been run: the workspace won't install in a session
container (`random_events` C++ lib won't build; ROS imports). Verification was static —
parse, markers, import resolution. CI is the verifier.
