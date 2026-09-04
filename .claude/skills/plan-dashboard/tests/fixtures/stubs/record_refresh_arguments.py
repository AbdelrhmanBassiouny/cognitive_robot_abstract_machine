#!/usr/bin/env python3
"""
Record what one plan's refresh was handed, and write the page it was asked for.

Driven by ``refresh_dashboard_stub.sh``, which build_site.py's tests put in
``refresh_dashboard.sh``'s place: the assertions read ``arguments.json`` beside the
written page to see what the site build passed down.

The options are ``build_site.py``'s own :class:`RefreshArgument`, so a flag renamed
there fails here rather than being silently ignored.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

STUBS_DIRECTORY = Path(__file__).resolve().parent
TESTS_DIRECTORY = STUBS_DIRECTORY.parent.parent
sys.path.insert(0, str(TESTS_DIRECTORY.parent))
sys.path.insert(0, str(TESTS_DIRECTORY))

from build_dashboard import ItemStatus  # noqa: E402
from build_site import RefreshArgument, RefreshSummaryKey  # noqa: E402
from script_arguments import ScriptArgumentParser  # noqa: E402
from site_fixtures import (  # noqa: E402
    RECORDED_ARGUMENTS_FILENAME,
    RecordedArgumentKey,
)

CORRECTED_KEY = "corrected"
"""
The manifest corrections ``sync_manifest_status.py`` reports, which this stub makes none
of.
"""

SUMMARY = {
    CORRECTED_KEY: [],
    RefreshSummaryKey.COUNTS.value: {
        ItemStatus.DONE.value: 1,
        ItemStatus.IN_PROGRESS.value: 1,
    },
}
"""
The summary shape refresh_dashboard.sh prints: its own correction list merged with
build_dashboard.py's per-status counts.
"""


def main() -> None:
    """
    Write the page and the record of what produced it.
    """
    parser = ScriptArgumentParser(__doc__)
    for option in RefreshArgument:
        parser.add(option, f"Recorded as {option}", default="")
    arguments = parser.parse()

    output_page = Path(arguments.output)
    output_page.write_text(f"<html><body>{arguments.plan_id}</body></html>\n")
    (output_page.parent / RECORDED_ARGUMENTS_FILENAME).write_text(
        json.dumps(
            {
                RefreshArgument.PLAN_ID.value: arguments.plan_id,
                RefreshArgument.TRACKING_URL.value: arguments.tracking_url,
                RecordedArgumentKey.PLAN.value: Path(arguments.plan).read_text(),
                RecordedArgumentKey.ROADMAP.value: Path(arguments.roadmap).read_text(),
                RecordedArgumentKey.PULL_REQUEST_DATA.value: Path(
                    arguments.pr_data
                ).read_text(),
            }
        )
    )
    print(json.dumps(SUMMARY))


if __name__ == "__main__":
    main()
