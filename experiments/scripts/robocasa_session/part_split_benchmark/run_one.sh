#!/bin/bash
# Run one (object, setting) pair, capped in memory and time; record a timeout or crash if split.py could not.
# usage: run_one.sh <object> <config> <seconds>
cd /root/work/part_split_benchmark/code
ulimit -v 32000000
timeout "$3" python split.py "$1" "$2" > "../logs/$1.$2.log" 2>&1
rc=$?
if [ ! -f "../results/$1/$2.json" ]; then
  mkdir -p "../results/$1"
  if [ $rc -eq 124 ]; then status="timeout after $3 s"; else status="crashed (exit $rc)"; fi
  echo "{\"object\": \"$1\", \"config\": \"$2\", \"status\": \"$status\"}" > "../results/$1/$2.json"
fi
echo "done $1 $2 rc=$rc"
