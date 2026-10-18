#!/bin/bash
# Locate every object's parts one at a time, and split each located object as soon as it is located.
# usage: run.sh <parallel splits> <seconds per split> [objects...]
source /opt/ros/cram-env/bin/activate; source /opt/ros/overlay_ws/install/setup.bash
export MUJOCO_GL=egl OMP_NUM_THREADS=4
cd /root/work/part_decomposition/code
mkdir -p ../logs ../results ../located
python locate.py "${@:3}" >> ../logs/locate.log 2>&1 &
locate=$!
while true; do
  running=$(kill -0 $locate 2>/dev/null && echo 1 || echo 0)
  for f in ../located/*.json; do
    case "$f" in *.error.json) continue;; esac
    key=$(basename "$f" .json)
    [ -f "../results/$key.json" ] || [ -f "../logs/$key.started" ] || { touch "../logs/$key.started"; echo "$key"; }
  done
  [ "$running" = 0 ] && break
  sleep 20
done | xargs -P "${1:-8}" -I{} bash run_one.sh {} "${2:-900}"
wait
echo RUN FINISHED
