---
jupyter:
  jupytext:
    text_representation:
      extension: .md
      format_name: markdown
      format_version: '1.3'
      jupytext_version: 1.16.3
  kernelspec:
    display_name: Python 3 (ipykernel)
    language: python
    name: python3
---

# Plan Language

The CoraPlex plan language structures what a plan does. It is the set of cramph composites: statechart nodes that run
their children in a given order and decide, from how the children ended, whether they succeeded themselves. A plan is a
tree of these composites with actions at its leaves, built on its own and then compiled and executed by a
{class}`~coraplex.plans.executors.PlanExecutor`.

| Name                | Description                                                                                                         |
|---------------------|---------------------------------------------------------------------------------------------------------------------|
| **Sequence**        | Runs its children one after another and fails as soon as one of them fails.                                         |
| **TryInOrder**      | Runs its children one after another until one succeeds, and fails only if all of them failed.                      |
| **Parallel**        | Holds all children at once and succeeds once enough of them, all by default, are at their goals together.          |
| **TryAll**          | Runs all children at once and succeeds once one of them succeeded.                                                  |
| **RepeatUntil**     | Attempts a child again whenever an attempt fails, until it succeeds or a monitor calls the repeating off.           |
| **Monitored nodes** | `CancelledWhenTrue`, `PausedWhileTrue` and `PausedUntilTrue` cancel or pause a child depending on a monitor.        |

# Setup the World

If you are performing a plan with a simulated robot, you need a world, and an executor running the plan in it. The
`run` function below gives every plan an executor of its own, since an executor runs one statechart.

```python
from coraplex.testing import setup_world
from semantic_digital_twin.robots.pr2 import PR2

world = setup_world()
pr2 = PR2.from_world(world)

from coraplex.plans.context_extensions import RobotAccess
from coraplex.plans.executors import SimulatedPlanExecutor
from cramph.statechart import Statechart

extensions = [RobotAccess(pr2)]

def run(plan):
    """
    Run `plan` simulated in `world`, with the robot and settings in `extensions`.
    """
    executor = SimulatedPlanExecutor(world, context_extensions=extensions)
    statechart = Statechart(context=executor.context)
    statechart.add_node(plan)
    executor.compile(statechart)
    executor.execute()
    return executor
```

## Sequence

A sequence runs its children one after another. If one of them fails, the sequence fails and the children after it
never start.

We will start with a simple example that moves the robot and parks its arms.

```python
from coraplex.robot_plans.actions.core.navigation import NavigateAction
from coraplex.robot_plans.actions.core.robot_body import ParkArmsAction
from cramph.composites import Sequence
from semantic_digital_twin.spatial_types import Pose

navigate = NavigateAction(target_location=Pose.from_xyz_rpy(1, 1, 0, reference_frame=world.root))
park = ParkArmsAction(arms=pr2.all_arms)

plan = Sequence(nodes=[navigate, park])
```

The plan is executed by putting it into a statechart of a simulated executor, compiling and executing it.

```python
run(plan)
```

Afterwards the statechart the plan ran in can be inspected in an interactive visualization.

```python
plan.statechart.visualize()
```

## Try In Order

Try in order also runs its children one after another, but a failing child does not end it: the next child is tried
instead. It fails only if all of its children failed.

```python
from coraplex.robot_plans.actions.core.navigation import NavigateAction
from coraplex.robot_plans.actions.core.robot_body import ParkArmsAction
from cramph.composites import TryInOrder
from semantic_digital_twin.spatial_types import Pose

navigate = NavigateAction(target_location=Pose.from_xyz_rpy(1, 1, 0, reference_frame=world.root))
park = ParkArmsAction(arms=pr2.all_arms)

plan = TryInOrder(nodes=[navigate, park])

run(plan)
```

## Parallel

Parallel holds all of its children at once, in the same statechart, and succeeds once enough of them, all of them
by default, are at their goals on the same tick.

```python
from coraplex.robot_plans.actions.core.navigation import NavigateAction
from coraplex.robot_plans.actions.core.robot_body import ParkArmsAction
from cramph.composites import Parallel
from semantic_digital_twin.spatial_types import Pose

navigate = NavigateAction(target_location=Pose.from_xyz_rpy(1, 1, 0, reference_frame=world.root))
park = ParkArmsAction(arms=pr2.all_arms)

plan = Parallel(nodes=[navigate, park])

run(plan)
```

## Try All

TryAll is to Parallel what TryInOrder is to Sequence: it runs all of its children at once and succeeds once one of
them succeeded.

```python
from coraplex.robot_plans.actions.core.navigation import NavigateAction
from coraplex.robot_plans.actions.core.robot_body import ParkArmsAction
from cramph.composites import TryAll
from semantic_digital_twin.spatial_types import Pose

navigate = NavigateAction(target_location=Pose.from_xyz_rpy(1, 1, 0, reference_frame=world.root))
park = ParkArmsAction(arms=pr2.all_arms)

plan = TryAll(nodes=[navigate, park])

run(plan)
```

## Combination of Expressions

Composites are statechart nodes themselves, so they nest. For example, a Sequence can run as one child of a Parallel.

```python
from coraplex.robot_plans.actions.core.navigation import NavigateAction
from coraplex.robot_plans.actions.core.robot_body import MoveTorsoAction, ParkArmsAction
from cramph.composites import Parallel, Sequence
from semantic_digital_twin.datastructures.definitions import TorsoState
from semantic_digital_twin.spatial_types import Pose

navigate = NavigateAction(target_location=Pose.from_xyz_rpy(1, 1, 0, reference_frame=world.root))
park = ParkArmsAction(arms=pr2.all_arms)
move_torso = MoveTorsoAction(torso_state=TorsoState.HIGH)

plan = Parallel(nodes=[navigate, Sequence(nodes=[park, move_torso])])

run(plan)
```

