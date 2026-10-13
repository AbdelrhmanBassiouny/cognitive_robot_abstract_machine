## Stage 4 - the open plan runs (PR #369, draft, branch
`claude/the-open-plan-runs`, on #368)

Rewritten by the refactor round below. What stands now:
- `experiments/open_slots/plan.py` - `sorting_plan(board, lid, arm, end_effector)`,
  the figure's whole plan written once: `sequential([a(PickUpAction)(...),
  an(InsertionAction)(...)])` with all its slots open.
- `coraplex.plans.plan_node.PlanNode.grounded_by(backend)` - the general machinery that
  answers a stated plan.
- `experiments/scripts/framework_demo.py` - builds the simulated lab, looks, writes the
  plan and grounds it, reporting which backend answered which slot.
- `framework.pdf`/`framework.typ` untouched by this stage.


## The plan performs (still #369)
The ask: make the plan performable on the demo, and film it from the robot's camera and
from a front view.

Done:
- **`ActuatorDrivenAction`** in `pick_and_place_action.py`: a `SubClassSafeGeneric`
  family whose members bind the plan action each carries out (`PickUpActionMujoco` ->
  `PickUpAction`, and so on). `ActuatorDrivenAction.performing(resolved, simulation,
  actuators)` turns a resolved plan into the actions that drive this lab, and
  `NoActionCarriesItOut` where nothing does.
- **The grasp is read.** `_top_down_pose_builder` -> `_grasp_pose_builder(world, robot,
  arm, grasp)`, turned by `grasp.grasp_orientation()`; all three MuJoCo actions now take
  a `grasp_description`. The old fixed `pitch=pi` is exactly `RIGHT`+`TOP`, so the
  existing demos (all `FRONT`+`TOP`) now grasp rotated 90 degrees about the vertical -
  `test_tracy_pickup_demo_mujoco.py` is the check on that.
- **The plan says the hand comes down on the piece** (`FROM_ABOVE = TOP`), since a piece
  resting on a surface offers the fingers nothing else; only the approach direction is
  sampled, and every sample is then performable. Both actions state the one grasp.
