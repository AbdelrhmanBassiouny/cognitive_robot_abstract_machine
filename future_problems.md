# Future problems

Problems set aside until the statechart refactoring of `plan-cramp-second-iter` is
done. No test is parked for any of them at the moment. A test that has to wait for one
is marked `@pytest.mark.parked` (or `pytestmark = pytest.mark.parked` for a whole
module) and skipped. Once a problem is solved, remove the marker from its tests and its
entry from this file.

## Sending statecharts as JSON

- Whether an underspecified statement (a krrood `Match`) has to survive JSON at all.
  Today `StatementNode.statement` is not serialized, and the node is sent as the
  `CompositeNodeChoosingItsChild` it is, so the receiving process asks the sender for
  each child instead of grounding the statement itself. Tests covering that, and a
  statement inside a sent statechart, are still to be written.
- `FunctionCall` and `ThreadedPredicateMonitor` hold a Python callable and cannot be
  sent; writing a statechart holding one raises `ClassNotSerializableError`. They have
  no round-trip case.

## Design questions set aside

Design changes the review of ichumuh#8 raised and that were deliberately left for
later.

### A statechart that takes its context from its executor

Building a plan's statechart still reads `Statechart(context=executor.context)`. The
statechart could instead get its context from the executor compiling it, but a node
expands the moment it joins a statechart (`Statechart.add_node`), and expanding reads
the context, so the context would have to be known before the executor is, or
expansion would have to move to compile time. That is a cramph change of its own.

### Steps of the composite actions typed as statements

The steps of the composite actions are typed as the action they hold
(`pick_up: MoveAndPickUpAction`) although they may hold a `Match`. Typing them
`MoveAndPickUpAction | Match` makes ORMatic leave the field out of the data access
object, so a stored transport loses its steps; ORMatic needs to map such a union first.

### The trial's own sequence around a candidate

`ActionTrial.succeeds` runs a candidate in a `Sequence` of its own, so that the nodes a
plan transformation puts beside it are tried with it, the way the candidate runs for
real inside the `/steps` sequence its `StatementNode` chose. Simon would rather not wrap the
candidate; doing without it needs plan transformations that can insert beside a node
no language node runs.

### Holding still inside `StatechartCompiler.compile`

Waiting for every `RecompileCallback` to come to rest happens around a world-structure
rebuild and before a node chooses its child (`StatechartCompiler.when_held_still`), not inside
`StatechartCompiler.compile` itself. A compile that waits has to leave the statechart ticking
with nodes it has not compiled yet, but the state arrays grow the moment a node joins
and the compiled tick keeps reading the arrays it was compiled against, so the tick
would run on stale state until the compile happened.

### Robot-specific motions that were not ported to plan transformations

Of the per-robot mappings of the removed `coraplex/alternative_motion_mappings`, these
have no plan transformation in
`coraplex/robot_plans/robot_specific_plan_transformations.py`:

- **HSRB, real robot: driving through Navigation 2.** The mapping replaced the drive goal
  with a `NavigateActionServerTask` on the action topic `/hsrb/move_base`, sending a
  `nav2_msgs` `NavigateToPose`. It does not fit yet, because `nav2_msgs` is an optional
  dependency that the old module, like `giskardpy/motion_statechart/ros2_nodes/ros_tasks.py`,
  imported inside a try-except, and the topic was a literal in the code. Options: a
  transformation over `DrivesBase` like the differential drive ones, with `nav2_msgs`
  imported unguarded and the topic as a field of the transformation; or the HSRB's robot
  view naming its navigation action server.
- **Stretch, real robot only: tool center point motion and gripper stalls.** In
  simulation the Stretch needs neither of its old mappings any more: it transports and
  opens containers with the plain goals (`test_transport`, `test_transport_open_container`
  in `test_multi_robot_action_designator.py`), and `FaceAtAction` already turns the side
  its arm reaches out on towards a target, as the mapping once did. Still to be checked
  on the real Stretch, whose tracking lags, is whether it needs what the mappings did
  beyond that:
  - moving the tool frame on a straight line (`CartesianPoseStraight`) with the base's
    heading held, and counting the motion as done once the joints stand still
    (`LocalMinimumReached`, threshold 0.025) instead of failing it as stalled;
  - grasps that tolerate stalled fingers. `MoveGripper(tolerate_stall=True,
    stall_minimum_time=...)` already builds what the gripper mapping did, but a grasp
    only uses it with `tolerate_grasp_stall=True`, which is off by default.

  If the real robot needs the tool center point motion, it needs a goal type of its own
  for moving a tool center point, so a transformation can match it:
  `MovesToolCenterPoint.tool_center_point_goal` builds a plain `CartesianPose` or
  `CartesianPosition` inside many actions.


# real robot problems
- motion statechart inspector doesn't work