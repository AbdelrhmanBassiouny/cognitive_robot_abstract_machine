# Plan handover

Instructions for continuing 3 handed-over plans. Each item below is one pull
request's worth of work: what it does, where it stands, what it builds on and what is
already known about it.

If `basstler` is installed, do not follow this file: run `basstler plan-handover import`
from a checkout of your fork of the project, or of the repository below if you push to it,
instead.

| Plan | Items | Underway | Not started |
| --- | --- | --- | --- |
| [Split the Montessori perception package's landing into reviewable layers](#plan-montessori-perception-split) | 7 | 1 | 6 |
| [Knowledge-directed perception: scene grounding](#plan-knowledge-directed-grounding) | 8 | 7 | 1 |
| [Knowledge-directed perception: query language and method selection](#plan-knowledge-directed-requests) | 15 | 10 | 4 |

## Rules

- Read the project's `AGENTS.md` (else `CLAUDE.md`) before changing anything.
- Follow the standing rules of the item's plan. They bind every item as much as its own notes.
- Work one item per session. Plans are listed after the plans they depend on.
- Underway items live on branches of
  [AbdelrhmanBassiouny/cognitive_robot_abstract_machine](https://github.com/AbdelrhmanBassiouny/cognitive_robot_abstract_machine).
  Continuing one means pushing there; without write access, push the branch to your fork
  and open its pull request again from there.
- The sessions that started these items cannot be opened. What they decided is in each
  item's notes, its progress note and its pull request.

## Working an item

1. Check its dependencies: start it once they have merged, else stack it on the branch of
   the one that has not.
2. If it has a branch, check it out and build on it. Read its pull request, its
   description, every unresolved review thread, and its progress note.
3. If it has no branch, cut one from that unmerged dependency's branch, else from the
   default branch, and open a draft pull request.
4. Read the comments on the plan's tracking issue: structural changes to the plan are
   posted there.
5. Plan the change with tests first, implement it, and keep the pull request's
   description and the progress note true to the work.

<a id="plan-montessori-perception-split"></a>
## Plan `montessori-perception-split`: Split the Montessori perception package's landing into reviewable layers

#202 lands the Montessori perception package on main as one 65-file, +11,220-line pull request. Its import graph cuts cleanly into layers that each stand on main plus the layers below them, with their own tests. This plan builds those layers as a stack of pull requests, each holding exactly #202's final file contents, and ends with #202 itself retargeted onto the stack so that it shows only the ROS runtime. No history is rewritten, so every branch already stacked on #202 stays valid.

Tracking issue: [AbdelrhmanBassiouny/cognitive_robot_abstract_machine#486](https://github.com/AbdelrhmanBassiouny/cognitive_robot_abstract_machine/issues/486).
Plan files: [`plans/montessori-perception-split`](plans/montessori-perception-split).

### Standing rules

- `network_limits` is its own pull request off `main`, not the bottom of the stack.
- The ~3,560-line detection layer is cut in two (5a/5b).
- #202 is kept and becomes the top layer. It is not closed and replaced.
- Layers 4 and 6 need only `main` and layer 4 respectively, but are still stacked in a line. That gives every branch a single parent, so no base is a merge of two branches.

<a id="montessori-perception-split--shape-vocabulary-on-main"></a>
### `shape-vocabulary-on-main`: Land the Montessori shape vocabulary, the board's hole geometry and the piece set

- **Status:** in progress
- **Recommended model:** sonnet
- **Branch:** `claude/ecstatic-knuth-curscv`
- **Pull request:** [AbdelrhmanBassiouny/cognitive_robot_abstract_machine#488](https://github.com/AbdelrhmanBassiouny/cognitive_robot_abstract_machine/pull/488)
- **Progress note:** [`pr-progress/claude/ecstatic-knuth-curscv.md`](pr-progress/claude/ecstatic-knuth-curscv.md)
- **Depends on:** nothing

Shape-sorting vocabulary in semantic_digital_twin (ShapeSortingPiece + Cube/Cylinder/...Piece, ShapeSortingHole, ShapeSortingBoard, all in shape_sorting_toy/ with the board mesh, hole specifications, PieceSet, PieceColor; Polygon2D, Color.hue_distance, convex footprint), shared with main's coraplex Tracy demo; experiments keeps PieceColorMatcher. No longer a verbatim cut of #202: #202 adopts these names when it merges main and this layer. Promoted upstream as cram2#804. pieces.py:203 thread's EQL matching is item observation-matched-against-the-piece-set.

Blockers:

- Waiting on CI at a958c9e117 and the developer's call on two open #488 threads (generality; PieceColor as a Color enum). cram2#804's description and its 3 outdated threads are the developer's to update upstream.

<a id="montessori-perception-split--simulated-world-on-main"></a>
### `simulated-world-on-main`: Land the simulated Montessori world

- **Status:** not started
- **Recommended model:** haiku
- **Depends on:** [`shape-vocabulary-on-main`](#montessori-perception-split--shape-vocabulary-on-main)

montessori/world.py, test_montessori_world.py, dataset/synthetic_fixed_arm_robot.py and .urdf, and dataset/__init__.py - 5 files, ~1,770 lines. Has to land before any detection code, because pipeline.py reads BOARD_SCALE from world.py. That one constant brings in all 1,169 lines of world.py; detect-per-supporting-surface (knowledge-directed-grounding) removes that use later.

<a id="montessori-perception-split--frame-reading-on-main"></a>
### `frame-reading-on-main`: Land reading, rectifying and showing camera frames

- **Status:** not started
- **Recommended model:** haiku
- **Depends on:** [`simulated-world-on-main`](#montessori-perception-split--simulated-world-on-main)

perception/__init__.py, perception/exceptions.py, camera.py, orthophoto.py, viewer.py, the opencv dependency in experiments/pyproject.toml, and test_montessori_camera.py and test_montessori_viewer.py - 8 files, ~1,570 lines. Needs only main, so it could branch off main instead. It is stacked linearly so that every later layer has a single parent.

<a id="montessori-perception-split--piece-recognition-on-main"></a>
### `piece-recognition-on-main`: Land outline measurement and recognising a piece from its edges

- **Status:** not started
- **Recommended model:** sonnet
- **Depends on:** [`frame-reading-on-main`](#montessori-perception-split--frame-reading-on-main)

footprint.py, detections.py, edges.py and piece_matcher.py, test_montessori_footprint.py, and the direct piece-recognition tests. Those tests are split verbatim out of test_montessori_piece_matching.py into a module of their own, since that file imports pipeline.py at the top and uses the shared scene fixtures. This is the first half of the ~3,560-line detection layer, cut in two at the developer's decision (2026-10-02). Fallback if the piece-matcher tests turn out not to stand without the pipeline: fold this item into detection-pipeline-on-main rather than land code here that nothing tests.

<a id="montessori-perception-split--detection-pipeline-on-main"></a>
### `detection-pipeline-on-main`: Land the detection pipeline, its overlays and the simulated scene it is tested on

- **Status:** not started
- **Recommended model:** sonnet
- **Depends on:** [`piece-recognition-on-main`](#montessori-perception-split--piece-recognition-on-main)

pipeline.py, overlay.py, colors.py and scene_source.py, dataset/montessori_scene_renderer.py and montessori_scene_fixtures.py, test_montessori_views.py, test_montessori_perception.py, and the rest of test_montessori_piece_matching.py. The second half of the detection layer.

<a id="montessori-perception-split--captures-on-main"></a>
### `captures-on-main`: Land the real-camera captures and reading them back

- **Status:** not started
- **Recommended model:** haiku
- **Depends on:** [`detection-pipeline-on-main`](#montessori-perception-split--detection-pipeline-on-main)

perception/captures.py, the 18 files under montessori/resources/captures (3 MB), dataset/montessori_capture_truths.py, test_montessori_captures.py, and the .gitignore rosbags rule - 22 files, ~790 lines. Needs only frame-reading-on-main; it is stacked linearly for the same reason as that layer.

<a id="montessori-perception-split--perception-node-on-main"></a>
### `perception-node-on-main`: #202 itself, retargeted: the ROS runtime on top of the stack

- **Status:** not started
- **Recommended model:** sonnet
- **Pull request:** [AbdelrhmanBassiouny/cognitive_robot_abstract_machine#202](https://github.com/AbdelrhmanBassiouny/cognitive_robot_abstract_machine/pull/202)
- **Depends on:** [`captures-on-main`](#montessori-perception-split--captures-on-main)

perception/node.py, markers.py, recordings.py, watch_camera.py, capture_from_bag.py, tracy_experiments/equipment.py and tracy_experiments/__init__.py - 7 files, ~1,770 lines, all importing rclpy, so nothing here can run their tests. The item is to merge the top of the stack, and network-limits-on-main's branch, into montessori_perception_on_main (node.py's check_large_messages_can_arrive() call becomes LargeMessageReceiver().check_messages_can_arrive(), per #487), retarget #202's base to captures-on-main's branch, and rewrite #202's description to cover only this layer.

<a id="plan-knowledge-directed-grounding"></a>
## Plan `knowledge-directed-grounding`: Knowledge-directed perception: scene grounding

The scene grounding wave of knowledge-directed-perception (split out on 2026-09-05 to get every successor under the plan-size budget): the three faults visible on the running demo - a clip that shows the floor, pieces on the board's lid that are never found, and duplicate detections on the board's borders - are one fault, the scene being described by constants instead of read from the world the node already fetches.

Tracking issue: [AbdelrhmanBassiouny/cognitive_robot_abstract_machine#201](https://github.com/AbdelrhmanBassiouny/cognitive_robot_abstract_machine/issues/201).
Plan files: [`plans/knowledge-directed-grounding`](plans/knowledge-directed-grounding).

### Standing rules

- The perception package lands on `main` first (`montessori-perception-on-main`), since every item across all three successors edits files that exist on no branch but `tracy_icra`.
- The `surfaces` track (this plan) is sequential: each item edits the same pipeline the previous one left behind, so branches stack rather than run in parallel.
- `surface-finish-annotation` (`knowledge-directed-requests`) depends on nothing and can start immediately, off `main` - it touches only `semantic_digital_twin`.

<a id="knowledge-directed-grounding--surfaces-from-world"></a>
### `surfaces-from-world`: Take the workspace from the table the robot knows about, not from a constant

- **Status:** in progress
- **Recommended model:** sonnet
- **Branch:** `perception_surfaces_from_world`
- **Pull request:** [AbdelrhmanBassiouny/cognitive_robot_abstract_machine#205](https://github.com/AbdelrhmanBassiouny/cognitive_robot_abstract_machine/pull/205)
- **Progress note:** [`pr-progress/perception_surfaces_from_world.md`](pr-progress/perception_surfaces_from_world.md)
- **Depends on:** [`montessori-perception-split/perception-node-on-main`](#montessori-perception-split--perception-node-on-main)

Fixes the first fault: the clip shows the floor because TRACY_WORKSPACE (node.py:102) is a hand-written 1.0 x 1.2 m rectangle. table_top_z() already pulls the tabletop's collision shape out of the fetched world for its height and discards scale.x, scale.y and the origin, which are exactly the bounds being guessed. Derives the region and every plane height from the world, and from HasSupportingSurface.supporting_surface where one exists. The review round of 2026-08-29 is answered in full.

Blockers:

- Unanswered question to the developer, raised on #205 at review time and still open: WorkspaceSurface.of_body picks the body's widest horizontal face, following table_top_z's existing rule, where the highest face is arguably the truer reading of "the surface things rest on".

<a id="knowledge-directed-grounding--detect-per-supporting-surface"></a>
### `detect-per-supporting-surface`: Look at every supporting surface, not only the table

- **Status:** in progress
- **Recommended model:** sonnet
- **Branch:** `perception_per_supporting_surface`
- **Pull request:** [AbdelrhmanBassiouny/cognitive_robot_abstract_machine#221](https://github.com/AbdelrhmanBassiouny/cognitive_robot_abstract_machine/pull/221)
- **Progress note:** [`pr-progress/perception_per_supporting_surface.md`](pr-progress/perception_per_supporting_surface.md)
- **Depends on:** [`surfaces-from-world`](#knowledge-directed-grounding--surfaces-from-world)

Fixes the second fault: a piece resting on the board's lid is invisible twice over. The pipeline rectifies loose pieces onto exactly one plane (table_height), so a piece eighty millimetres higher is parallax-shifted out of both silhouettes; and pipeline.py:626 drops any contour the board encloses, coding the board as an obstacle when it is physically a supporting surface like the table. One detection pass per surface, each at its own plane height, with detections attributed to the surface supporting them. Built 2026-08-30 as #221, 2744c23d.

<a id="knowledge-directed-grounding--one-detection-per-thing"></a>
### `one-detection-per-thing`: One physical thing, one detection, and none inside a body already known

- **Status:** in progress
- **Recommended model:** sonnet
- **Branch:** `claude/plan-item-kickoff-kdp-z4pv7l`
- **Pull request:** [AbdelrhmanBassiouny/cognitive_robot_abstract_machine#225](https://github.com/AbdelrhmanBassiouny/cognitive_robot_abstract_machine/pull/225)
- **Progress note:** [`pr-progress/claude/plan-item-kickoff-kdp-z4pv7l.md`](pr-progress/claude/plan-item-kickoff-kdp-z4pv7l.md)
- **Depends on:** [`detect-per-supporting-surface`](#knowledge-directed-grounding--detect-per-supporting-surface)

Fixes the third fault: the duplicate boxes on the board's borders are the lid's own edges, which a rectangular or triangular prism template fits at about 0.7 - above the 0.62 threshold. board.encloses only rejects a contour whose centre falls inside the board, and a contour riding the border has its centre outside; nothing anywhere forbids two detections occupying one place. Rejects a detection intersecting a known body's volume, and resolves overlapping detections against each other. semantic_digital_twin.reasoning.predicates.is_place_occupied already exists for the first half.

<a id="knowledge-directed-grounding--holes-fitted-like-pieces"></a>
### `holes-fitted-like-pieces`: Find the board's holes by fitting its whole known layout, not one contour at a time

- **Status:** in progress
- **Recommended model:** sonnet
- **Branch:** `claude/plan-item-kickoff-ge8541`
- **Pull request:** [AbdelrhmanBassiouny/cognitive_robot_abstract_machine#236](https://github.com/AbdelrhmanBassiouny/cognitive_robot_abstract_machine/pull/236)
- **Progress note:** [`pr-progress/claude/plan-item-kickoff-ge8541.md`](pr-progress/claude/plan-item-kickoff-ge8541.md)
- **Depends on:** [`pieces-looked-for-where-expected`](#knowledge-directed-grounding--pieces-looked-for-where-expected)

The board's holes are found by fitting the mesh's own rigid six-hole layout over the lid in one shot - three degrees of freedom for all six holes together, seeded from the board detection's own pose - rather than classifying each contour on its own. A free per-contour fit was tried first and is what put the fault there: a triangular prism template laid anywhere near the board's middle reaches 0.85-0.89 agreement in every capture, higher than any genuine piece on the lid, and converges on the same spot each time.

<a id="knowledge-directed-grounding--pieces-looked-for-where-expected"></a>
### `pieces-looked-for-where-expected`: Look for a piece where it is expected, not only where a colour blob appears

- **Status:** in progress
- **Recommended model:** opus
- **Branch:** `claude/plan-item-kickoff-kdp-o4l189`
- **Pull request:** [AbdelrhmanBassiouny/cognitive_robot_abstract_machine#232](https://github.com/AbdelrhmanBassiouny/cognitive_robot_abstract_machine/pull/232)
- **Progress note:** [`pr-progress/claude/plan-item-kickoff-kdp-o4l189.md`](pr-progress/claude/plan-item-kickoff-kdp-o4l189.md)
- **Depends on:** [`one-detection-per-thing`](#knowledge-directed-grounding--one-detection-per-thing)

The structural change the rest of the plan's perception work needs. Today a piece is only found where colour segmentation isolated a blob, so one wearing the lid's own hue, or touching another piece, is never fitted however plainly its edges show.

<a id="knowledge-directed-grounding--competing-explanations"></a>
### `competing-explanations`: Decide a detection by comparing explanations, not against a fixed threshold

- **Status:** in progress
- **Recommended model:** opus
- **Branch:** `claude/plan-item-kickoff-kdp-r8nttk`
- **Pull request:** [AbdelrhmanBassiouny/cognitive_robot_abstract_machine#270](https://github.com/AbdelrhmanBassiouny/cognitive_robot_abstract_machine/pull/270)
- **Progress note:** [`pr-progress/claude/plan-item-kickoff-kdp-r8nttk.md`](pr-progress/claude/plan-item-kickoff-kdp-r8nttk.md)
- **Depends on:** [`pieces-looked-for-where-expected`](#knowledge-directed-grounding--pieces-looked-for-where-expected), [`holes-fitted-like-pieces`](#knowledge-directed-grounding--holes-fitted-like-pieces)

PieceMatcher.minimum_agreement is one number, 0.62, standing for how much of an outline must lie along a seen edge before a piece is reported, and its recorded justification is that a correct piece reaches 0.63 to 0.86 while the best wrong piece of the same colour reaches 0.62. Measured on 2026-08-31, that boundary does not hold anywhere near the board: a triangular prism template reaches 0.85 to 0.89 on the board's own middle in every capture, above every genuine piece detection on the lid in the same captures, which run 0.64 to 0.71 for the most part.

<a id="knowledge-directed-grounding--montessori-classes-in-the-orm"></a>
### `montessori-classes-in-the-orm`: Map the Montessori package's own classes, which the ORM has never seen

- **Status:** in progress
- **Recommended model:** sonnet
- **Branch:** `claude/montessori-classes-orm-s7vxu1`
- **Pull request:** [AbdelrhmanBassiouny/cognitive_robot_abstract_machine#223](https://github.com/AbdelrhmanBassiouny/cognitive_robot_abstract_machine/pull/223)
- **Progress note:** [`pr-progress/claude/montessori-classes-orm-s7vxu1.md`](pr-progress/claude/montessori-classes-orm-s7vxu1.md)
- **Depends on:** [`montessori-perception-split/perception-node-on-main`](#montessori-perception-split--perception-node-on-main)

experiments/src/experiments/montessori/ has no __init__.py, and never has on any branch, so pkgutil does not report it as a subpackage of experiments and the ORM generator's package walk skips the whole thing. Nothing under experiments.montessori is in experiments/orm/ormatic_interface.py - not MontessoriShape, not CubeShape, not ShapeSortingBoard.

<a id="knowledge-directed-grounding--demo-runs-on-grounded-perception"></a>
### `demo-runs-on-grounded-perception`: The demo sees only the table, finds pieces on the lid, and reports each once

- **Status:** not started
- **Recommended model:** sonnet
- **Depends on:** [`one-detection-per-thing`](#knowledge-directed-grounding--one-detection-per-thing)

Lands on the tracy_icra demo branch, which knowledge-directed-expectation/demo-detects-and-recovers-a-failed-insert tracks. Wave one is finished when the three faults are gone on the real robot, not when their pull requests are approved: the clipped windows show the table and nothing beyond it, a cube resting on the board's lid is detected there, and no detection rides the board's borders. Verified against the live camera, with a captured frame kept for the tests.

<a id="plan-knowledge-directed-requests"></a>
## Plan `knowledge-directed-requests`: Knowledge-directed perception: query language and method selection

The requests wave of knowledge-directed-perception (split out on 2026-09-05 to get every successor under the plan-size budget): perception as an entity query language backend beside the native and SQLAlchemy ones, so asking is evaluating rather than calling a pipeline by hand. The backend pushes what it can of a query's conditions into the search and filters the rest over the detections that come back; a rule tree over the target and the surface says which detector runs and how its parameters are set.

Tracking issue: [AbdelrhmanBassiouny/cognitive_robot_abstract_machine#201](https://github.com/AbdelrhmanBassiouny/cognitive_robot_abstract_machine/issues/201).
Plan files: [`plans/knowledge-directed-requests`](plans/knowledge-directed-requests).

### Standing rules

- Unmerged is not unusable: an item stacks on the open, reviewed EQL rule-tree stack (#159 -> #210 -> #79 -> #76 -> #80 -> #77) directly rather than waiting for it to land. Only the classic krrood.ripple_down_rules machinery is genuinely unusable.
- State every cost comparison as a ratio to a baseline measured in the same run (e.g. "1.08x the parent"), never as bare seconds: the container's speed varies between runs by more than the differences measured.
- A direction relation (left of, above) is read from where the camera stands, via RgbdFrame.point_of_view, not from the world's axes.
- A relation asserted about the thing sought is an ordinary EQL Match over the relation's own class, not a Match subclass (the developer reversed StatedRelation); value comparison is stated explicitly at the call sites that need it.

<a id="knowledge-directed-requests--perception-backend"></a>
### `perception-backend`: Answer a query by looking, as a backend of the entity query language

- **Status:** in progress
- **Recommended model:** opus
- **Branch:** `perception_eql_backend`
- **Pull request:** [AbdelrhmanBassiouny/cognitive_robot_abstract_machine#222](https://github.com/AbdelrhmanBassiouny/cognitive_robot_abstract_machine/pull/222)
- **Progress note:** [`pr-progress/perception_eql_backend.md`](pr-progress/perception_eql_backend.md)
- **Depends on:** nothing

Answers a query by looking, as a `PerceptionBackend` beside `EntityQueryLanguageBackend` and `SQLAlchemyBackend` - `SQLAlchemyBackend` already sets the shape (translate the query into another engine's plan, run it there), and the compiler from a query to a detection pipeline is the same move against a camera. It subclasses `SelectiveBackend`: a camera reports what is really there and cannot invent an attribute nobody can see (the plan's own open question, answered here).

<a id="knowledge-directed-requests--perception-predicates-guide-the-search"></a>
### `perception-predicates-guide-the-search`: Guide the search by predicates and annotations, not by attribute names

- **Status:** in progress
- **Recommended model:** opus
- **Branch:** `claude/plan-item-kickoff-perception-ogf2g9`
- **Pull request:** [AbdelrhmanBassiouny/cognitive_robot_abstract_machine#227](https://github.com/AbdelrhmanBassiouny/cognitive_robot_abstract_machine/pull/227)
- **Progress note:** [`pr-progress/claude/plan-item-kickoff-perception-ogf2g9.md`](pr-progress/claude/plan-item-kickoff-perception-ogf2g9.md)
- **Depends on:** [`perception-backend`](#knowledge-directed-requests--perception-backend)

Raised by the developer across five review threads on #222, which are one ask: a look should be narrowed by what the world means, not by an attribute spelled as a string. SUPPORTING_SURFACE_ATTRIBUTE_NAME = "supporting_surface" and the mimic's PLACE_ATTRIBUTE_NAME are the smell; AGENTS.md's own rule against a literal duplicating a value with its own source of truth condemns them independently of the redesign, and #222 leaves them standing with a test asserting the name is a real field.

<a id="knowledge-directed-requests--search-clipped-to-a-predicates-region"></a>
### `search-clipped-to-a-predicates-region`: Clip the search to the region a spatial predicate allows

- **Status:** in progress
- **Recommended model:** sonnet
- **Branch:** `claude/kdp-search-constraints-pfaph7`
- **Pull request:** [AbdelrhmanBassiouny/cognitive_robot_abstract_machine#238](https://github.com/AbdelrhmanBassiouny/cognitive_robot_abstract_machine/pull/238)
- **Progress note:** [`pr-progress/claude/kdp-search-constraints-pfaph7.md`](pr-progress/claude/kdp-search-constraints-pfaph7.md)
- **Depends on:** [`perception-predicates-guide-the-search`](#knowledge-directed-requests--perception-predicates-guide-the-search), [`knowledge-directed-grounding/pieces-looked-for-where-expected`](#knowledge-directed-grounding--pieces-looked-for-where-expected)

Clips the search to the region a spatial predicate allows - the same economy the supporting-surface pushdown already buys, stated in the world's vocabulary instead of an attribute's, so narrowing stops being a filter over what a detector returned and becomes less picture to search in the first place. Depends on `perception-predicates-guide-the- search` (where a statement's predicates are read at all) and `pieces-looked-for-where- expected` (which owns the *believed place* type this item's clip is built from) - building either half twice is the duplication this plan has already paid for.

Blockers:

- One of the six review threads of 2026-09-02 is still open, and it is the developer's to close rather than work for this item.

<a id="knowledge-directed-requests--imagination-world-rejects-what-a-predicate-refuses"></a>
### `imagination-world-rejects-what-a-predicate-refuses`: Reject what a predicate refuses, by testing it in a copy of the world

- **Status:** in progress
- **Recommended model:** opus
- **Branch:** `claude/knowledge-directed-perception-imagination-g9hsnr`
- **Pull request:** [AbdelrhmanBassiouny/cognitive_robot_abstract_machine#255](https://github.com/AbdelrhmanBassiouny/cognitive_robot_abstract_machine/pull/255)
- **Progress note:** [`pr-progress/claude/knowledge-directed-perception-imagination-g9hsnr.md`](pr-progress/claude/knowledge-directed-perception-imagination-g9hsnr.md)
- **Depends on:** [`perception-predicates-guide-the-search`](#knowledge-directed-requests--perception-predicates-guide-the-search), [`search-clipped-to-a-predicates-region`](#knowledge-directed-requests--search-clipped-to-a-predicates-region)

The developer's third mechanism on r3893499716, deferred out of #227 as a second pull request's worth of work: a predicate no search algorithm covers is still answerable, by detecting what the other conditions do reach, spawning what was found into a copy of the world, evaluating the predicate there against real Body and SemanticAnnotations, and deleting what it rejects. It is what closes the gap #227 leaves open.

<a id="knowledge-directed-requests--how-to-look-concluded-from-the-request"></a>
### `how-to-look-concluded-from-the-request`: Work out how to answer a look from the request, instead of being handed a pipeline

- **Status:** in progress
- **Recommended model:** opus
- **Branch:** `claude/plan-item-kickoff-perception-idzwsk`
- **Pull request:** [AbdelrhmanBassiouny/cognitive_robot_abstract_machine#266](https://github.com/AbdelrhmanBassiouny/cognitive_robot_abstract_machine/pull/266)
- **Progress note:** [`pr-progress/claude/plan-item-kickoff-perception-idzwsk.md`](pr-progress/claude/plan-item-kickoff-perception-idzwsk.md)
- **Depends on:** [`choose-detection-method`](#knowledge-directed-requests--choose-detection-method), [`detector-parameters-from-knowledge`](#knowledge-directed-requests--detector-parameters-from-knowledge)

Raised by the developer on `search-clipped-to-a-predicates-region`'s review (r3915356623), 2026-09-02: the pipeline's own six fields are not one kind of thing - the world already supplies the table, lid, world and reference frame (`of_world`); `detector-parameters- from-knowledge` concludes `headroom`; only the two detectors are genuinely hand-wired.

<a id="knowledge-directed-requests--surfaces-found-by-looking"></a>
### `surfaces-found-by-looking`: Find a surface in the image from what the world says it is like

- **Status:** in progress
- **Recommended model:** sonnet
- **Branch:** `claude/plan-item-kickoff-kdp-34snn0`
- **Pull request:** [AbdelrhmanBassiouny/cognitive_robot_abstract_machine#259](https://github.com/AbdelrhmanBassiouny/cognitive_robot_abstract_machine/pull/259)
- **Progress note:** [`pr-progress/claude/plan-item-kickoff-kdp-34snn0.md`](pr-progress/claude/plan-item-kickoff-kdp-34snn0.md)
- **Depends on:** [`perception-backend`](#knowledge-directed-requests--perception-backend), [`choose-detection-method`](#knowledge-directed-requests--choose-detection-method)

Finds a surface in the picture from what the twin already says it is like - a large horizontal plane, mirror-finished, colourless, of about the modelled size - stated as an entity query language expression rather than read off a constant or a body's collision shape, since neither is a measurement of where the table really is and the demo has already drifted from its own model once. `SurfaceFinder`/`SurfaceRules` is `choose-detection-method`'s claim turned on the surface itself.

<a id="knowledge-directed-requests--choose-detection-method"></a>
### `choose-detection-method`: Choose the detector by rule from the target and the surface

- **Status:** in progress
- **Recommended model:** sonnet
- **Branch:** `claude/choose-detection-method-gf64yp`
- **Pull request:** [AbdelrhmanBassiouny/cognitive_robot_abstract_machine#231](https://github.com/AbdelrhmanBassiouny/cognitive_robot_abstract_machine/pull/231)
- **Progress note:** [`pr-progress/claude/choose-detection-method-gf64yp.md`](pr-progress/claude/choose-detection-method-gf64yp.md)
- **Depends on:** [`perception-backend`](#knowledge-directed-requests--perception-backend)

The detector interface the backend dispatches to, chosen by a rule tree over properties of the surface and the target - this is where perception measurably gets better as the robot knows more, and the item the paper's central claim rests on. Two shapes for the same claim were both built and layered at the developer's direction: each detector declares the looks it can answer as an entity query language condition (his own suggestion, r3893463818), and a ripple-down tree chooses among the ones that can (the item's own original design). Built 2026-08-31 as PR #231, `69f30348a`.

<a id="knowledge-directed-requests--detector-parameters-from-knowledge"></a>
### `detector-parameters-from-knowledge`: Take the detectors' numbers from the objects and the surfaces they look at

- **Status:** in progress
- **Recommended model:** opus
- **Branch:** `claude/knowledge-directed-perception-detector-zrm57t`
- **Pull request:** [AbdelrhmanBassiouny/cognitive_robot_abstract_machine#239](https://github.com/AbdelrhmanBassiouny/cognitive_robot_abstract_machine/pull/239)
- **Progress note:** [`pr-progress/claude/knowledge-directed-perception-detector-zrm57t.md`](pr-progress/claude/knowledge-directed-perception-detector-zrm57t.md)
- **Depends on:** [`choose-detection-method`](#knowledge-directed-requests--choose-detection-method)

The detectors' numbers - hue windows, size ranges, edge-agreement thresholds, mesh classification thresholds, and (widened 2026-08-31) the numbers that say *how to search* (seed radius, step, candidate set, required lead) - are knowledge about the pieces, the surfaces and the lighting, not properties of the detector reading them. They move onto the twin's objects and surfaces, concluded for a run by a ripple-down rule tree the same way `choose-detection-method`'s tree concludes which detector runs; the contour accept/reject chain (`pipeline.py:619`) becomes rules the same way.

<a id="knowledge-directed-requests--tune-detection-rules-against-the-camera"></a>
### `tune-detection-rules-against-the-camera`: Conclude a detection rule while watching the camera, with its numbers on sliders

- **Status:** not started
- **Recommended model:** sonnet
- **Branch:** `perception_interactive_rule_tuning`
- **Depends on:** [`detector-parameters-from-knowledge`](#knowledge-directed-requests--detector-parameters-from-knowledge)

The developer's own suggestion on #202: an interactive presenter for the ripple-down rules' `ConclusionHelper`, showing the live camera feed beside the parameters it would conclude, so an expert sees what a value does before committing it as a rule. Needs `detector-parameters-from-knowledge`'s rule-concluded parameters to present. Un-deferred 2026-08-31 at the developer's direction: what the deferral was mostly paying for - the interactive expert interface, the model-file store, the `@rdr` decorator - is already written, open, out of draft and reviewed on the RDR stack.

<a id="knowledge-directed-requests--a-look-is-described-by-a-match"></a>
### `a-look-is-described-by-a-match`: Describe a look by an underspecified match over the twin's own entities, not by a case class

- **Status:** in progress
- **Recommended model:** opus
- **Branch:** `claude/knowledge-directed-perception-vz2hhq`
- **Pull request:** [AbdelrhmanBassiouny/cognitive_robot_abstract_machine#275](https://github.com/AbdelrhmanBassiouny/cognitive_robot_abstract_machine/pull/275)
- **Progress note:** [`pr-progress/claude/knowledge-directed-perception-vz2hhq.md`](pr-progress/claude/knowledge-directed-perception-vz2hhq.md)
- **Depends on:** [`choose-detection-method`](#knowledge-directed-requests--choose-detection-method), [`surfaces-found-by-looking`](#knowledge-directed-requests--surfaces-found-by-looking), [`how-to-look-concluded-from-the-request`](#knowledge-directed-requests--how-to-look-concluded-from-the-request)

Added 2026-09-05 at the developer's direction on #259 (r3940339984 and r3940357436): "why not replace this with an EQL match statement of semdt semantic annotation or kinematic structure entities?", and "eql based rdrs (pr 77 for example) can take an underspecified match statement and get needed information from it to evaluate the rule tree of the rdr." Every rule tree on this plan states its conditions over a hand-written case class that flattens what the world already states, because the tree needs one variable to bind: TargetOnSurface on #231, RequestedLook on #266, and SoughtSurface on…

<a id="knowledge-directed-requests--camera-pose-fitted-to-the-model"></a>
### `camera-pose-fitted-to-the-model`: Correct where the camera stands by fitting what is seen to what the twin models

- **Status:** in progress
- **Recommended model:** sonnet
- **Branch:** `claude/camera-pose-fitted-p2mk7d`
- **Pull request:** [AbdelrhmanBassiouny/cognitive_robot_abstract_machine#286](https://github.com/AbdelrhmanBassiouny/cognitive_robot_abstract_machine/pull/286)
- **Depends on:** [`surfaces-found-by-looking`](#knowledge-directed-requests--surfaces-found-by-looking), [`knowledge-directed-grounding/holes-fitted-like-pieces`](#knowledge-directed-grounding--holes-fitted-like-pieces)

Added 2026-09-05 at the developer's direction on #259, folding the two threads he asked to keep together (r3940349876 and r3940351882): "since we have a 3d model of the world, we can use this information to maybe even calibrate the camera ...

<a id="knowledge-directed-requests--observation-matched-against-the-piece-set"></a>
### `observation-matched-against-the-piece-set`: Recognise a piece by matching what was seen against the piece set's instances, in EQL

- **Status:** not started
- **Recommended model:** sonnet
- **Depends on:** [`a-look-is-described-by-a-match`](#knowledge-directed-requests--a-look-is-described-by-a-match), [`detector-parameters-from-knowledge`](#knowledge-directed-requests--detector-parameters-from-knowledge), [`montessori-perception-split/shape-vocabulary-on-main`](#montessori-perception-split--shape-vocabulary-on-main)

Added 2026-10-13 at the developer's direction, from the KnownPiece thread on #488 (r4250836397). A seen blob becomes a partial EQL description (outline from above, measured hue, height) resolved against the PieceSet instances with tolerance predicates (hue, height, outline fit), replacing PieceMatcher's Python hue filter and outline fit and detector_choice.py's exact colour equality. #265 is an integration branch, so the parts it needs are taken from #222/#275, not from #265.

<a id="knowledge-directed-requests--demo-asks-by-query"></a>
### `demo-asks-by-query`: The demo's perception runs because a query was evaluated

- **Status:** not started
- **Recommended model:** sonnet
- **Depends on:** [`choose-detection-method`](#knowledge-directed-requests--choose-detection-method), [`knowledge-directed-grounding/demo-runs-on-grounded-perception`](#knowledge-directed-grounding--demo-runs-on-grounded-perception)

Lands on the tracy_icra demo branch, which knowledge-directed-expectation/demo-detects-and-recovers-a-failed-insert tracks. Every perception call in montessori_demo.py goes through the backend rather than calling the pipeline by hand, and the detector that answers is the one the rule tree chose from the surface and the target - visibly a different one for the steel table than for the board's lid. This is the wave's claim made demonstrable: the same question, answered differently because the robot knows what it is looking at.

<a id="knowledge-directed-requests--perception-join"></a>
### `perception-join`: Join the two perception lineages, in the pull request that already is the join

- **Status:** blocked
- **Recommended model:** sonnet
- **Branch:** `claude/detector-consolidation-analysis-rgg3xg`
- **Pull request:** [AbdelrhmanBassiouny/cognitive_robot_abstract_machine#299](https://github.com/AbdelrhmanBassiouny/cognitive_robot_abstract_machine/pull/299)
- **Progress note:** [`pr-progress/claude/detector-consolidation-analysis-rgg3xg.md`](pr-progress/claude/detector-consolidation-analysis-rgg3xg.md)
- **Depends on:** [`knowledge-directed-grounding/competing-explanations`](#knowledge-directed-grounding--competing-explanations), [`a-look-is-described-by-a-match`](#knowledge-directed-requests--a-look-is-described-by-a-match)

#299's 9c4840bf94 already is the join commit -- its own message says the two detectors "arrived on the same detector from different branches of #231, onto the rewrite #236 had already landed" -- sitting on #265 because no other base held both lineages. knowledge-directed-grounding's chain (#202 to #270) is correctly stacked and is one side; knowledge-directed-requests' (#231 to #275, plus #259) is the other. Merging the tips leaves roughly 23 conflict hunks over 1,100 lines, 13 of them in pipeline.py.

Blockers:

- Eleven commits on #265 touch #299's own eight files and are on no lineage branch. Four are convergence glue a correctly ordered stack does not need; the other seven are perception-direct-commits.

<a id="knowledge-directed-requests--perception-direct-commits"></a>
### `perception-direct-commits`: Replay the seven perception features that reached no pull request

- **Status:** not started
- **Recommended model:** haiku
- **Depends on:** [`perception-join`](#knowledge-directed-requests--perception-join)

6c968260eb, 9ab3729019, 746f8ea3c6, 280832645d, 3d6504f7d9, 4bf6694f1d and 54b4ec5848 -- real features pushed straight onto #265, in no pull request's diff. The other four of the eleven (0e4d632b3f, a3acc06fbe, 83c3eae1b7, 5f63f0f503) are reconciliation glue that exists only because the lineages were merged all at once, and a correctly ordered stack should not need them.