In this case 'park' and 'move_torso' form a Sequence, and that Sequence runs in parallel with 'navigate'.

## Code Objects

A plan can also call Python code. A {class}`~cramph.threaded_nodes.FunctionCall` calls its function in a thread
of its own and succeeds once the function returned.

The function can either be a lambda expression or, for more complex code, a function.

```python
from cramph.threaded_nodes import FunctionCall
from coraplex.robot_plans.actions.core.robot_body import ParkArmsAction
from cramph.composites import Parallel


def code_test():
    print("-" * 20)
    print("Code function")


park = ParkArmsAction(arms=pr2.all_arms)
code_lambda = FunctionCall(function=lambda: print("This is from the code object"))
code_func = FunctionCall(function=code_test)

plan = Parallel(nodes=[park, code_lambda, code_func])

run(plan)
```

## Exception Handling

A step that fails lets its composite decide what follows: a Sequence fails as well, while TryInOrder and TryAll go on
with their other children and only fail if all of them failed. A
{class}`~cramph.threaded_nodes.FunctionCall` fails when its function raises one of its `failure_types`, here a
{class}`~coraplex.plans.failures.PlanFailure`. Any other exception, such as a KeyError, is raised out of the
execution.

We will see how a failure is handled at a simple example using TryAll, so that a failing step does not fail the whole
plan.

```python
from coraplex.plans.failures import PlanFailure
from cramph.threaded_nodes import FunctionCall
from coraplex.robot_plans.actions.core.navigation import NavigateAction
from cramph.composites import TryAll
from semantic_digital_twin.spatial_types import Pose


def code_test():
    raise PlanFailure


navigate = NavigateAction(target_location=Pose.from_xyz_rpy(1, 1, 0, reference_frame=world.root))
code_func = FunctionCall(function=code_test, failure_types=(PlanFailure,))

plan = TryAll(nodes=[navigate, code_func])

run(plan)

print(plan.life_cycle_state)
print(code_func.life_cycle_state)
```

## Repeat

{class}`~giskardpy.motion_statechart.goals.templates.RepeatOnStall` attempts a task again whenever an attempt stops
making progress, until the task succeeds or its stop monitor fires. Counting the attempts with
{class}`~cramph.monitors.CountNodeResets` limits how often it tries, and the exception it is given is raised once the
attempts run out.

```python
from cramph.exceptions import RepetitionsExhausted
from coraplex.robot_plans.actions.core.robot_body import MoveTorsoAction
from cramph.composites import Sequence
from cramph.monitors import CountNodeResets
from giskardpy.motion_statechart.goals.templates import RepeatOnStall
from semantic_digital_twin.datastructures.definitions import TorsoState

move_torso = Sequence(nodes=[MoveTorsoAction(torso_state=TorsoState.HIGH), MoveTorsoAction(torso_state=TorsoState.LOW)])

plan = RepeatOnStall(
    task=move_torso,
    stop_retry_monitor=CountNodeResets(node=move_torso, target=3),
    exception=RepetitionsExhausted(repeated_node=move_torso, maximum_repetitions=3),
)

run(plan)
```

## Monitors

A monitor lets you attach a condition to a part of the plan that is evaluated alongside it, so it can act on that part
while it is running. The condition is a statechart node, for instance a monitor that turns True after a fixed amount of
simulation time.

There are three monitored nodes for this:

* {class}`~cramph.composites.CancelledWhenTrue` stops its node once the monitor observes True and gives up on the plan
  with the exception it is given, such as {class}`~coraplex.plans.failures.PlanCancelled`, instead of leaving the rest
  of the plan waiting for a subtree that will not finish.
* {class}`~cramph.composites.PausedWhileTrue` holds its node for as long as the monitor observes True.
* {class}`~cramph.composites.PausedUntilTrue` holds its node until the monitor observes True, then lets it run.

For the example we will move the torso up and down, and stop it after 2 seconds of simulation time. Since cancelling
gives up on the plan, executing it raises {class}`~coraplex.plans.failures.PlanCancelled`.

```python
from cramph.exceptions import PlanCancelled
from coraplex.robot_plans.actions.core.robot_body import MoveTorsoAction
from cramph.composites import CancelledWhenTrue, Sequence
from cramph.monitors import CountSimulationTimeSeconds
from semantic_digital_twin.datastructures.definitions import TorsoState

two_seconds = CountSimulationTimeSeconds(seconds=2)

plan = CancelledWhenTrue(
    monitor=two_seconds,
    monitored_node=Sequence(
        nodes=[MoveTorsoAction(torso_state=TorsoState.HIGH), MoveTorsoAction(torso_state=TorsoState.LOW)]
    ),
    exception=PlanCancelled(monitor=two_seconds),
)

try:
    run(plan)
except PlanCancelled as cancelled:
    print(cancelled)
```

{class}`~cramph.composites.PausedUntilTrue` can be used the same way to launch a subtree in a paused state that is only
released once the monitor's condition is fulfilled.

```python
from coraplex.robot_plans.actions.core.robot_body import MoveTorsoAction
from cramph.composites import PausedUntilTrue, Sequence
from cramph.monitors import CountSimulationTimeSeconds
from semantic_digital_twin.datastructures.definitions import TorsoState

plan = PausedUntilTrue(
    monitor=CountSimulationTimeSeconds(seconds=2),
    monitored_node=Sequence(
        nodes=[MoveTorsoAction(torso_state=TorsoState.HIGH), MoveTorsoAction(torso_state=TorsoState.LOW)]
    ),
)

run(plan)
```
This will hold the wrapped plan for the first 2 seconds of simulation time before letting it run.
