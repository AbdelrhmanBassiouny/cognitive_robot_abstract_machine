import os
import time
import unittest

import numpy
import mujoco
from physics_simulators.mujoco_simulator import MujocoSimulator
from physics_simulators.base_simulator import (
    SimulatorConstraints,
    SimulatorState,
    SimulatorCallbackResult,
)

resources_path = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "..",
    "..",
    "semantic_digital_twin",
    "resources",
    "mjcf",
)
headless = os.environ.get("CI", "false").lower() == "true"
# headless = False


class MujocoSimulatorTestCase(unittest.TestCase):
    file_path = os.path.join(resources_path, "floor.xml")
    headless = headless
    step_size = 1e-3

    def test_functions(self):
        simulator = MujocoSimulator(
            _headless=self.headless,
            _step_size=self.step_size,
            file_path=os.path.join(resources_path, "mjx_single_cube_no_mesh.xml"),
        )
        simulator.start(simulate_in_thread=False, render_in_thread=True)

        for step in range(4000):
            if step < 1000:
                result = simulator.callbacks["get_all_body_names"]()
                self.assertIsInstance(result, SimulatorCallbackResult)
                self.assertEqual(
                    result.type,
                    SimulatorCallbackResult.ResultType.SUCCESS_WITHOUT_EXECUTION,
                )
                self.assertEqual(
                    result.result,
                    [
                        "world",
                        "link0",
                        "link1",
                        "link2",
                        "link3",
                        "link4",
                        "link5",
                        "link6",
                        "link7",
                        "hand",
                        "left_finger",
                        "right_finger",
                        "floor",
                        "box",
                    ],
                )

                result = simulator.callbacks["get_all_joint_names"]()
                self.assertIsInstance(result, SimulatorCallbackResult)
                self.assertEqual(
                    result.type,
                    SimulatorCallbackResult.ResultType.SUCCESS_WITHOUT_EXECUTION,
                )
                self.assertEqual(
                    result.result,
                    [
                        "joint1",
                        "joint2",
                        "joint3",
                        "joint4",
                        "joint5",
                        "joint6",
                        "joint7",
                        "finger_joint1",
                        "finger_joint2",
                    ],
                )

            if step == 1000 or step == 3000:
                result = simulator.callbacks["attach"](body_1_name="abc")
                self.assertEqual(
                    SimulatorCallbackResult.ResultType.FAILURE_BEFORE_EXECUTION_ON_MODEL,
                    result.type,
                )
                self.assertEqual("Body 1 abc not found", result.info)

                result = simulator.callbacks["attach"](body_1_name="world")
                self.assertEqual(
                    SimulatorCallbackResult.ResultType.FAILURE_BEFORE_EXECUTION_ON_MODEL,
                    result.type,
                )
                self.assertEqual("Body 1 and body 2 are the same", result.info)

                result = simulator.callbacks["attach"](body_1_name="box")
                self.assertEqual(
                    SimulatorCallbackResult.ResultType.SUCCESS_WITHOUT_EXECUTION,
                    result.type,
                )
                self.assertEqual(
                    "Body 1 box is already attached to body 2 world", result.info
                )

                result = simulator.callbacks["attach"](
                    body_1_name="box", body_2_name="hand"
                )
                self.assertEqual(
                    SimulatorCallbackResult.ResultType.SUCCESS_AFTER_EXECUTION_ON_MODEL,
                    result.type,
                )
                self.assertIn("Attached body 1 box to body 2 hand", result.info)

                result = simulator.callbacks["enable_contact"](
                    body_1_name="box", body_2_name="left_finger"
                )
                self.assertEqual(
                    SimulatorCallbackResult.ResultType.SUCCESS_AFTER_EXECUTION_ON_MODEL,
                    result.type,
                )
                result = simulator.enable_contact(
                    body_1_name="box", body_2_name="right_finger"
                )
                self.assertEqual(
                    SimulatorCallbackResult.ResultType.SUCCESS_AFTER_EXECUTION_ON_MODEL,
                    result.type,
                )

                result = simulator.callbacks["attach"](
                    body_1_name="box", body_2_name="hand"
                )
                self.assertEqual(
                    SimulatorCallbackResult.ResultType.SUCCESS_WITHOUT_EXECUTION,
                    result.type,
                )
                self.assertEqual(
                    "Body 1 box is already attached to body 2 hand", result.info
                )

            if step == 1200:
                result = simulator.callbacks["get_joint_value"](joint_name="joint1")
                self.assertEqual(
                    SimulatorCallbackResult.ResultType.SUCCESS_WITHOUT_EXECUTION,
                    result.type,
                )
                self.assertIsInstance(result.result, float)
                joint1_value = result.result

                result = simulator.callbacks["get_joints_values"](
                    joint_names=["joint1", "joint2"]
                )
                self.assertEqual(
                    SimulatorCallbackResult.ResultType.SUCCESS_WITHOUT_EXECUTION,
                    result.type,
                )
                self.assertIsInstance(result.result, dict)
                self.assertEqual(len(result.result), 2)
                self.assertIn("joint1", result.result)
                self.assertIsInstance(result.result["joint1"], float)
                self.assertIn("joint2", result.result)
                self.assertIsInstance(result.result["joint2"], float)
                self.assertEqual(joint1_value, result.result["joint1"])

                result = simulator.callbacks["get_body_position"](body_name="box")
                self.assertEqual(
                    SimulatorCallbackResult.ResultType.SUCCESS_WITHOUT_EXECUTION,
                    result.type,
                )
                self.assertIsInstance(result.result, numpy.ndarray)
                box_position = result.result

                result = simulator.callbacks["get_body_quaternion"](body_name="box")
                self.assertEqual(
                    SimulatorCallbackResult.ResultType.SUCCESS_WITHOUT_EXECUTION,
                    result.type,
                )
                self.assertIsInstance(result.result, numpy.ndarray)
                box_quaternion = result.result

                result = simulator.callbacks["get_bodies_positions"](
                    body_names=["box", "link0"]
                )
                self.assertEqual(
                    SimulatorCallbackResult.ResultType.SUCCESS_WITHOUT_EXECUTION,
                    result.type,
                )
                self.assertIsInstance(result.result, dict)
                self.assertEqual(len(result.result), 2)
                self.assertIn("box", result.result)
                self.assertIsInstance(result.result["box"], numpy.ndarray)
                self.assertIn("link0", result.result)
                self.assertIsInstance(result.result["link0"], numpy.ndarray)
                self.assertTrue(numpy.allclose(box_position, result.result["box"]))

                result = simulator.callbacks["get_bodies_quaternions"](
                    body_names=["box", "link0"]
                )
                self.assertEqual(
                    SimulatorCallbackResult.ResultType.SUCCESS_WITHOUT_EXECUTION,
                    result.type,
                )
                self.assertIsInstance(result.result, dict)
                self.assertEqual(len(result.result), 2)
                self.assertIn("box", result.result)
                self.assertIsInstance(result.result["box"], numpy.ndarray)
                self.assertIn("link0", result.result)
                self.assertIsInstance(result.result["link0"], numpy.ndarray)
                self.assertTrue(numpy.allclose(box_quaternion, result.result["box"]))

            if step == 800:
                box_position = numpy.array([0.7, 0.0, 1.0])
                result = simulator.callbacks["set_body_position"](
                    body_name="box", position=box_position
                )
                self.assertEqual(
                    SimulatorCallbackResult.ResultType.SUCCESS_AFTER_EXECUTION_ON_DATA,
                    result.type,
                )

                result = simulator.callbacks["get_body_position"](body_name="box")
                self.assertEqual(
                    SimulatorCallbackResult.ResultType.SUCCESS_WITHOUT_EXECUTION,
                    result.type,
                )
                self.assertIsInstance(result.result, numpy.ndarray)
                self.assertTrue(numpy.allclose(box_position, result.result))

                box_position = numpy.array([0.7, 0.0, 2.0])
                result = simulator.callbacks["set_bodies_positions"](
                    bodies_positions={"box": box_position}
                )
                self.assertEqual(
                    SimulatorCallbackResult.ResultType.SUCCESS_AFTER_EXECUTION_ON_DATA,
                    result.type,
                )

                result = simulator.callbacks["get_body_position"](body_name="box")
                self.assertTrue(numpy.allclose(box_position, result.result))

                box_quaternion = numpy.array([0.707, 0.707, 0.0, 0.0])
                box_quaternion /= numpy.linalg.norm(box_quaternion)
                result = simulator.callbacks["set_body_quaternion"](
                    body_name="box", quaternion=box_quaternion
                )
                self.assertEqual(
                    SimulatorCallbackResult.ResultType.SUCCESS_AFTER_EXECUTION_ON_DATA,
                    result.type,
                )

                result = simulator.callbacks["get_body_quaternion"](body_name="box")
                self.assertEqual(
                    SimulatorCallbackResult.ResultType.SUCCESS_WITHOUT_EXECUTION,
                    result.type,
                )
                self.assertIsInstance(result.result, numpy.ndarray)
                self.assertTrue(numpy.allclose(box_quaternion, result.result))

                box_quaternion = numpy.array([0.707, 0.0, 0.707, 0.0])
                box_quaternion /= numpy.linalg.norm(box_quaternion)
                result = simulator.callbacks["set_bodies_quaternions"](
                    bodies_quaternions={"box": box_quaternion}
                )
                self.assertEqual(
                    SimulatorCallbackResult.ResultType.SUCCESS_AFTER_EXECUTION_ON_DATA,
                    result.type,
                )

                result = simulator.callbacks["get_body_quaternion"](body_name="box")
                self.assertTrue(numpy.allclose(box_quaternion, result.result))

                joint1_value = 0.3
                result = simulator.callbacks["set_joint_value"](
                    joint_name="joint1", value=joint1_value
                )
                self.assertEqual(
                    SimulatorCallbackResult.ResultType.SUCCESS_AFTER_EXECUTION_ON_DATA,
                    result.type,
                )

                result = simulator.callbacks["get_joint_value"](joint_name="joint1")
                self.assertEqual(
                    SimulatorCallbackResult.ResultType.SUCCESS_WITHOUT_EXECUTION,
                    result.type,
                )
                self.assertIsInstance(result.result, float)
                self.assertAlmostEqual(joint1_value, result.result, places=3)

                joints_values = {"joint1": joint1_value, "joint2": 0.5}
                result = simulator.callbacks["set_joints_values"](
                    joints_values=joints_values
                )
                self.assertEqual(
                    SimulatorCallbackResult.ResultType.SUCCESS_AFTER_EXECUTION_ON_DATA,
                    result.type,
                )

                result = simulator.callbacks["get_joints_values"](
                    joint_names=["joint1", "joint2"]
                )
                self.assertEqual(
                    SimulatorCallbackResult.ResultType.SUCCESS_WITHOUT_EXECUTION,
                    result.type,
                )
                self.assertIsInstance(result.result, dict)
                self.assertEqual(len(result.result), 2)
                self.assertIn("joint1", result.result)
                self.assertIsInstance(result.result["joint1"], float)
                self.assertIn("joint2", result.result)
                self.assertIsInstance(result.result["joint2"], float)
                self.assertAlmostEqual(joint1_value, result.result["joint1"], places=3)

            if step == 1550:
                result = simulator.callbacks["save"](key_name="step_1550")
                self.assertEqual(
                    SimulatorCallbackResult.ResultType.SUCCESS_WITHOUT_EXECUTION,
                    result.type,
                )
                self.key_id = result.result
                result = simulator.callbacks["load"](key_id=self.key_id)
                self.assertEqual(
                    SimulatorCallbackResult.ResultType.SUCCESS_AFTER_EXECUTION_ON_DATA,
                    result.type,
                )
                self.assertEqual(self.key_id, result.result)

            if step == 1570:
                self.save_file_path = os.path.join(
                    resources_path, "../output/step_1570.xml"
                )
                if not os.path.exists(os.path.dirname(self.save_file_path)):
                    os.makedirs(os.path.dirname(self.save_file_path))
                result = simulator.callbacks["save"](
                    file_path=self.save_file_path, key_name="step_1570"
                )
                self.assertEqual(
                    SimulatorCallbackResult.ResultType.SUCCESS_WITHOUT_EXECUTION,
                    result.type,
                )
                self.key_id = result.result
                result = simulator.callbacks["load"](
                    file_path=self.save_file_path, key_id=self.key_id
                )
                self.assertEqual(
                    SimulatorCallbackResult.ResultType.SUCCESS_AFTER_EXECUTION_ON_DATA,
                    result.type,
                )
                self.assertEqual(self.key_id, result.result)

            if step == 2000 or step == 4000:
                result = simulator.callbacks["detach"](body_name="abc")
                self.assertEqual(
                    SimulatorCallbackResult.ResultType.FAILURE_BEFORE_EXECUTION_ON_MODEL,
                    result.type,
                )
                self.assertEqual("Body abc not found", result.info)

                result = simulator.callbacks["detach"](body_name="world")
                self.assertEqual(
                    SimulatorCallbackResult.ResultType.SUCCESS_WITHOUT_EXECUTION,
                    result.type,
                )
                self.assertEqual("Body world is already detached", result.info)

                result = simulator.callbacks["detach"](body_name="box")
                self.assertEqual(
                    SimulatorCallbackResult.ResultType.SUCCESS_AFTER_EXECUTION_ON_MODEL,
                    result.type,
                )
                self.assertEqual("Detached body box from body hand", result.info)

                result = simulator.callbacks["detach"](body_name="box")
                self.assertEqual(
                    SimulatorCallbackResult.ResultType.SUCCESS_WITHOUT_EXECUTION,
                    result.type,
                )
                self.assertEqual("Body box is already detached", result.info)

            if step == 8000:
                result = simulator.callbacks["get_contact_bodies"](body_name="abc")
                self.assertEqual(
                    SimulatorCallbackResult.ResultType.FAILURE_WITHOUT_EXECUTION,
                    result.type,
                )
                self.assertEqual("Body abc not found", result.info)

                result = simulator.callbacks["get_contact_bodies"](body_name="hand")
                self.assertEqual(
                    SimulatorCallbackResult.ResultType.SUCCESS_WITHOUT_EXECUTION,
                    result.type,
                )
                self.assertIsInstance(result.result, set)

            if step == 100:
                result = simulator.callbacks["get_contact_points"](body_names=["abc"])
                self.assertEqual(
                    SimulatorCallbackResult.ResultType.FAILURE_WITHOUT_EXECUTION,
                    result.type,
                )
                self.assertEqual("Body abc not found", result.info)

                result = simulator.callbacks["get_contact_points"](
                    body_names=["box", "hand"]
                )
                self.assertEqual(
                    SimulatorCallbackResult.ResultType.SUCCESS_WITHOUT_EXECUTION,
                    result.type,
                )
                self.assertIsInstance(result.result, list)
                self.assertEqual(len(result.result), 0)

                result = simulator.callbacks["get_contact_points"](body_names=["world"])
                self.assertEqual(
                    SimulatorCallbackResult.ResultType.SUCCESS_WITHOUT_EXECUTION,
                    result.type,
                )
                self.assertIsInstance(result.result, list)
                self.assertEqual(len(result.result), 4)

            if step == 500 and mujoco.mj_version() < 3005000:
                result = simulator.callbacks["ray_test"](
                    ray_from_position=[0.7, 0.0, 1.0], ray_to_position=[0.7, 0.0, 0.0]
                )
                self.assertEqual(
                    SimulatorCallbackResult.ResultType.SUCCESS_WITHOUT_EXECUTION,
                    result.type,
                )

                result = simulator.callbacks["ray_test"](
                    ray_from_position=[0.7, 0.0, 0.2], ray_to_position=[0.7, 0.0, 0.0]
                )
                self.assertEqual(
                    SimulatorCallbackResult.ResultType.SUCCESS_WITHOUT_EXECUTION,
                    result.type,
                )

                result = simulator.callbacks["ray_test_batch"](
                    ray_from_position=[0.7, 0.0, 0.2],
                    ray_to_positions=[[0.7, 0.0, 1.0], [0.7, 0.0, 0.0]],
                )
                self.assertEqual(
                    SimulatorCallbackResult.ResultType.SUCCESS_WITHOUT_EXECUTION,
                    result.type,
                )
                self.assertAlmostEqual(
                    result.result[1]["hit_position"][2], 0.0599, places=3
                )

            simulator.step()
            time.sleep(0.001)
        simulator.stop()


