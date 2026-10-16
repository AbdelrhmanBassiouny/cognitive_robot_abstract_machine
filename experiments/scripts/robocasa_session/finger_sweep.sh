cd /root/scripts; source /opt/ros/cram-env/bin/activate; source /opt/ros/overlay_ws/install/setup.bash
for c in "20 3 0.05" "50 5 0.05" "20 2 0.1"; do MUJOCO_GL=egl timeout 300 python probe_finger.py $c 2>&1 | grep "^\[" | sed -n "4p;7p;10p"; done
