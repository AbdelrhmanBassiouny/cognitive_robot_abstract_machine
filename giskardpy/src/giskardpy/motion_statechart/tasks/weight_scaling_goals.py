from dataclasses import dataclass

import krrood.symbolic_math.symbolic_math as sm
from giskardpy.motion_statechart.context import MotionStatechartContext
from giskardpy.motion_statechart.graph_node import Task, NodeArtifacts
from semantic_digital_twin.world_description.world_entity import Body


@dataclass
class MaxManipulability(Task):
    """
    This goal maximizes the manipulability of the kinematic chain between root_link and tip_link.
    This chain should only include rotational joint and no linear joints i.e. torso lift joints or odometry joints.
    """

    root_link: Body
    tip_link: Body
    m_threshold: float = 0.5

    def build(self, context: MotionStatechartContext) -> NodeArtifacts:
        artifacts = NodeArtifacts()
        root_P_tip = context.world.compose_forward_kinematics_expression(
            self.root_link, self.tip_link
        ).to_position()[:3]

        symbols = root_P_tip.free_variables()
        e = sm.vstack([root_P_tip])
        J = e.jacobian(symbols)
        JJT = J.dot(J.T)
        m = sm.sqrt(JJT.det())

        artifacts.geometry.add_position_constraint(
            reference_velocity=1,
            expr_goal=self.m_threshold,
            quadratic_weight=1,
            expr_current=m,
            name=self.name,
        )

        artifacts.observation = sm.abs(self.m_threshold - m) <= 0.01
        return artifacts