# @unittest.skip("This test is not meant to be run in CI")
class MujocoSimulatorComplexTestCase(unittest.TestCase):
    file_path = os.path.join(resources_path, "mjx_single_cube_no_mesh.xml")
    Simulator = MujocoSimulator
    headless = headless
    step_size = 5e-4

    def test_running_in_10s_in_1(self):
        simulator = MujocoSimulator(_headless=self.headless, _step_size=self.step_size, file_path=self.file_path)
        constraints = SimulatorConstraints(max_real_time=10.0)
        simulator.start(
            constraints=constraints, simulate_in_thread=True, render_in_thread=True
        )
        while simulator.state != SimulatorState.STOPPED:
            time.sleep(1)
        self.assertIs(simulator.state, SimulatorState.STOPPED)

    def test_running_in_10s_2(self):
        simulator = MujocoSimulator(_headless=self.headless, _step_size=self.step_size, file_path=self.file_path)
        constraints = SimulatorConstraints(max_real_time=10.0)
        simulator.start(
            constraints=constraints, simulate_in_thread=True, render_in_thread=False
        )
        while simulator.state != SimulatorState.STOPPED:
            time.sleep(1)
        self.assertIs(simulator.state, SimulatorState.STOPPED)

    def test_running_in_10s_3(self):
        simulator = MujocoSimulator(_headless=self.headless, _step_size=self.step_size, file_path=self.file_path)
        constraints = SimulatorConstraints(max_real_time=10.0)
        simulator.start(
            constraints=constraints, simulate_in_thread=False, render_in_thread=True
        )
        while simulator.state != SimulatorState.STOPPED:
            simulator.step()
            time.sleep(0.001)
            if simulator.current_number_of_steps == 10000:
                simulator.stop()
        self.assertIs(simulator.state, SimulatorState.STOPPED)

    def test_running_in_10s_4(self):
        simulator = MujocoSimulator(_headless=self.headless, _step_size=self.step_size, file_path=self.file_path)
        constraints = SimulatorConstraints(max_real_time=10.0)
        simulator.start(
            constraints=constraints, simulate_in_thread=False, render_in_thread=False
        )
        while simulator.state != SimulatorState.STOPPED:
            simulator.step()
            simulator.render()
            time.sleep(0.001)
            if simulator.current_number_of_steps == 10000:
                simulator.stop()
        self.assertIs(simulator.state, SimulatorState.STOPPED)

    def test_running_2_simulators(self):
        simulator1 = MujocoSimulator(_headless=self.headless, _step_size=self.step_size, file_path=self.file_path)
        simulator1.start(simulate_in_thread=False, render_in_thread=True)
        self.headless = True
        simulator2 = MujocoSimulator(_headless=self.headless, _step_size=self.step_size, file_path=self.file_path)
        simulator2.start(simulate_in_thread=False)
        simulator3 = MujocoSimulator(_headless=self.headless, _step_size=self.step_size, file_path=self.file_path)
        simulator3.start(simulate_in_thread=False)
        for step in range(10000):
            simulator1.step()
            simulator2.step()
            simulator3.step()
        simulator1.stop()
        simulator2.stop()
        simulator3.stop()
        self.assertIs(simulator1.state, SimulatorState.STOPPED)
        self.assertIs(simulator2.state, SimulatorState.STOPPED)
        self.assertIs(simulator3.state, SimulatorState.STOPPED)


if __name__ == "__main__":
    unittest.main()
