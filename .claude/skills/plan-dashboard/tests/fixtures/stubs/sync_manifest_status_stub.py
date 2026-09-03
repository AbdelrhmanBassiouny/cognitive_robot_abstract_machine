#!/usr/bin/env python3
"""
Stand-in for sync_manifest_status.py used by test_refresh_dashboard_sh.py: records its
own invocation arguments to a file (so the test can inspect what refresh_dashboard.sh
passed it) and echoes back whatever the test wrote into --pr-data's file as the
"corrected" list, instead of reading a real plan.yaml and computing a correction from
live pull request state.
"""

import argparse
import json
import sys
from pathlib import Path

Path("sync_manifest_status_invocation.json").write_text(json.dumps(sys.argv[1:]))

parser = argparse.ArgumentParser()
parser.add_argument("--plan")
parser.add_argument("--pr-data")
parser.add_argument("--plans-dir")
arguments = parser.parse_args()

with open(arguments.pr_data) as pull_request_data_file:
    corrected = json.load(pull_request_data_file)

print(json.dumps({"corrected": corrected}))
