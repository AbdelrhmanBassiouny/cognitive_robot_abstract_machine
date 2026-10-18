#!/bin/bash
# usage: run_one.sh <object> <seconds>
cd /root/work/part_decomposition/code
ulimit -v 32000000
timeout "$2" python decompose.py "$1" > "../logs/$1.log" 2>&1
rc=$?
if [ ! -f "../results/$1.json" ]; then
  if [ $rc -eq 124 ]; then status="timeout after $2 s"; else status="crashed (exit $rc)"; fi
  echo "{\"object\": \"$1\", \"status\": \"$status\"}" > "../results/$1.json"
fi
echo "done $1 rc=$rc"
