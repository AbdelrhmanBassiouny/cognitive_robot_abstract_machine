#!/bin/bash
# Stands in for a refresh_dashboard.sh run that failed - a manifest that no longer
# validates - so build_site.py's handling of it can be tested.
echo "plan.yaml failed validation" >&2
exit 1
