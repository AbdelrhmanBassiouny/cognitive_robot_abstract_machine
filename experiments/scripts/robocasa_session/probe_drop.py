import sys, time
import numpy as np
from experiments.robocasa_task_execution.counter_to_sink import CounterToSinkEpisode, RoboCasaObjectName
from robocasa.models.scenes.scene_registry import LayoutType, StyleType
from robocasa.utils import object_utils
from semantic_digital_twin.spatial_types.spatial_types import Point3, Pose

episode = CounterToSinkEpisode.compose(LayoutType[sys.argv[1]], StyleType.STYLE001)
env = episode.environment
sites = next(iter(env.sink.get_int_sites(relative=False).values()))
print("int sites", [np.round(s, 3) for s in sites])
pose = episode.placement_pose()
body = episode.target_object.root
print("placement z", pose.to_np()[2, 3])
m = pose.to_np()
body.parent_connection.origin = Pose(position=Point3(m[0, 3], m[1, 3], sites[3][2] + 0.10), orientation=pose.quaternion, reference_frame=episode.task.world.root).homogeneous_matrix
target = env.objects[RoboCasaObjectName.TARGET]
w = body.global_pose
x, y, z, q = w.quaternion.to_np()
env.sim.data.set_joint_qpos(target.joints[0], np.concatenate([w.to_np()[:3, 3], [q, x, y, z]]))
env.sim.data.set_joint_qvel(target.joints[0], np.zeros(6))
env.sim.forward()
print("inside before drop", object_utils.obj_inside_of(env, "obj", env.sink, partial_check=True))
print("timestep", env.sim.model.opt.timestep)
t = time.time()
for i in range(1000):
    env.sim.step()
print("stepped in", time.time() - t)
print("obj pos after", env.sim.data.get_joint_qpos(target.joints[0])[:3])
print("inside after drop", object_utils.obj_inside_of(env, "obj", env.sink, partial_check=True))
