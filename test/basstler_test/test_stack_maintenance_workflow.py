"""
The one thing about the stack-maintenance workflow worth asserting from code.

The pass reads ``board.json`` and deletes it once it concludes - see
``RunReportCommand.perform``'s own docstring - so a caller who invokes it without first
exporting a board fails with :class:`stack.BoardUnavailable` every time, never only on a
second run. That ordering lives in a YAML string a reviewer has to read carefully to
verify; this test reads it back the same way the shell would, so a future edit that
drops or reorders the export step fails here instead of in the next scheduled run.
"""

from __future__ import annotations

import yaml

from basstler.locations import PackageLocation
from basstler.maintenance_commands import BoardCommand, UnattendedRunCommand

STACK_MAINTENANCE_WORKFLOW = (
    PackageLocation.REPOSITORY_ROOT / ".github" / "workflows" / "stack-maintenance.yml"
)
"""
The workflow document that runs the maintenance pass unattended.
"""


def _maintenance_pass_run_script() -> str:
    """:return: The shell script of the step that runs the maintenance pass."""
    document = yaml.safe_load(STACK_MAINTENANCE_WORKFLOW.read_text())
    steps = document["jobs"]["maintain"]["steps"]
    step = next(
        step for step in steps if step.get("name") == "Run the maintenance pass"
    )
    return step["run"]


def test_the_board_is_exported_before_the_report_is_run():
    """
    ``run-report`` derives its stack from ``board.json`` and consumes it, so the export
    that produces that file has to run first in the same job.
    """
    script = _maintenance_pass_run_script()

    board_export = script.index(
        f'"${{MAINTENANCE_MODULE}}" {BoardCommand.invoked_as} --write'
    )
    unattended_run = script.index(
        f'"${{MAINTENANCE_MODULE}}" {UnattendedRunCommand.invoked_as}'
    )

    assert board_export < unattended_run
