"""Render the volumetric graph of convex sets of the RoboCasa sink and its surroundings with the
existing GCS volume figure.

Usage: render_gcs_sink.py <output directory>  (env BLOAT=metres)
"""
import os
import sys
from pathlib import Path

import numpy as np

from experiments.robocasa_task_execution.counter_to_sink import CounterToSinkEpisode
from robocasa.models.scenes.scene_registry import LayoutType, StyleType
from semantic_digital_twin.semantic_annotations.semantic_annotations import SemanticEnvironmentAnnotation
from semantic_digital_twin.spatial_types import HomogeneousTransformationMatrix, Point3
from semantic_digital_twin.world_description.geometry import VolumetricBoundingBox
from semantic_digital_twin.world_description.graph_of_convex_sets.boxes import VolumetricGraphOfBoundingBoxes
from semantic_digital_twin.world_description.graph_of_convex_sets.plotting import NavigationPath, NavigationScene, Theme
from semantic_digital_twin.world_description.graph_of_convex_sets.volume_figure import (
    GraphOfConvexSetsVolumeFigure,
    SceneCamera,
)
from semantic_digital_twin.world_description.shape_collection import BoundingBoxCollection

output_directory = Path(sys.argv[1])
bloat = float(os.environ.get("BLOAT", "0.05"))

episode = CounterToSinkEpisode.compose(LayoutType.LAYOUT001, StyleType.STYLE001)
world = episode.task.world
floor_corner, x_corner, y_corner, rim_corner = next(iter(episode.environment.sink.get_int_sites(relative=False).values()))
basin_center = (x_corner + y_corner) / 2
floor_z, rim_z = floor_corner[2], rim_corner[2]
front_y = floor_corner[1]

margin = 0.6
search_space = BoundingBoxCollection(
    shapes=[
        VolumetricBoundingBox(
            min_x=basin_center[0] - margin, max_x=basin_center[0] + margin,
            min_y=front_y - 0.4, max_y=basin_center[1] + 0.45,
            min_z=floor_z - 0.15, max_z=rim_z + 0.5,
            origin=HomogeneousTransformationMatrix(reference_frame=world.root),
        )
    ],
    reference_frame=world.root,
)
graph = VolumetricGraphOfBoundingBoxes.free_space_from_world(world, search_space, bloat_obstacles=bloat)
obstacles = SemanticEnvironmentAnnotation(root=world.root, _world=world).build_bloated_obstacle_collection(
    search_space, obstacle_height_clearance=0.0
)
start = Point3(basin_center[0], front_y - 0.25, rim_z + 0.05, reference_frame=world.root)
goal = Point3(basin_center[0], basin_center[1], floor_z + 0.1, reference_frame=world.root)
waypoints = graph.path_from_to(start, goal)
print(f"{len(graph.graph.nodes())} convex sets, {len(graph.graph.edges())} adjacencies, {len(list(obstacles))} obstacle boxes")
print("path", [np.round(p.to_np()[:3], 3).tolist() for p in waypoints])

scene = NavigationScene(
    graph_of_convex_sets=graph,
    environment_name="robocasa_sink",
    path=NavigationPath(waypoints),
    obstacles=obstacles,
)
for name, eye in {"front": Point3(0.9, -1.6, 1.1), "above": Point3(0.3, -0.6, 2.0)}.items():
    figure = GraphOfConvexSetsVolumeFigure(scene, theme=Theme.LIGHT, camera=SceneCamera(eye=eye), image_formats=(".png",))
    for path in figure.save(output_directory / name):
        print("wrote", path)
