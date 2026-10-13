## shape-vocabulary-on-main (montessori-perception-split, layer 2) - draft #488

Cut from #202 at 6dda1916e (was 4653fe32e); branch off main 236b295a2.

Done:
- Kickoff: bootstrap 5e1856058, layer 1fc3188fb, draft PR, manifest, roadmap, dashboard.
- Review 2026-10-04 (9 threads): the developer chose to answer it on #202 and then re-cut.
  - 6dda1916e on montessori_perception_on_main changes every caller on #202:
    - enum removed in favour of the MontessoriShape classes;
    - HoleShapeClassifier, ShapeSortingBoardMesh and HoleFootprint.MARKER_THICKNESS;
    - PieceHue, HueCircle and PieceSet.this_lab();
    - Point2 and PlanarBoundingBox reused, and Polygon2D added to SemDT geometry.py with test_polygon.py;
    - pieces-only tests moved into test_montessori_pieces.py.
    - Tests: 174 passed, 1 skipped with --noconftest via the /home/user/wt202 worktree and PYTHONPATH.
  - 2f0358c7b re-cuts #488: 10 files byte-identical to 6dda1916e; 45 passed on the branch alone.
  - Replied on all 9 threads and resolved 8. The SemDT thread stays open on whether HueCircle belongs in SemDT.
  - #488 and #202 descriptions updated. #488 stays a draft. #202 was already ready before this push and was left as it was.
  - Plan notes and roadmap saved (5bc27b51c).

- /plan-item-resolve 2026-10-12 (auto mode, session 01T25zXQ): head 06bc048f1 (3 merges of main after 2f0358c7b).
  - All 10 layer files still byte-identical to origin/montessori_perception_on_main (645e7104e).
  - CI red: test_each_lib (experiments). Two tests in test_montessori_semantics.py call Pose.to_position() and
    to_rotation_matrix(), which main's #694 (fff798615) turned into the properties position / rotation_matrix.
    #202 carries the same test file, so it fails too. Fix = 2 lines (pose.position, pose.rotation_matrix.to_rpy()).
    This is an API migration, not a change to what the tests assert.
  - New review threads 2026-10-12 (open):
    - pieces.py:203 KnownPiece: generalize "what is known about an entity" into EQL partial descriptions
      (a(CubeShape)(...).where(HasColor, HasHeight)); asks for a brainstorm, possibly a new plan.
    - pieces.py:228 PieceHue: relate hue to SemDT's Color instead of a separate concept.
    - Still open from 10-04: HueCircle in SemDT?
  - Research: there is no AnonymousEntity or Proxy class; the reviewer means Ontomatic's AnonymousClass (dl:
    krrood/ontomatic/utils.py:45; dl2: ontology_info.py:343), set up dynamically with setattr.
    EQL's Match (krrood query/match.py) already gives typed partial descriptions with nested keyword arguments,
    .where(), membership via .from_([obj]) and generation via EntityQueryLanguageGenerativeBackend.
    Gaps:
    - a(Polygon2D.rectangle) declares type `method`.
    - Polygon2D has no width/length attributes.
    - MontessoriShape has no outline/height/color.
    - There is no HasColor/HasHeight predicate.
    - Color is RGBA only, with no hue.
  - Stopped to ask the developer. Answers:
    - the CI fix goes on #202, then re-cut;
    - hue moves into SemDT Color in this round;
    - #488 is blocked on the KnownPiece redesign.
  - d4abc697d on #202 migrates Pose to_* to properties across the whole package (main's #694 also broke
    pipeline/overlay/detections/markers/node and four other test modules). It also replaces
    the(match.expression) with the(match) (main's f70c1aff45). 174 passed, 1 skipped.
  - be578659e on #202:
    - SemDT gains Hue (degrees, distance), Color.from_hsv and Color.hue, with test_hue.py;
    - PieceHue(Hue, Enum) is CYAN 172 / YELLOW 42 and KnownPiece.hue is a Hue;
    - hue_tolerance is 8 degrees;
    - HueCircle is gone and HueChannel in pipeline.py reads the OpenCV channel.
    - 196 passed, 1 skipped.
  - 91a1dfba6 re-cuts #488 from be578659e: 11 files byte-identical, 52 passed. Pushed.
  - Threads:
    - replied on the hue thread and the HueCircle/SemDT thread, then resolved both;
    - replied on the KnownPiece thread with the brainstorm, left open.
    - Description updated; still a draft.
  - #202's ready/draft state was not changed. It was ready before, as in the 10-04 round.
  - Plan: item status blocked, with blockers, notes and roadmap section.

- 2026-10-13, the developer's answers:
  - (2) fold DetectionColor -> done in d350dabb3 on #202. Detection colours are SemDT Colors, markers.py
    uses ColorToRos2Converter, and BgrPixel in colors.py holds OpenCV's BGR/255 encoding. 197 passed, 1 skipped.
    None of those files is in #488's layer, so no re-cut.
  - (1) The developer asked whether height/outline/hue are really MontessoriShape's. Answer: no, they are
    general body geometry.
    - height = VolumetricBoundingBox.height of the collision in the supporting frame (exists).
    - outline = a footprint projected onto the resting plane (missing; proposed
      ShapeCollection.footprint -> Polygon2D).
    - colour = Shape.color, with Color.hue (exists).
    - rotation period = symmetry of the footprint (proposed Polygon2D method).
    - Tolerance predicates go in SemDT.
  - The developer asked whether the lab set should be normal instances. Answer: agreed. Real bodies with the
    measured geometry and colour, annotated with their MontessoriShape. The partial EQL description is then
    the observation, queried against those instances.
  - Found: world.py builds the simulated pieces from the hole footprints (clearance-scaled, its own thicknesses),
    taking only the colour from PieceSet. That is a second description that disagrees (triangular prism
    0.02 vs 0.03 m).
  - Questions put to the developer:
    - is there exactly one piece of each kind?
    - where do the instances live (builder in pieces.py, placed by world.py)?
    - footprint caching for PieceMatcher;
    - the simulated world switching to the measured sizes.

  - The developer answered:
    - there are two physical sets, of slightly different size and colour;
    - the builder in pieces.py, placed by world.py, is fine;
    - the simulated world uses only ground-truth values.
  - Scope check: everything depends on #488's unlanded SemDT types (Polygon2D, Hue). So it all lands through
    #202 plus re-cuts, with no new plan or item. The SemDT part goes to layer 2, the matcher/pipeline to
    5a/5b, and world.py to 3.
  - 83019e34d on #202: ShapeCollection.convex_footprint_in_frame (scipy ConvexHull of the projected meshes;
    shapely is not installed), Polygon2D.rotational_symmetry_angle (CORNER_MATCH_TOLERANCE) and
    NoShapesToProject. New test_footprint.py, plus tests in test_polygon.py. 208 passed, 1 skipped.
  - 13b021da8 re-cuts #488 from 83019e34d: 14 files (adds shape_collection.py, exceptions.py,
    test_footprint.py), byte-identical, 62 passed. Description updated; still a draft.
  - Asked the developer for the second set's measurements (size per piece, hue), whether both sets are on the
    table at once, and whether the disk/sphere (no ground truth) leave the simulated world.

Next: the Montessori rewrite once the second set's numbers arrive. Set 1 can start now:
- the lab pieces as SemDT bodies annotated with MontessoriShape, built in pieces.py from ground truth;
- PieceMatcher reading footprint/symmetry/hue from them;
- world.py and the renderer using them;
- KnownPiece removed.
Then re-cut layer 2. CI on #202's d4abc697d..83019e34d and #488's 13b021da8 is not polled.
