cd /root/scripts
source /opt/ros/cram-env/bin/activate
source /opt/ros/overlay_ws/install/setup.bash
run() { MUJOCO_GL=egl timeout 300 python sweep_gains.py "$2" 2>&1 | grep -E "^(t=|max speed|Traceback|[A-Za-z]*Error)" | sed "s/^/$1 /"; }
run A_current '{"upper":{"torque_limit":30,"stiffness":1000,"damping":60,"armature":0.1},"wrist":{"torque_limit":10,"stiffness":300,"damping":10,"armature":0.05},"pan":{"torque_limit":2.645,"stiffness":100,"damping":6,"armature":0.05},"tilt":{"torque_limit":18,"stiffness":300,"damping":15,"armature":0.05}}' > /tmp/sweep_A.txt &
run B_armature '{"upper":{"torque_limit":30,"stiffness":1000,"damping":100,"armature":0.5},"wrist":{"torque_limit":10,"stiffness":300,"damping":20,"armature":0.1},"pan":{"torque_limit":2.645,"stiffness":100,"damping":10,"armature":0.5},"tilt":{"torque_limit":18,"stiffness":300,"damping":30,"armature":0.5}}' > /tmp/sweep_B.txt &
run C_more_torque '{"upper":{"torque_limit":100,"stiffness":2000,"damping":200,"armature":0.5},"wrist":{"torque_limit":30,"stiffness":500,"damping":30,"armature":0.1},"pan":{"torque_limit":20,"stiffness":200,"damping":30,"armature":0.5},"tilt":{"torque_limit":40,"stiffness":400,"damping":40,"armature":0.5}}' > /tmp/sweep_C.txt &
run D_stiff '{"upper":{"torque_limit":200,"stiffness":5000,"damping":500,"armature":1.0},"wrist":{"torque_limit":50,"stiffness":1000,"damping":50,"armature":0.2},"pan":{"torque_limit":50,"stiffness":1000,"damping":100,"armature":1.0},"tilt":{"torque_limit":50,"stiffness":1000,"damping":100,"armature":1.0}}' > /tmp/sweep_D.txt &
wait
cat /tmp/sweep_?.txt
