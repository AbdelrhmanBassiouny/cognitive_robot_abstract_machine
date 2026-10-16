cd /root/scripts
source /opt/ros/cram-env/bin/activate
source /opt/ros/overlay_ws/install/setup.bash
MUJOCO_GL=egl timeout 300 python sweep_gains.py '{"upper":{"torque_limit":100,"stiffness":2000,"damping":200,"armature":0.5},"wrist":{"torque_limit":30,"stiffness":500,"damping":30,"armature":0.1},"pan":{"torque_limit":20,"stiffness":200,"damping":30,"armature":0.5},"tilt":{"torque_limit":40,"stiffness":400,"damping":40,"armature":0.5}}' > /tmp/sweep_one.txt 2>&1
grep -v Warning /tmp/sweep_one.txt | grep -v INFO | grep -v Unknown | tail -12
