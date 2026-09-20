"""
The framework figure, drawn as far as the plan has been answered.

The paper's figure is one typst source; the video compiles that same source with an
input that says how many backends have answered, which open slot is being answered right
now, and what the run actually read, so what the video builds up is the figure the paper
prints, drawn from the same file.
"""

from __future__ import annotations

import io
import json
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path

import numpy as np
import typst
from PIL import Image
from typing_extensions import Dict, List, Optional

import experiments
from experiments.video.timeline import Frame

FIGURE_SOURCE = (
    Path(experiments.__file__).parents[2]
    / "doc"
    / "figures"
    / "framework"
    / "framework.typ"
)
"""
The paper's figure, which the video compiles with its own input.
"""

VIDEO_INPUT = "video"
"""
The name of the typst input the figure reads the video's wishes from.
"""

FIGURE_WIDTH_CENTIMETRES = 18.0
"""
The width the figure's source lays itself out at.
"""

CENTIMETRES_PER_INCH = 2.54


class Slot(StrEnum):
    """
    The plan's open slots, by the backend that answers each, in the order the choice
    asks them.
    """

    PERCEPTION = "perception"
    SIMULATION = "simulation"
    PROBABILISTIC = "probabilistic"
    RULES = "rules"

    @property
    def stage(self) -> int:
        """
        How many backends have answered once this slot's has.
        """
        return list(Slot).index(self) + 1


class PlanAction(StrEnum):
    """
    The two actions the plan sequences, in their order.
    """

    PICK_UP = "pick_up"
    INSERTION = "insertion"


@dataclass(frozen=True)
class GraspChartBar:
    """
    One bar of the figure's grasp chart.
    """

    approach: str
    """
    The approach direction, as the enumeration names it.
    """

    alignment: str
    """
    The vertical alignment, as the enumeration names it.
    """

    p: float
    """
    The height of the bar.
    """

    chosen: bool = False
    """
    Whether this is the grasp the plan was answered with.
    """


@dataclass(frozen=True)
class RunReadings:
    """
    What a run actually read, in place of the values the figure's source states.
    """

    resolved_lines: Dict[Slot, List[str]] = field(default_factory=dict)
    """
    The lines each answered slot of the resolved plan shows.
    """

    grasps: List[GraspChartBar] = field(default_factory=list)
    """
    The grasp chart's bars, or none to keep the source's.
    """

    support_reading: Optional[str] = None
    """
    What the working-memory panel reads off the two boxes.
    """

    support_verdict: Optional[str] = None
    """
    What the working-memory panel concludes.
    """

    def as_input(self) -> Dict[str, object]:
        """
        The readings as the figure's input carries them.
        """
        given: Dict[str, object] = {}
        if self.resolved_lines:
            given["resolved_lines"] = {
                slot.value: lines for slot, lines in self.resolved_lines.items()
            }
        if self.grasps:
            given["grasps"] = [
                {
                    "approach": bar.approach,
                    "alignment": bar.alignment,
                    "p": bar.p,
                    "chosen": bar.chosen,
                }
                for bar in self.grasps
            ]
        if self.support_reading is not None:
            given["support_reading"] = self.support_reading
        if self.support_verdict is not None:
            given["support_verdict"] = self.support_verdict
        return given


@dataclass(frozen=True)
class FigureBox:
    """
    A stretch of the figure, in centimetres from its top left corner.
    """

    x: float
    """
    Its left edge.
    """

    y: float
    """
    Its top edge.
    """

    width: float
    """
    How wide it is.
    """

    height: float
    """
    How tall it is.
    """

    @classmethod
    def from_query(cls, given: Dict[str, float]) -> FigureBox:
        """
        :param given: A box as the figure's geometry metadata states it.
        """
        return cls(x=given["x"], y=given["y"], width=given["w"], height=given["h"])


@dataclass(frozen=True)
class FigureGeometry:
    """
    Where the figure's columns and panels lie, as the figure itself states them.
    """

    width: float
    """
    The figure's width, in centimetres.
    """

    height: float
    """
    The figure's height, in centimetres.
    """

    plan: FigureBox
    """
    The column of the underspecified plan.
    """

    resolved: FigureBox
    """
    The column of the resolved plan.
    """

    panels: Dict[Slot, FigureBox]
    """
    Each backend's panel, by the slot it answers.
    """

    slots: Dict[Slot, FigureBox]
    """
    Each open slot of the plan: the sub-query its backend answers, as the plan boxes it.
    """

    actions: Dict[PlanAction, FigureBox]
    """
    The stretch of the plan each of its actions takes, from its first line to its last.
    """

    @classmethod
    def from_query(cls, given: Dict[str, object]) -> FigureGeometry:
        """
        :param given: The geometry as the figure's metadata states it.
        """
        return cls(
            width=given["width"],
            height=given["height"],
            plan=FigureBox.from_query(given["plan"]),
            resolved=FigureBox.from_query(given["resolved"]),
            panels={slot: FigureBox.from_query(given["panels"][slot.value]) for slot in Slot},
            slots={slot: FigureBox.from_query(given["slots"][slot.value]) for slot in Slot},
            actions={action: FigureBox.from_query(given["actions"][action.value]) for action in PlanAction},
        )


GEOMETRY_LABEL = "<geometry>"
"""
The typst label the figure states its geometry under.
"""


@dataclass(frozen=True)
class FrameworkFigure:
    """
    The figure at one stage of being answered.
    """

    stage: int = len(Slot)
    """
    How many backends have answered, in the order the choice asks them.
    """

    focus: Optional[Slot] = None
    """
    The open slot being answered right now, ringed in its own hue.
    """

    readings: RunReadings = RunReadings()
    """
    What the run read, where the figure's source states a stand-in.
    """

    bubble_only: bool = True
    """
    Whether to draw only the thought bubble, without the robot below it.
    """

    panel_titles: Optional[Dict[Slot, str]] = None
    """
    What each backend's panel is titled, or None to keep the source's titles.
    """

    source: Path = FIGURE_SOURCE
    """
    The figure's typst source.
    """

    def as_input(self) -> Dict[str, object]:
        """
        This stage as the figure's input carries it.
        """
        given: Dict[str, object] = {
            "stage": self.stage,
            "bubble_only": self.bubble_only,
        }
        if self.focus is not None:
            given["focus"] = self.focus.value
        if self.panel_titles is not None:
            given["panel_titles"] = {
                slot.value: title for slot, title in self.panel_titles.items()
            }
        given.update(self.readings.as_input())
        return given

    @property
    def geometry(self) -> FigureGeometry:
        """
        Where the figure's columns and panels lie at this stage.
        """
        # the query answers as JSON text
        return FigureGeometry.from_query(
            json.loads(
                typst.query(
                    str(self.source),
                    GEOMETRY_LABEL,
                    field="value",
                    one=True,
                    sys_inputs={VIDEO_INPUT: json.dumps(self.as_input())},
                )
            )
        )

    def drawn(self, width: int) -> Frame:
        """
        Compile the figure to a picture.

        :param width: How many pixels wide the picture is.
        :return: The picture, as red, green and blue.
        """
        pixels_per_inch = width / (FIGURE_WIDTH_CENTIMETRES / CENTIMETRES_PER_INCH)
        encoded = typst.compile(
            str(self.source),
            format="png",
            ppi=pixels_per_inch,
            sys_inputs={VIDEO_INPUT: json.dumps(self.as_input())},
        )
        picture = Image.open(io.BytesIO(encoded)).convert("RGB")
        return np.asarray(picture)
