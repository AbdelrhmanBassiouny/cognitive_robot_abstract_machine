# Future problems

Problems set aside until the statechart refactoring of `plan-cramp-second-iter` is
done. Every test listed here is marked `@pytest.mark.parked` (or `pytestmark =
pytest.mark.parked` for a whole module) and skipped. Once a problem is solved, remove
the marker from its tests and its entry from this file.

## Sending statecharts as JSON

The JSON tests run again and are no longer parked. Every node class is sent through
JSON by a `test_node_json_round_trips.py` per package (`test/cramph_test/test_statechart`,
`test/giskardpy_test/test_motion_statechart`, `test/giskardpy_test/test_ros2_stuff`,
`test/coraplex_test/test_plan`), built on `test/statechart_json_round_trip.py`.

Open questions:

- Whether an underspecified statement (a krrood `Match`) has to survive JSON at all.
  Today `UnderspecifiedNode.statement` is not serialized, and the node is sent as the
  `CompositeNodeChoosingItsChild` it is, so the receiving process asks the sender for
  each child instead of grounding the statement itself. Tests covering that, and a
  statement inside a sent statechart, are still to be written.
- A coraplex `Action` is sent as itself and declares the context extensions it
  requires (`RobotAccess` and, per action, `ExecutionMode` or `MotionToleranceConfig`).
  It reads them only while expanding, which happens in the sending process, but a
  statechart checks them whenever a node joins or compiles, so a receiving process
  whose context lacks them rejects the action with
  `NodesMissingContextExtensionsError`. Either the receiver's context gets them, or
  requirements needed to expand are told apart from those needed to build and tick.
- `FunctionCall` and `ThreadedPredicateMonitor` hold a Python callable and cannot be
  sent; writing a statechart holding one raises `ClassNotSerializableError`. They have
  no round-trip case.
- The real-stretch cross-process demo,
  `test/experiments_test/real_stretch_demo_test/test_real_stretch_demo_process_boundary.py`:
  `test_demonstration_runs_against_a_controller_in_another_process`, failed because
  `MoveGripper` did not survive a round trip. `MoveGripper` does now; the demo itself
  still has to be run where `robokudo_msgs` is installed.

## Design questions set aside

These park no tests; they are design changes the review of ichumuh#8 raised and that
were deliberately left for later.

### A statechart that takes its context from its executor

Building a plan's statechart still reads `Statechart(context=executor.context)`. The
statechart could instead get its context from the executor compiling it, but a node
expands the moment it joins a statechart (`Statechart.add_node`), and expanding reads
the context, so the context would have to be known before the executor is, or
expansion would have to move to compile time. That is a cramph change of its own.

### Underspecified statements as steps of a plan language node

A composite action whose step may be an `a(...)` statement wraps the statement in an
`UnderspecifiedNode` itself (`ActionOfSteps._node_running`). The plan language nodes
could accept a krrood `Match` among their children directly. Two ways to get there:

- cramph defines a node carrying a krrood `Match` (cramph may import krrood), which
  every `CramLanguageNode` wraps a `Match` child in when it adopts it, and coraplex's
  `UnderspecifiedNode` becomes, or extends, that node. The statement then lives in
  cramph although only coraplex grounds it.
- cramph defines a context extension that converts a child a language node cannot run
  into one it can, which coraplex registers for `Match`. Nothing about statements
  enters cramph, but a language node then needs its context to adopt its children,
  which it only has once it joined a statechart.

Separately, the steps of the composite actions are typed as the action they hold
(`pick_up: MoveAndPickUpAction`) although they may hold a `Match`. Typing them
`MoveAndPickUpAction | Match` makes ORMatic leave the field out of the data access
object, so a stored transport loses its steps; ORMatic needs to map such a union first.

### The trial's own sequence around a candidate

`ActionTrial.succeeds` runs a candidate in a `Sequence` of its own, so that the nodes a
plan transformation puts beside it are tried with it, the way the candidate runs for
real inside the `Attempt` of its `UnderspecifiedNode`. Simon would rather not wrap the
candidate; doing without it needs plan transformations that can insert beside a node
no language node runs.

### Holding still inside `Statechart.compile`

Waiting for every `RecompileCallback` to come to rest happens around a world-structure
rebuild and before a node chooses its child (`Statechart._when_held_still`), not inside
`Statechart.compile` itself. A compile that waits has to leave the statechart ticking
with nodes it has not compiled yet, but the state arrays grow the moment a node joins
and the compiled tick keeps reading the arrays it was compiled against, so the tick
would run on stale state until the compile happened.

