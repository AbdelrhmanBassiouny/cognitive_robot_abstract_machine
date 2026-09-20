"""
What the video says about itself: the paper it goes with, the words it must and must
not show, and what the narrator says over each part.

Review is double anonymous, so nothing here names an author, a laboratory or the robot;
the robot is called what the paper calls it, and the one place a name could change is
this file.
"""

from __future__ import annotations

from dataclasses import dataclass

from typing_extensions import List, Tuple

from experiments.video.narration import Line

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


# %% what is said


@dataclass(frozen=True)
class NarrationLines:
    """
    What the narrator says, one line per part of the video, in the order they are heard.

    Every line starts with the part it names and may run on into what follows it; the
    code refuses a line that is still being said when the next begins.
    """

    title: Line = Line(
        f"This video accompanies paper {PAPER_ID}: A Unified Knowledge Representation "
        "and Reasoning Framework for Cognitive Architectures.",
        spoken="This video accompanies paper thirty-eight eighty-nine: A Unified "
        "Knowledge Representation and Reasoning Framework for Cognitive Architectures.",
    )
    framework: Line = Line(
        "A query's representation and grounded meaning are kept apart from its "
        "computation, so any capable backend can answer it."
    )
    taxonomy: Line = Line(
        "Selective backends retrieve what is known; generative backends compute."
    )
    backend_choice: Line = Line(
        "A backend choice picks among the capable ones by meta-queries over the task, "
        "in an order of preference."
    )
    plan_pick_up: Line = Line(
        "We demonstrate this with an under-specified plan in the query interface over "
        "an action domain language: pick up the cyan cube resting on the board,"
    )
    plan_insertion: Line = Line(
        "and insert it into a hole. The cube's pose, the grasp approach direction and "
        "the hole are left open, and resolved from the innermost sub-query outward."
    )
    perception_query: Line = Line("Finding the cube falls to the perception backend.")
    perception_views: Tuple[Line, ...] = (
        Line("The table is rectified to the plane the detectors read;"),
        Line("support restricts the view to the lid;"),
        Line("colour segments what is cyan on it;"),
        Line("and the cube is what remains."),
    )
    working_memory_query: Line = Line(
        "The working-memory backend verifies the support condition again, in "
        "simulation."
    )
    working_memory: Line = Line(
        "A geometric check for interference between the cube's bottom and the board's "
        "top confirms that the cube rests on the lid."
    )
    probabilistic_query: Line = Line(
        "Only the probabilistic backend is capable of choosing the grasp approach "
        "direction."
    )
    probabilistic: Line = Line(
        "From its model registry it selects the model fitting the query — a prior "
        "over approach directions — and samples from it."
    )
    rules_query: Line = Line(
        "The hole is inferred by the rule-based reasoning backend."
    )
    rules: Line = Line(
        "It matches the cube's known shape against the holes held in working memory "
        "and selects the hole whose outline fits."
    )
    resolved: Line = Line(
        "With every open field answered, the resolved plan is executed on the robot."
    )
    attribution: Line = Line(
        "Next, temporal and action-attribution queries, enabled by an event "
        "segmentation framework running alongside the agent program."
    )
    attribution_sorting: Line = Line(
        "Which objects moved is answered from the motion events and their tracked "
        "objects; which of them the robot moved, from the agent-interaction events "
        "restricted to those objects."
    )
    attribution_pushed: Line = Line(
        "In a second trial the robot stands idle while a person pushes the cube: it "
        "moved, but not by the robot."
    )
    perturbations: Line = Line(
        "Finally, we evaluate the system over many real-world runs in which the "
        "objects are perturbed during execution, and the program adapts."
    )
    episodic_memory: Line = Line(
        "Every run is recorded by the architecture's episodic memory: environment, "
        "sensor readings, tasks, plan and detected events."
    )
    long_term_memory: Line = Line(
        "The same queries then go to the long-term memory backend over all recorded "
        "episodes: in which did the cube move, and in which did the robot pick it up?"
    )
    closing: Line = Line("Thank you for watching.")

    @property
    def every(self) -> Tuple[Line, ...]:
        """
        Every line, in the order it is heard.
        """
        lines: List[Line] = []
        for value in vars(self).values():
            lines.extend(value if isinstance(value, tuple) else [value])
        return tuple(lines)
