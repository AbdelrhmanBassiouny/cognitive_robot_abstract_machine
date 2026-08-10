"""
The live-only motion-statechart tab.
"""

from __future__ import annotations

from dataclasses import dataclass

from typing_extensions import Any, Dict

from cramera.knowledge.subgraph import GraphPanelPayload


@dataclass(kw_only=True)
class ChartViewPayload(GraphPanelPayload):
    """
    The (live-only) statechart tab.

    Motion statecharts only exist while giskardpy executes them: one is compiled per
    merged motion group and thrown away afterwards, and nothing of it is recorded into
    the bundle — the UI fills this view from the bridge's ``/chart`` while attached.
    """

    breadcrumb: str = "motion statechart"
    """
    Breadcrumb label shown above the (initially empty) chart.
    """

    empty_message: str = (
        "Motion statecharts are built and ticked at execution time. "
        "Start the demo with cramera-live and press ◉ Live — "
        "the statechart of the running motion group appears here, "
        "coloured by its node life cycle."
    )
    """
    What the panel shows until a live bridge is attached.
    """

    @classmethod
    def live_only(cls) -> ChartViewPayload:
        """
        The statechart tab, which only ever has content while a demo is running.
        """
        return cls()

    def panel_options(self) -> Dict[str, Any]:
        """
        The breadcrumb and the live/layout flags the statechart tab is rendered with.
        """
        return {
            "breadcrumb": self.breadcrumb,
            "layout": "hier",
            "live": "chart",
            "empty": self.empty_message,
        }
