"""
What the video says about itself: the paper it goes with, and the words it must and
must not show.

Review is double anonymous, so nothing here names an author, a laboratory or the robot;
the robot is called what the paper calls it, and the one place a name could change is
this file.
"""

from __future__ import annotations

from dataclasses import dataclass

PAPER_ID = "3889"
"""
The paper's submission number, as the conference assigned it.
"""


@dataclass(frozen=True)
class VideoScript:
    """
    The words the video's slides carry.
    """

    title: str = (
        "A Unified Knowledge Representation and Reasoning Framework for "
        "Cognitive Architectures"
    )
    """
    The paper's title, as submitted.
    """

    conference: str = "ICRA 2027"
    """
    The conference the paper is submitted to.
    """

    paper_id: str = PAPER_ID
    """
    The paper's submission number.
    """

    kind: str = "Supplementary video"
    """
    What the video is, under the title.
    """

    robot_name: str = "the robot"
    """
    What the robot is called on screen; the paper names no robot, so neither does the
    video.
    """

    repository_link: str = (
        "https://anonymous.4open.science/r/cognitive_robot_abstract_machine-48BD/"
    )
    """
    Where the code is, anonymised as the paper links it.
    """

    @property
    def submission_line(self) -> str:
        """
        The conference and the paper's number, on one line.
        """
        return f"{self.conference}  ·  Paper ID {self.paper_id}"
