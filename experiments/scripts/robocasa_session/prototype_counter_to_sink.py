"""Prototype: the PR2 performs RoboCasa's PickPlaceCounterToSink with an underspecified coraplex transport."""
import logging
import time

from semantic_digital_twin.adapters.robocasa_dataset.loader import RoboCasaDatasetLoader
from robocasa.models.scenes.scene_registry import LayoutType, StyleType

import numpy as np
from coraplex.datastructures.dataclasses import Context
from coraplex.execution_environment import kinematically_simulated_robot
from coraplex.plans.factories import sequential
from coraplex.robot_plans.actions.composite.transporting import TransportAction
from coraplex.robot_plans.actions.core.robot_body import MoveTorsoAction, ParkArmsAction
from semantic_digital_twin.adapters.urdf import URDFParser
from semantic_digital_twin.datastructures.definitions import TorsoState
from semantic_digital_twin.robots.pr2 import PR2
from semantic_digital_twin.semantic_annotations.semantic_annotations import Sink
from semantic_digital_twin.spatial_types.spatial_types import Point3, Pose
from semantic_digital_twin.world_description.connections import OmniDrive

logging.basicConfig(level=logging.INFO)

import collections
import coraplex.plans.underspecified as underspecified_module
from coraplex.language import SequentialNode
from coraplex.plans.failures import PlanFailure

failure_counts = collections.Counter()


class LoggingTrialSequence(SequentialNode):
    """Logs why a trial candidate failed, then re-raises."""

    def perform(self):
        try:
            return super().perform()
        except PlanFailure as failure:
            action = self.children[0].designator
            navigate = getattr(action, "navigate", None)
            stand = navigate.target_location.to_np()[:3, 3].round(2).tolist() if navigate is not None else None
            failure_counts[(type(action).__name__, type(failure).__name__)] += 1
            if sum(failure_counts.values()) <= 12:
                print("TRIAL FAILED", type(action).__name__, "stand", stand, type(failure).__name__, str(failure)[:300].replace("\n", " | "))
            raise


underspecified_module.SequentialNode = LoggingTrialSequence
logging.getLogger("semantic_digital_twin").setLevel(logging.WARNING)

start = time.time()
import robosuite

loader = RoboCasaDatasetLoader()
environment = robosuite.make(
    env_name="PickPlaceCounterToSink",
    robots=loader.scene_composition_robot,
    layout_ids=int(LayoutType.LAYOUT001),
    style_ids=int(StyleType.STYLE001),
    has_renderer=False,
    has_offscreen_renderer=False,
    use_camera_obs=False,
    control_freq=20,
    ignore_done=True,
    seed=0,
)
environment.reset()
task = loader.load_task_from_environment(environment)
world = task.world
print("instruction:", task.instruction, f"({time.time() - start:.0f}s)")

from semantic_digital_twin.semantic_annotations.semantic_annotations import Floor
with world.modify_world():
    world.add_semantic_annotation(Floor(root=world.get_body_by_name("floor_room_main")))

pr2_world = URDFParser.from_file(PR2.get_ros_file_path()).parse()
with world.modify_world():
    drive = OmniDrive.create_with_dofs(parent=world.root, child=pr2_world.root, world=world)
    world.merge_world(pr2_world, drive)
    drive.has_hardware_interface = True
drive.origin = task.robot_base_pose
pr2 = PR2.from_world(world)

from semantic_digital_twin.grasping.grasp_candidates import HasGraspCandidates
cup = next(a for a in world.semantic_annotations if a.root == task.manipulated_objects[0] and isinstance(a, HasGraspCandidates))
print("target object", type(cup).__name__, cup.root.name.name)
sink = world.get_semantic_annotations_by_type(Sink)[0]
sink_box = sink.root.collision.as_bounding_box_collection_in_frame(world.root).bounding_box()
cup_position = cup.root.global_pose.to_np()[:3, 3]
print("cup at", cup_position.round(3), "sink box", [round(float(v), 3) for v in (sink_box.min_x, sink_box.max_x, sink_box.min_y, sink_box.max_y, sink_box.min_z, sink_box.max_z)])

target = Pose(
    position=Point3((sink_box.min_x + sink_box.max_x) / 2, (sink_box.min_y + sink_box.max_y) / 2, 0.78),
    orientation=cup.root.global_pose.quaternion,
    reference_frame=world.root,
)

context = Context(world, pr2, sampling_seed=42)
transport = TransportAction.from_graspable_by_closest_grasps(cup, target, pr2.right_arm, context)
plan = sequential([MoveTorsoAction(TorsoState.HIGH), ParkArmsAction(pr2.all_arms), transport], context)

start = time.time()
try:
    with kinematically_simulated_robot:
        plan.perform()
finally:
    print("failure counts", dict(failure_counts))
print(f"performed in {time.time() - start:.0f}s")

final = cup.root.global_pose.to_np()[:3, 3]
inside = sink_box.min_x <= final[0] <= sink_box.max_x and sink_box.min_y <= final[1] <= sink_box.max_y and final[2] < sink_box.max_z
print("cup now at", final.round(3), "distance to target", round(float(np.linalg.norm(final - target.to_np()[:3, 3])), 3), "inside sink box:", inside)
print("robot base at", drive.origin.to_np()[:3, 3].round(3))
