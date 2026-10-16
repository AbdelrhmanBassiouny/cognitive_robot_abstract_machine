"""Time MuJoCo compiling a single RoboCasa object, and report its mesh sizes."""
import sys
import time

from semantic_digital_twin.adapters.robocasa_dataset.loader import RoboCasaDatasetLoader
import mujoco

sys.argv, category = sys.argv[:2], sys.argv[2]
exec(open("/root/scripts/render_counter_to_sink_helpers.py").read())

world = RoboCasaDatasetLoader().load_object(category)
for body in world.bodies:
    for kind, shapes in (("visual", body.visual.shapes), ("collision", body.collision.shapes)):
        for shape in shapes:
            mesh = shape.mesh
            print(category, body.name.name, kind, type(shape).__name__, "faces", len(mesh.faces), flush=True)
start = time.time()
render(frozen_copy(world), {"object": (np.array([0.5, -0.5, 0.5]), np.array([0.0, 0.0, 0.0]), 50.0)}, Path(sys.argv[1]), category)
print(category, f"compiled and rendered in {time.time() - start:.0f}s", flush=True)
