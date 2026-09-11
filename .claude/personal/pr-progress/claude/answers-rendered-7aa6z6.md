# claude/answers-rendered-7aa6z6 -> PR #318 (draft)

Base: claude/icra-experiments-simulation-pipeline-w4ep7n (#265). NOT main - this
stacks on #265, which owns the recording pipeline the cards read.

## Plan (all six steps done)

1. [x] MujocoSim.geoms_of / recolor / make_visible, promoted out of
       test_region_appearance.py (commit 532264f, b1e9947)
2. [x] experiments/paper/scene.py - SceneRender, RenderedScene, PointOfView (adb67f0)
3. [x] experiments/paper/timeline.py - EventTimeline (7befcc8)
4. [x] experiments/paper/camera_frame.py - BagFrameAt (8611ca0)
5. [x] experiments/paper/query_card.py + panel.py, FigureFile.IMAGE,
       TypstRenderer.render_image_figure (bd817d3)
6. [x] experiments/scripts/render_query_cards.py, cards wired into
       generate_paper_figures.py (e0c4225)

All four "done when" cards exist and are tested: ObjectsSeen,
SideOfAnotherObject, PickedUpRecently, NumberOfOwnDegreesOfFreedom.

## Outstanding / for the next session

- CI has not reported yet. Nothing has been subscribed and no check-in is armed,
  per my own rules - I will prompt if I want CI handled.
- Could not run locally (no ROS in the sandbox, so the ORM interfaces cannot be
  generated): test_paper_figures.py, test_paper_figures_from_the_database.py, and
  any end-to-end run of the two scripts. The scripts are smoke-tested via --help
  only; their logic lives in QueryCardSet.write_every_episode, which is tested.
- generate_orm.py was edited to ignore the five new paper modules. That edit was
  NOT verified by running the generator (same ROS reason). If CI's ORM build
  fails, that is the first place to look.
- Drive-by fix carried in this PR: MujocoEntityNotFoundError was not a @dataclass,
  so all fifteen raises of it in multi_sim.py died with a TypeError. Fixed because
  geoms_of depends on it. It does NOT fix test_world_multi_sim_with_change, which
  was already red and now shows its real cause.
- The example card PNG is not committed (experiments/doc tracks only
  references.bib); the PR description carries the .typ and a description instead,
  and the images went to the session. Say the word if you want them committed so
  the description can show them inline.

## Sandbox notes (not committed, would need redoing in a fresh session)

Workspace installed with `pip install --no-deps -e <each package>` under
python3.12, plus hand-stubbed rosbag2_py / rclpy / sensor_msgs / tf2_msgs in
site-packages, urdf_parser_py copied from an sdist, casadi pinned to ~=3.7.0, and
libosmesa6 via apt. Tests then run with
`MUJOCO_GL=osmesa python3.12 -m pytest <paths> --orm-build=never`.
