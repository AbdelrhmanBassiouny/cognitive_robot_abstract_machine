#!/usr/bin/env python3
"""
Record what one plan's refresh was handed, and write the page it was asked for.

Driven by ``refresh_dashboard_stub.sh``, which build_site.py's tests put in
``refresh_dashboard.sh``'s place: the assertions read ``arguments.json`` beside the
written page to see what the site build passed down.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

ARGUMENTS_FILENAME = "arguments.json"
"""
The record written beside the page, holding what this run was handed.
"""

SUMMARY = {"corrected": [], "counts": {"done": 1, "in_progress": 1}}
"""
The summary shape refresh_dashboard.sh prints: its own correction list merged with
build_dashboard.py's per-status counts.
"""


def main() -> None:
    """
    Write the page and the record of what produced it.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan-id", required=True)
    parser.add_argument("--plan", required=True)
    parser.add_argument("--roadmap", required=True)
    parser.add_argument("--pr-data", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--tracking-url", default="")
    arguments = parser.parse_args()

    output_page = Path(arguments.output)
    output_page.write_text(f"<html><body>{arguments.plan_id}</body></html>\n")
    (output_page.parent / ARGUMENTS_FILENAME).write_text(
        json.dumps(
            {
                "--plan-id": arguments.plan_id,
                "--tracking-url": arguments.tracking_url,
                "plan": Path(arguments.plan).read_text(),
                "roadmap": Path(arguments.roadmap).read_text(),
                "pr-data": Path(arguments.pr_data).read_text(),
            }
        )
    )
    print(json.dumps(SUMMARY))


if __name__ == "__main__":
    main()