### Robot-specific motions that were not ported to plan transformations

The motion designators that `coraplex/alternative_motion_mappings` replaced per robot are
gone, and so is that package. The drive goals of the Stretch and the Tiago and the
Stretch's way of closing a container are plan transformations now
(`coraplex/robot_plans/plan_transformations.py`). Three mappings were left out:

- **HSRB, real robot: driving through Navigation 2.** The mapping replaced the drive goal
  with a `NavigateActionServerTask` on the action topic `/hsrb/move_base`, sending a
  `nav2_msgs` `NavigateToPose`. It does not fit yet, because `nav2_msgs` is an optional
  dependency that the old module, like `giskardpy/motion_statechart/ros2_nodes/ros_tasks.py`,
  imported inside a try-except, and the topic was a literal in the code. Options: a
  transformation over `DrivesBase` like the differential drive ones, with `nav2_msgs`
  imported unguarded and the topic as a field of the transformation; or the HSRB's robot
  view naming its navigation action server.
- **Stretch, simulated and real: moving the tool center point.** The mapping held the
  base's orientation (`CartesianOrientation`, bound on start) while a
  `CartesianPoseStraight` moved the tool frame relative to the world root, and counted
  the motion as done once the joints stood still (`LocalMinimumReached`, threshold
  0.025). It does not fit yet, because the tool center point goal is no node of a type
  of its own: `MovesToolCenterPoint.tool_center_point_goal` builds a plain
  `CartesianPose` or `CartesianPosition` inside many actions, so a transformation would
  have to recognise it among every Cartesian goal by its tip, and the reachability checks
  of the pose validator would not see the replacement. Options: a goal type of its own
  for moving a tool center point, which a transformation can match; a context extension
  that `MovesToolCenterPoint` asks for the goal; or dropping the mapping as tuning of one
  demonstration.
- **Stretch, simulated and real: gripper thresholds.** The mapping moved the gripper with a
  `JointPositionList` of threshold 0 beside a `LocalMinimumReached` with a joint
  convergence threshold of 0.1 and a minimum threshold of 0, either of which ended the
  motion. It does not fit yet, because `MoveGripper` builds its children when it is
  created, so its fields cannot be changed afterwards and the whole goal has to be
  replaced, and it may be the body of an action or a step of a plan language node.
  Options: check whether `MoveGripper(tolerate_stall=True, stall_minimum_time=...)`
  already covers what the Stretch needs; otherwise a transformation over `MoveGripper`
  that replaces it wherever it runs.

## Problems the bowl and cup plan ran into

These park no tests; `test/coraplex_test/test_bowl_and_cup.py` works around them.

### An opened drawer slides shut while unrelated motions run

After `OpenAction` pulled the kitchen's `sink_area_left_middle_drawer_main_joint` out
to its limit of 0.48 m, the drawer stood at 0.31 m when the plan ended, in the run
without collision avoidance. It moves while no running node refers to it: most of the
way while `MoveTorsoAction` raises the torso (0.44 m to 0.32 m over about 400 ticks),
and a few millimetres during each `ParkArmsAction`. With collision avoidance the same
plan ended at 0.44 m. During the pick-ups it also moves towards the grippers, because
their goals are expressed relative to the objects lying in the drawer, so the drawer
joint is on the kinematic chain of the goal.

The drawer is a degree of freedom of the environment that the controller is free to
move. Why it gets a velocity from motions that do not involve it is not yet known. The
test therefore asserts where the bowl and the cup end up, and not that the drawer stays
open. Options: find out which constraint or solver tolerance moves it; or let the
controller move a degree of freedom of the environment only while a node asks for it,
as `Open` and `Close` do.

### `OpenAction` grasps a handle along the x-axis of its body

`OpenAction` and `CloseAction` take hold of a handle with
`GraspCandidate.from_body_origin(handle)`: at the origin of the handle's body,
approaching along its x-axis and closing the fingers along its y-axis. The handle links
of `kitchen-small.urdf` and `kitchen.urdf` have their x-axis pointing out of the
furniture and their y-axis along the bar, so the gripper is sent to the handle from
inside the furniture and the motion stalls. The handles of the apartment happen to
point the way the grasp expects.

The test adds a frame at the handle's origin that points into the furniture and across
the bar (`add_handle_frame`) and annotates that frame as the `Handle`. Options:
`OpenAction` and `CloseAction` take the grasp from `Handle.grasp_candidates`, and
`Handle` derives it from its geometry and the body it opens; or the annotations of the
kitchen carry the grasp frame of each handle.
