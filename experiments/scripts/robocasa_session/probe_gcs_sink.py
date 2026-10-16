"""Does a volumetric graph of bounding boxes leave the inside of the RoboCasa sink free?"""
import time
from collections import Counter

import numpy as np

from experiments.robocasa_task_execution.counter_to_sink import CounterToSinkEpisode
from robocasa.models.scenes.scene_registry import LayoutType, StyleType
from semantic_digital_twin.spatial_types import HomogeneousTransformationMatrix, Point3
from semantic_digital_twin.world_description.geometry import VolumetricBoundingBox
from semantic_digital_twin.world_description.graph_of_convex_sets.boxes import VolumetricGraphOfBoundingBoxes
from semantic_digital_twin.world_description.shape_collection import BoundingBoxCollection

episode = CounterToSinkEpisode.compose(LayoutType.LAYOUT001, StyleType.STYLE001)
world = episode.task.world
sink = episode.environment.sink
for name, corners in sink.get_int_sites(relative=False).items():
    print("int site", name, [np.round(c, 3).tolist() for c in corners])
p0, px, py, pz = next(iter(sink.get_int_sites(relative=False).values()))
basin_center = (px + py) / 2
print("basin centre", np.round(basin_center, 3), "floor z", p0[2], "rim z", pz[2])

sink_bodies = [b for b in world.bodies if b.name.name.startswith(sink.name) and b.collision.shapes]
for b in sink_bodies:
    print(b.name.name, Counter(type(s).__name__ for s in b.collision.shapes))
    for box in b.collision.as_bounding_box_collection_in_frame(world.root):
        print("   box", np.round([box.min_x, box.min_y, box.min_z, box.max_x, box.max_y, box.max_z], 3).tolist())

margin = 0.35
search_space = BoundingBoxCollection(
    shapes=[
        VolumetricBoundingBox(
            min_x=basin_center[0] - margin, max_x=basin_center[0] + margin,
            min_y=basin_center[1] - margin, max_y=basin_center[1] + margin,
            min_z=p0[2] - 0.05, max_z=pz[2] + 0.6,
            origin=HomogeneousTransformationMatrix(reference_frame=world.root),
        )
    ],
    reference_frame=world.root,
)
for bloat in (0.0, 0.02, 0.05):
    start = time.time()
    graph = VolumetricGraphOfBoundingBoxes.free_space_from_world(world, search_space, bloat_obstacles=bloat)
    print(f"bloat {bloat}: {len(graph.graph.nodes())} boxes, {len(graph.graph.edges())} edges in {time.time()-start:.1f}s")
    above = Point3(basin_center[0], basin_center[1], pz[2] + 0.3, reference_frame=world.root)
    inside = Point3(basin_center[0], basin_center[1], p0[2] + 0.08, reference_frame=world.root)
    for label, point in (("above", above), ("inside", inside)):
        node = graph._node_of_point(point)
        print("  ", label, np.round(point.to_np()[:3], 3).tolist(), "free" if node is not None else "occupied")
    if graph._node_of_point(above) is not None and graph._node_of_point(inside) is not None:
        path = graph.path_from_to(above, inside)
        print("   path", None if path is None else [np.round(p.to_np()[:3], 3).tolist() for p in path])
