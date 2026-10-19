---
jupyter:
  jupytext:
    text_representation:
      extension: .md
      format_name: markdown
      format_version: '1.3'
      jupytext_version: 1.16.3
  kernelspec:
    display_name: Python 3
    language: python
    name: python3
---

# Motions

A motion is a single giskard goal: the smallest thing the robot does, such as driving the base, moving a tool center
point or opening a gripper. Actions build them, and a plan collects them into one motion state chart that is executed as
a whole. You can also mount a goal in a plan yourself, which is what this page does.

Goals live in {mod}`giskardpy.motion_statechart`: the leaf tasks in `tasks`, the composite goals in `goals`. They take
world entities rather than names, so a goal says which body moves relative to which other body.

We need a robot to move, so we start with a world and a PR2.

```python
from coraplex.testing import setup_world
from semantic_digital_twin.robots.pr2 import PR2


world = setup_world()
pr2_view = PR2.from_world(world)

from coraplex.plans.context_extensions import RobotAccess
from coraplex.plans.executors import KinematicallySimulatedPlanExecutor
from cramph.statechart import Statechart

extensions = [RobotAccess(pr2_view)]

def run(plan):
    """
    Run `plan` simulated in `world`, with the robot and settings in `extensions`.
    """
    executor = KinematicallySimulatedPlanExecutor(world, context_extensions=extensions)
    statechart = Statechart(context=executor.context)
    statechart.add_node(plan)
    executor.compile(statechart)
    executor.execute()
    return executor
```

## Driving the base

In simulation the base is placed by writing the odometry, because there is no drive to follow a pose. On a real robot
the same plan commands the pose instead; {class}`~coraplex.robot_plans.actions.core.navigation.NavigateAction` picks
between the two for you.

```python
from giskardpy.motion_statechart.monitors.overwrite_state_monitors import SetOdometry
from semantic_digital_twin.spatial_types.spatial_types import Pose

target = Pose.from_xyz_quaternion(pos_x=1.0, reference_frame=world.root)
goal = SetOdometry(
    base_pose=target.homogeneous_matrix,
    odom_connection=pr2_view.root.parent_connection,
)

run(goal)
```

## Moving the tool center point

{class}`~giskardpy.motion_statechart.tasks.cartesian_tasks.CartesianPose` moves one body to a pose expressed relative to
another. For a tool center point, the tip is the arm's tool frame.

```python
from giskardpy.motion_statechart.tasks.cartesian_tasks import CartesianPose

end_effector = pr2_view.left_arm.end_effector
goal = CartesianPose(
    root_link=RobotAccess(pr2_view).controlled_root,
    tip_link=end_effector.tool_frame,
    goal_pose=Pose.from_xyz_quaternion(
        1.5, 0.6, 0.6, 0, 0, 0, 1, reference_frame=world.root
    ),
)

run(goal)
```

{attr}`~coraplex.plans.context_extensions.RobotAccess.controlled_root` is the link the goal is expressed relative to: the
world root for a robot that drives its base while it manipulates, and the robot's own root otherwise.

## Looking at something

{class}`~giskardpy.motion_statechart.tasks.pointing.Pointing` turns a camera's forward axis towards a point.

```python
from giskardpy.motion_statechart.tasks.pointing import Pointing

camera = pr2_view.get_default_camera()
goal = Pointing(
    root_link=pr2_view.get_torso().root,
    tip_link=camera.root,
    goal_point=Pose.from_xyz_quaternion(
        1, 1, 1, 0, 0, 0, 1, reference_frame=world.root
    ).position,
    pointing_axis=camera.forward_facing_axis,
)

run(goal)
```

## Opening and closing a gripper

{class}`~giskardpy.motion_statechart.goals.gripper.MoveGripper` drives a gripper to one of the states its end effector
defines. It reads the finger positions off the end effector, so the same goal works on any robot.

```python
from giskardpy.motion_statechart.goals.gripper import MoveGripper
from semantic_digital_twin.datastructures.definitions import GripperState

goal = MoveGripper(end_effector=end_effector, state=GripperState.OPEN)

run(goal)
```

Closing onto an object is the interesting case: the fingers stop short of the position they were commanded, so
`tolerate_stall=True` lets fingers that stopped moving count as done, and `allow_gripper_collision=True` lets them touch
what they grasp.

```python
goal = MoveGripper(
    end_effector=end_effector,
    state=GripperState.CLOSE,
    tolerate_stall=True,
    allow_gripper_collision=True,
)

run(goal)
```

## Detecting an object

{class}`~coraplex.perception.PerceptionTask` answers a perception query inside the chart and writes what it saw into the
world, so a goal planned after it binds the corrected pose.
{class}`~coraplex.robot_plans.actions.core.misc.DetectAction` builds one for you and is the usual way to perceive.

## Moving joints

{class}`~giskardpy.motion_statechart.tasks.joint_tasks.JointPositionList` drives any set of joints to target positions.
It takes the connections themselves, so the joints are named once, in the world model.

```python
from giskardpy.motion_statechart.tasks.joint_tasks import JointPositionList, JointState

goal = JointPositionList(
    goal_state=JointState.from_mapping(
        {
            world.get_connection_by_name("torso_lift_joint"): 0.2,
            world.get_connection_by_name("r_shoulder_pan_joint"): -1.2,
        }
    )
)

run(goal)
```
