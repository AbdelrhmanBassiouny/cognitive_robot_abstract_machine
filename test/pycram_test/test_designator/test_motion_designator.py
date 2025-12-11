from copy import deepcopy

from pycram.datastructures.enums import ApproachDirection, VerticalAlignment, Arms
from pycram.datastructures.grasp import GraspDescription
from pycram.datastructures.pose import PoseStamped
from pycram.language import SequentialPlan
from pycram.process_module import simulated_robot
from pycram.robot_plans import MoveMotion, BaseMotion, PickUpActionDescription
from pycram.testing import ApartmentWorldTestCase
from semantic_digital_twin.robots.pr2 import PR2


class TestActionDesignatorGrounding(ApartmentWorldTestCase):

    def test_pick_up_motion(self):
        test_world = deepcopy(self.world)
        test_robot = PR2.from_world(test_world)
        grasp_description = GraspDescription(
            ApproachDirection.FRONT, VerticalAlignment.NoAlignment, False
        )
        description = PickUpActionDescription(
            test_world.get_body_by_name("milk.stl"), [Arms.LEFT], [grasp_description]
        )

        plan = SequentialPlan(self.context, description)
        with simulated_robot:
            plan.perform()

        motion_nodes = list(filter(lambda x: isinstance(x, BaseMotion), plan.nodes))

        self.assertEqual(len(motion_nodes), 1)
