"""
The live-only motion-statechart tab.
"""

from __future__ import annotations

from dataclasses import dataclass

from typing_extensions import Any, Dict


@dataclass
class ChartViewPayload:
    """
    The (live-only) statechart tab.

    Motion statecharts only exist while giskardpy executes them: one is compiled per
    merged motion group and thrown away afterwards, and nothing of it is recorded into
    the bundle — the UI fills this view from the bridge's ``/chart`` while attached.
    """

    ok: bool
    """
    Always ``True`` — this view has no failure mode.
    """

    @classmethod
    def live_only(cls) -> ChartViewPayload:
        """
        The statechart tab, which only ever has content while a demo is running.
        """
        return cls(True)

    def to_payload(self) -> Dict[str, Any]:
        """
        The JSON-serializable shape the frontend expects.
        """
        return {
            "ok": self.ok,
            "breadcrumb": "motion statechart",
            "nodes": [],
            "edges": [],
            "details": {},
            "layout": "hier",
            "live": "chart",
            "empty": "Motion statecharts are built and ticked at execution time. "
            "Start the demo with cramera-live and press ◉ Live — "
            "the statechart of the running motion group appears here, "
            "coloured by its node life cycle.",
        }
