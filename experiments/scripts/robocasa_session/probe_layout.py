"""Print the kitchen counter surface, room bounds and wall/floor bodies to place the robot and camera."""
from experiments.robocasa_kitchen_demo import _counter_top_surface, _largest_counter_top, load_kitchen
from robocasa.models.scenes.scene_registry import LayoutType, StyleType
from semantic_digital_twin.spatial_computations.raytracer import RayTracer

world = load_kitchen(LayoutType.LAYOUT001, StyleType.STYLE001)
print("counter", _counter_top_surface(world, _largest_counter_top(world)))
print("scene bounds", RayTracer(world).scene.bounds.round(2).tolist())
for body in world.bodies:
    name = body.name.name
    if any(word in name for word in ("wall", "floor", "counter")) and body.collision and body.collision.shapes:
        box = body.collision.as_bounding_box_collection_in_frame(world.root).bounding_box()
        print(name, [round(v, 2) for v in (box.min_x, box.max_x, box.min_y, box.max_y, box.min_z, box.max_z)])
