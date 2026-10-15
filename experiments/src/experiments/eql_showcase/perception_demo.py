"""
What Tracy's camera saw, committed into a digital twin and asked about in the cramera
viewer.

Run it through the viewer's demo wrapper, then open ``http://localhost:8711``::

    cramera-live experiments/src/experiments/eql_showcase/perception_demo.py

Each capture taken off the real camera over the Montessori board is looked at by the
perception pipeline in turn, and what it found -- the board, its holes and the loose
pieces -- replaces the twin's previous look. The EQL panel asks the twin about it with
the same predicates the robot reasons with.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from typing_extensions import Dict, List, Optional

from cramera.knowledge.queryable_knowledge import QueryableKnowledge, QueryScope
from cramera.live.bridge import Bridge
from cramera.live.runner import start
from experiments.montessori.perception.captures import (
    CAPTURE_DIRECTORY,
    CapturePart,
    SceneCapture,
)
from experiments.montessori.perception.node import TRACY_WORKSPACE
from experiments.montessori.perception.overlay import RectifiedView
from experiments.montessori.perception.pipeline import MontessoriPerceptionPipeline
from experiments.montessori.semantics import MontessoriShape
from experiments.montessori.world import BOARD_SCALE
from experiments.eql_showcase.perceived_twin import PerceivedTwin, SeenPiece
from experiments.eql_showcase.showcase import QUESTIONS_FILE, ShowcaseQuestions

PERCEPTION_QUESTIONS_FILE = QUESTIONS_FILE.with_name("perception_questions.yaml")
"""
The file the perception showcase's questions are read from.
"""

TRACY_TABLE_HEIGHT = 0.88
"""
Height of Tracy's table top, in metres, read off the ``map`` to ``table`` transform the
recordings the captures were taken from publish.
"""

SECONDS_PER_LOOK = 30.0
"""
How long each capture stays committed before the next one is looked at.
"""

LOOK_TITLE = "camera: {}"
"""
The name the viewer shows for the questions, with the capture being looked at.
"""

# %% the captures


def capture_names() -> List[str]:
    """
    The name of every capture shipped with the perception package, in order.
    """
    return sorted(
        path.name.removesuffix(CapturePart.COLOR)
        for path in CAPTURE_DIRECTORY.glob(f"*{CapturePart.COLOR}")
    )


# %% the showcase


@dataclass
class PerceptionShowcase:
    """
    Looks at the captures one after another, commits each look into the twin and offers
    the twin to the viewer's EQL panel.
    """

    bridge: Optional[Bridge]
    """
    The bridge serving the viewer, or None for a look no viewer is shown.
    """

    twin: PerceivedTwin = field(default_factory=PerceivedTwin.beside_tracy)
    """
    The twin each look is committed into.
    """

    pipeline: MontessoriPerceptionPipeline = field(
        default_factory=lambda: MontessoriPerceptionPipeline(
            region=TRACY_WORKSPACE,
            table_height=TRACY_TABLE_HEIGHT,
            board_height=float(BOARD_SCALE.z),
        )
    )
    """
    The perception pipeline the captures are looked at with.
    """

    questions: ShowcaseQuestions = field(
        default_factory=lambda: ShowcaseQuestions.from_file(PERCEPTION_QUESTIONS_FILE)
    )
    """
    The ready-made questions about what the camera saw.
    """

    view: Optional[RectifiedView] = field(init=False, default=None)
    """
    The camera's top-down view of the table in the last look, or None before the first.
    """

    def commit(self, capture_name: str) -> None:
        """
        Look at one capture and commit what was seen into the twin.

        :param capture_name: The capture to look at.
        """
        frame = SceneCapture.load(capture_name).to_frame()
        self.twin.commit(self.pipeline.detect(frame))
        self.view = RectifiedView(frame, self.pipeline.rectify_table(frame))

    def look_at(self, capture_name: str) -> None:
        """
        Look at one capture, commit what was seen and offer it to the viewer.

        :param capture_name: The capture to look at.
        """
        self.commit(capture_name)
        self.bridge.register_query_source(
            [self.knowledge()],
            LOOK_TITLE.format(capture_name.replace("_", " ")),
            self.questions.presets([QueryScope.CURRENT_STATE]),
        )

    def knowledge(self) -> QueryableKnowledge:
        """
        The twin as it is now, with every kind of Montessori piece in scope by name.
        """
        knowledge = QueryableKnowledge.of_world(self.twin.world)
        knowledge.extra_names.update(self.piece_kinds())
        return knowledge

    @staticmethod
    def piece_kinds() -> Dict[str, type]:
        """
        Every kind of Montessori piece, and the piece the robot can grasp, by name.
        """
        kinds = [MontessoriShape, *MontessoriShape.__subclasses__(), SeenPiece]
        return {kind.__name__: kind for kind in kinds}


def main(capture_name: Optional[str] = None) -> None:
    """
    Show what the camera saw: one capture, or every capture in turn, over and over.

    :param capture_name: The capture to look at, or None to cycle through them all.
    """
    twin = PerceivedTwin.beside_tracy()
    showcase = PerceptionShowcase(bridge=start(twin.world).bridge, twin=twin)
    if capture_name is not None:
        showcase.look_at(capture_name)
        return
    while True:
        for name in capture_names():
            showcase.look_at(name)
            time.sleep(SECONDS_PER_LOOK)


if __name__ == "__main__":
    main()
