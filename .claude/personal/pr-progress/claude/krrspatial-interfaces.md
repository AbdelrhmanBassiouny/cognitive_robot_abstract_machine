Plan
- Answer cram2#1019's reviews; the owner posts the replies and resolves the threads.
- Design doc (implemented): https://claude.ai/artifact/3aEJ5hBBxZ7GGBMNK6XXKq

Done
- 387b26e3: cross product on the frame kind (CartesianFrame3Dimensional.cross_product; FrameHasNoCrossProductError); CrossProductVector, SymbolicAxisCoordinates removed; coordinate_system_arguments overridden once by SymbolicSpatialValue.
- 6501202762 (owner chose C): AffineFrame.axes names the axes (FrameAxis X/Y/Z for any straight-axis frame; Cartesian kinds return them); AxisCoordinates reads/builds through frame_kind.axes and raises MissingAxisCoordinatesError at definition; AxisCoordinate marker and coordinate_names removed.
- 802b43fd: README "Adding a space" models camera pixels end to end (CropAndResize change, asserted results); test_readme_example.py runs it. PR description gained the example and an effort table.
- Verified at 802b43fd: test/krrood_spatial_math_test 732 passed; pre-commit clean. SemDT/giskard/coraplex not run (ROS).

Next
- Owner: post the replies in .claude/personal/review-replies/cram2-1019.md (notes branch), updated to 802b43fd.
- Owner to decide: homogeneous_weight -> bool has_position (another session's suggestion; recommended yes, reverses the earlier "keep int").
- Possible follow-up: a reusable law test for coordinate changes (inverse @ change is no change).
- Read CI on 802b43fd. #524 needs its own resolve.
