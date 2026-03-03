from giskardpy.qp.solvers.qp_solver_ids import SupportedQPSolver

from conftest import robot_factory
from giskardpy.executor import Executor, SimulationPacer
from giskardpy.motion_statechart.context import MotionStatechartContext
from giskardpy.motion_statechart.goals.templates import Sequence
from giskardpy.motion_statechart.graph_node import EndMotion
from giskardpy.motion_statechart.monitors.overwrite_state_monitors import (
    SetSeedConfiguration,
)
from giskardpy.motion_statechart.motion_statechart import MotionStatechart
from giskardpy.motion_statechart.tasks.cartesian_tasks import (
    CartesianPose,
    CartesianPosition,
)
from giskardpy.motion_statechart.tasks.joint_tasks import JointPositionList
from giskardpy.qp.qp_controller_config import QPControllerConfig
from semantic_digital_twin.adapters.ros.visualization.viz_marker import (
    VizMarkerPublisher,
)
from semantic_digital_twin.datastructures.joint_state import JointState
from semantic_digital_twin.spatial_types import HomogeneousTransformationMatrix, Point3


def test_joint_goal(fucking_huge_robot, rclpy_node):
    VizMarkerPublisher(_world=fucking_huge_robot, node=rclpy_node).with_tf_publisher()
    msc = MotionStatechart()
    goal = 1

    msc.add_node(
        node1 := JointPositionList(
            goal_state=JointState.from_str_dict(
                {
                    "map_T_link1": goal,
                    "link1_T_link2": goal,
                    "link2_T_link3": goal,
                    "link3_T_link4": goal,
                    "link4_T_link5": goal,
                    "link5_T_eef": goal,
                },
                world=fucking_huge_robot,
            )
        )
    )
    msc.add_node(EndMotion.when_true(node1))

    kin_sim = Executor(
        MotionStatechartContext(world=fucking_huge_robot),
        pacer=SimulationPacer(real_time_factor=1),
    )
    kin_sim.compile(motion_statechart=msc)

    kin_sim.tick_until_end()


def execute(link_length: float, vel_limit: float, rclpy_node):
    fucking_huge_robot = robot_factory(
        fucking_huge_link_length=link_length, vel_limit=vel_limit
    )
    VizMarkerPublisher(_world=fucking_huge_robot, node=rclpy_node).with_tf_publisher()
    msc = MotionStatechart()
    goal = 1
    eef = fucking_huge_robot.get_kinematic_structure_entity_by_name("eef")

    msc.add_node(
        node1 := Sequence(
            [
                SetSeedConfiguration(
                    seed_configuration=JointState.from_str_dict(
                        {
                            "map_T_link1": goal,
                            "link1_T_link2": goal,
                            "link2_T_link3": goal,
                            "link3_T_link4": goal,
                            "link4_T_link5": goal,
                            "link5_T_eef": goal,
                        },
                        world=fucking_huge_robot,
                    )
                ),
                CartesianPosition(
                    root_link=fucking_huge_robot.root,
                    tip_link=eef,
                    goal_point=Point3(y=-link_length, reference_frame=eef),
                    reference_velocity=0.2 * link_length,
                    # reference_angular_velocity=0.2 * 1000,
                ),
                # CartesianPose(
                #     root_link=fucking_huge_robot.root,
                #     tip_link=eef,
                #     goal_pose=HomogeneousTransformationMatrix.from_xyz_rpy(
                #         y=-link_length, reference_frame=eef
                #     ),
                #     reference_linear_velocity=0.2 * link_length,
                #     # reference_angular_velocity=0.2 * 1000,
                # ),
            ]
        )
    )
    msc.add_node(EndMotion.when_true(node1))

    kin_sim = Executor(
        MotionStatechartContext(
            world=fucking_huge_robot,
            qp_controller_config=QPControllerConfig(
                target_frequency=100,
                prediction_horizon=35,
                # qp_solver_id=SupportedQPSolver.gurobi,
            ),
        ),
        pacer=SimulationPacer(real_time_factor=2),
    )
    kin_sim.compile(motion_statechart=msc)

    kin_sim.tick_until_end(10_000)


def test_cart_goal(rclpy_node):
    execute(0.1, 0.1, rclpy_node)


def test_cart_goal3(rclpy_node):
    execute(0.1, 0.1, rclpy_node)
