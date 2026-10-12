# Future problems

Problems set aside until the statechart refactoring of `plan-cramp-second-iter` is
done. Every test listed here is marked `@pytest.mark.parked` (or `pytestmark =
pytest.mark.parked` for a whole module) and skipped. Once a problem is solved, remove
the marker from its tests and its entry from this file.

## Sending statecharts as JSON

The structure of plans, actions and contexts is still changing (one statechart context
instead of coraplex's own, statecharts without a root node, actions owning their body),
and each of those changes what a statechart's JSON holds. Keeping the round trips green
in the meantime would mean rewriting them for every intermediate shape, so they are
parked until the structure has settled.

Parked whole modules:

- `test/cramph_test/test_statechart/test_json_parsing.py`
- `test/cramph_test/test_statechart/test_extending_from_json.py`
- `test/giskardpy_test/test_motion_statechart/test_json_parsing.py`

Parked tests in otherwise active modules:

- `test/cramph_test/test_statechart/test_statechart.py`: `test_nested_goals`,
  `test_it_survives_a_json_round_trip`,
  `test_a_condition_with_a_predicate_survives_a_json_round_trip`,
  `test_nested_success_condition_survives_json_round_trip`
- `test/giskardpy_test/test_motion_statechart/test_collision_avoidance_tasks.py`:
  `test_external_collision_avoidance`,
  `test_external_collision_avoidance_with_weight_above_ca`,
  `test_self_collision_avoidance`, `test_hard_constraints_violated` (they execute the
  statechart that came back from a JSON round trip)
- `test/giskardpy_test/test_motion_statechart/test_composed_goals.py`:
  `test_velocity_limit_has_its_two_limits_after_a_json_round_trip`
- `test/coraplex_test/test_perception.py`:
  `test_perception_task_survives_a_json_round_trip`,
  `test_perception_task_survives_a_chart_round_trip`
- `test/coraplex_test/test_plan/test_plan_statechart.py`:
  `test_an_underspecified_node_is_sent_as_a_node_choosing_its_child`,
  `test_an_expanded_action_is_received_with_the_nodes_it_runs`

Open questions to settle when this is picked up again:

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
- A giskardpy `MoveGripper` does not survive a JSON round trip: its fail condition
  references nodes outside its scope after deserialization
  (`UnserializableGoalError`/`ConditionScopeError`). This breaks the real-stretch
  cross-process demo, parked as
  `test/experiments_test/real_stretch_demo_test/test_real_stretch_demo_process_boundary.py`:
  `test_demonstration_runs_against_a_controller_in_another_process`.

## ROS 2 goals

Everything that sends a goal to Giskard over ROS 2 sends its statechart as JSON, so it
waits for the problem above.

- `test/giskardpy_test/test_motion_statechart/test_ros.py`
- `test/giskardpy_test/test_ros2_stuff/test_abort_exceptions.py`
- `test/giskardpy_test/test_ros2_stuff/test_child_choices.py`
- `test/giskardpy_test/test_ros2_stuff/test_motion_goal.py`
- `test/giskardpy_test/test_ros2_stuff/test_motion_server.py`
- `test/giskardpy_test/test_ros2_stuff/test_force_torque_nodes.py`
- `test/giskardpy_test/test_ros2_stuff/test_integration_pr2.py`,
  `test_integration_hsr.py`, `test_integration_stretch.py`, `test_integration_daisy.py`
- `test/giskardpy_test/test_ros2_stuff/test_world_updates.py`:
  `test_the_changes_of_a_goal_are_waited_for`,
  `test_changes_that_never_arrive_are_reported`

## Feedback publishing

`giskardpy/middleware/ros2/feedback_publisher.py` reports a running goal's state to the
client, including the nodes waiting for a child. It is parked with the ROS 2 goals.

- `test/giskardpy_test/test_ros2_stuff/test_world_updates.py`:
  `TestRealWorldUpdatesDuringAMotion`, `TestModelChangesOfTheMotionItself`.
  `test_the_robot_is_halted_before_the_motion_is_built_again` expects the control loop
  to halt its command publishers before a recompile. The robot is now decelerated to
  rest by the controller instead (`MotionControl.before_recompile`), so the test has to
  assert that once it is picked up again.
- The feedback assertions of `test_motion_server.py` and `test_child_choices.py`, parked
  with those modules above.

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
(`coraplex/robot_plans/robot_specific_plan_transformations.py`). Three mappings were left out:

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
