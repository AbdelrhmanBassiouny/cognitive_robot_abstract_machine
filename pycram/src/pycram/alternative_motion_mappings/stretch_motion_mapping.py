from giskardpy.motion_statechart.tasks.cartesian_tasks import CartesianPose
from pycram.datastructures.enums import ExecutionType
from pycram.robot_description import ViewManager
from pycram.robot_plans import MoveTCPMotion
from pycram.robot_plans.motions.base import AlternativeMotion
from semantic_digital_twin.robots.stretch import Stretch


class StretchMoveTCPSim(MoveTCPMotion, AlternativeMotion[Stretch]):

    execution_type = ExecutionType.SIMULATED

    def perform(self):
        return

    @property
    def _motion_chart(self) -> CartesianPose:
        tip = ViewManager().get_end_effector_view(self.arm, self.robot_view).tool_frame
        return CartesianPose(
            root_link=self.world.root,
            tip_link=tip,
            goal_pose=self.target.to_spatial_type(),
        )


class StretchMoveTCPReal(MoveTCPMotion, AlternativeMotion[Stretch]):

    execution_type = ExecutionType.REAL

    def perform(self):
        return

    @property
    def _motion_chart(self) -> CartesianPose:
        tip = ViewManager().get_end_effector_view(self.arm, self.robot_view).tool_frame
        return CartesianPose(
            root_link=self.world.root,
            tip_link=tip,
            goal_pose=self.target.to_spatial_type(),
        )
