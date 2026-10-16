#!/bin/bash
source /opt/ros/cram-env/bin/activate
source /opt/ros/overlay_ws/install/setup.bash
export MUJOCO_GL=egl COLLISION_AVOIDANCE=1 MIN_STAND=0.525 GRIPPER_BUFFER=0.02 BLOAT=0.08 VERTICAL_BLOAT=0.08
cd /root/scripts
ulimit -v 80000000
: > /root/work/gcs/sweep_torso_pitch2.log
for torso in HIGH MID LOW; do
  for pitch in 90 60; do
    TORSO=$torso PITCH_DEGREES=$pitch MIN_STAND=0.40 timeout 300 python probe_gcs_reach.py /root/work/gcs 2>&1 \
      | grep -vE "CONTACT base" | grep -E "^ca1|base drifted|PR2 stands|GCS path|NO PATH|motion |tool frame at|inside the basin|INSIDE|Error" >> /root/work/gcs/sweep_torso_pitch2.log
    echo "--- done $torso $pitch" >> /root/work/gcs/sweep_torso_pitch2.log
  done
done
echo FINISHED >> /root/work/gcs/sweep_torso_pitch2.log
