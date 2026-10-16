cd /root/scripts
source /opt/ros/cram-env/bin/activate
source /opt/ros/overlay_ws/install/setup.bash
run() { MUJOCO_GL=egl timeout 300 python sweep_gains.py "$2" 2>&1 | grep -E "^(t=|max speed|Traceback|[A-Za-z]*Error)" | sed "s/^/$1 /" | cut -c1-260; }
run E_urdf_limits '{"upper":{"torque_limit":30,"stiffness":1000,"damping":100,"armature":1.0},"wrist":{"torque_limit":10,"stiffness":300,"damping":30,"armature":0.3},"pan":{"torque_limit":2.645,"stiffness":100,"damping":20,"armature":1.0},"tilt":{"torque_limit":18,"stiffness":300,"damping":40,"armature":1.0}}'
run F_tuned '{"upper":{"torque_limit":100,"stiffness":2000,"damping":200,"armature":0.5},"wrist":{"torque_limit":30,"stiffness":500,"damping":30,"armature":0.1},"pan":{"torque_limit":20,"stiffness":200,"damping":60,"armature":0.5},"tilt":{"torque_limit":40,"stiffness":400,"damping":40,"armature":0.5}}'
