#!/bin/bash
# Stage 2 driver: run every (object, setting) pair that has no result yet, in parallel.
# usage: sweep.sh <parallel jobs> <seconds per run>
source /opt/ros/cram-env/bin/activate; source /opt/ros/overlay_ws/install/setup.bash
export MUJOCO_GL=egl OMP_NUM_THREADS=4
cd /root/work/part_split_benchmark/code
mkdir -p ../logs ../results
python -c "from common import objects, CONFIGS; [print(o, c) for o in objects() for c in ['original', *CONFIGS]]" 2>/dev/null \
  | while read o c; do [ -f "../results/$o/$c.json" ] || echo "$o $c"; done \
  | xargs -P "${1:-24}" -n 2 sh -c 'bash run_one.sh "$0" "$1" '"${2:-900}"
echo SWEEP FINISHED
