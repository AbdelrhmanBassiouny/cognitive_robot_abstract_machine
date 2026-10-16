source /opt/ros/cram-env/bin/activate
source /opt/ros/overlay_ws/install/setup.bash
W=/opt/cram/.pr_worktree
for d in $W/*/src; do export PYTHONPATH=$d:$PYTHONPATH; done
cd /opt/cram/.pr_worktree
export MUJOCO_GL=egl
ulimit -v 120000000
export PYTHONPATH=$W:$PYTHONPATH
