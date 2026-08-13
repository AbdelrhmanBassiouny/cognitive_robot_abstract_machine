"""
Demo that does the following:

- load the kitchen_smal using smedt.
- Spawn a milk in the fridge
- Query the handle of the container where the milk is
- Spawn a PR2 and navigate it to a pose in front of the handle of the container that has
  the milk
- Create a neem of it.
- Query the neem using EQL to SQL
"""

import logging
import os

from importlib.resources import files
from pathlib import Path

from semantic_digital_twin.adapters.urdf import URDFParser

logging.disable(logging.CRITICAL)
world_path = os.path.join(
    Path(files("coraplex")).parent.parent, "resources", "worlds", "kitchen-small.urdf"
)
world = URDFParser.from_file(world_path).parse()


from semantic_digital_twin.adapters.ros.tf_publisher import TFPublisher
from semantic_digital_twin.adapters.ros.visualization.viz_marker import (
    VizMarkerPublisher,
)
import threading
import rclpy

rclpy.init()

node = rclpy.create_node("semantic_digital_twin")
thread = threading.Thread(target=rclpy.spin, args=(node,), daemon=True)
thread.start()

tf_publisher = TFPublisher(_world=world, node=node)
viz = VizMarkerPublisher(_world=world, node=node)

# %% infer semantic annotations (fridge, door, handle, ...) from the raw URDF bodies

from semantic_digital_twin.reasoning.world_reasoner import WorldReasoner

WorldReasoner(world).reason()

# %% spawn the milk in the fridge

from semantic_digital_twin.adapters.mesh import STLParser
from semantic_digital_twin.semantic_annotations.semantic_annotations import Fridge, Milk
from semantic_digital_twin.spatial_types.spatial_types import (
    HomogeneousTransformationMatrix,
)

MILK_MARGIN = 0.02
"""
Clearance kept between the milk and the fridge's floor and front so it does not clip
through the fridge's own geometry.
"""

fridge = world.get_semantic_annotations_by_type(Fridge)[0]
fridge_box = fridge.root.collision.as_bounding_box_collection_in_frame(
    fridge.root
).bounding_box()

milk_path = os.path.join(
    Path(files("coraplex")).parent.parent, "resources", "objects", "milk.stl"
)
milk_world = STLParser(milk_path).parse()
milk_body = milk_world.bodies_with_collision[0]
milk_bottom_offset = (
    -milk_body.collision.as_bounding_box_collection_in_frame(milk_world.root)
    .bounding_box()
    .min_z
)

# The fridge opens towards its local negative x-axis (`Cabinet.hole_direction`), so the
# fridge's front, where the door sits, is at `fridge_box.min_x`.
fridge_T_milk = HomogeneousTransformationMatrix.from_xyz_rpy(
    x=fridge_box.min_x + MILK_MARGIN,
    y=(fridge_box.min_y + fridge_box.max_y) / 2,
    z=fridge_box.min_z + MILK_MARGIN + milk_bottom_offset,
    reference_frame=fridge.root,
)
world.merge_world_at_pose(milk_world, fridge.root.global_transform @ fridge_T_milk)

milk_body = world.get_body_by_name("milk.stl")
with world.modify_world():
    world.add_semantic_annotation(Milk(root=milk_body))

# %% query the handle of the container the milk is in

from semantic_digital_twin.reasoning.predicates import InsideOf

CONTAINMENT_THRESHOLD = 0.5
"""
Minimum fraction of the milk's volume that must lie within a candidate container's
bounding box for that container to count as holding the milk.
"""

container = next(
    candidate
    for candidate in world.get_semantic_annotations_by_type(Fridge)
    if InsideOf(milk_body, candidate.root).compute_containment_ratio()
    > CONTAINMENT_THRESHOLD
)
handle = container.doors[0].handle

# %% spawn a PR2 and navigate it to a pose in front of the handle

from coraplex.datastructures.dataclasses import Context
from coraplex.datastructures.enums import Arms
from coraplex.execution_environment import simulated_robot
from coraplex.locations.factories import occupancy_location
from coraplex.plans.factories import sequential
from coraplex.robot_plans.actions.core.navigation import NavigateAction
from coraplex.robot_plans.actions.core.robot_body import ParkArmsAction
from semantic_digital_twin.robots.pr2 import PR2
from semantic_digital_twin.world_description.connections import OmniDrive

pr2_world = URDFParser.from_file(
    "package://iai_pr2_description/robots/pr2_with_ft2_cableguide.xacro"
).parse()
with world.modify_world():
    drive = OmniDrive.create_with_dofs(
        parent=world.root, child=pr2_world.root, world=world
    )
    world.merge_world(pr2_world, drive)

pr2 = PR2.from_world(world)
context = Context(world=world, robot=pr2, ros_node=node)
context.evaluate_conditions = False

with simulated_robot:
    # Park the arms first: their default outstretched posture collides with the kitchen
    # furniture around the fridge, which would make every candidate base pose invalid.
    sequential([ParkArmsAction(Arms.BOTH)], context=context).plan.perform()

    location = occupancy_location(handle.root.global_pose, context)
    target_pose = next(iter(location))
    sequential(
        [NavigateAction(target_location=target_pose)], context=context
    ).plan.perform()

# %% create a neem of the demo run

# TODO: this repository has no NEEM (Narrative-Enabled Episodic Memory) export yet -
# there is no neem/knowrob dependency and no episodic-memory logging API anywhere in the
# codebase. Wire this step up once the target NEEM tool/package has been decided on.
