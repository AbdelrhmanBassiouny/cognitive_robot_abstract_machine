"""
What the video says about itself: the paper it goes with, the words it must and must
not show, and what the narrator says over each part.

Review is double anonymous, so nothing here names an author, a laboratory or the robot;
the robot is called what the paper calls it, and the one place a name could change is
this file.
"""

from __future__ import annotations

from dataclasses import dataclass, field

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
        "The framework provides a common query interface over heterogeneous knowledge "
        "sources and computations: a query's representation and grounded meaning are "
        "separated from its computation, so that different backends can answer the "
        "same query from different knowledge sources."
    )
    plan: Line = Line(
        "We demonstrate this with an under-specified plan, written in the query "
        "interface over an action domain language: pick up the cyan cube resting on "
        "the Montessori board and insert it into a hole, leaving the cube's pose, the "
        "grasp approach direction, and the hole open."
    )
    backend_choice: Line = Line(
        "The plan is resolved from its innermost open sub-query outward. Backends are "
        "chosen by capability-based meta-queries over the given task, with an order of "
        "preference among the capable ones: perception, working memory, rule-based "
        "reasoning, then probabilistic reasoning."
    )
    perception: Line = Line(
        "Finding the cube falls to the perception backend. The conditions stated about "
        "the cube narrow its search: support restricts the view to the lid, and colour "
        "segments the cyan piece within it."
    )
    working_memory: Line = Line(
        "As a verification, the working-memory backend evaluates the support condition "
        "again in simulation: a geometric check for interference between the cube's "
        "bottom and the board's top confirms that the cube is actually resting on the "
        "lid."
    )
    probabilistic: Line = Line(
        "Only the probabilistic backend declares itself capable of choosing the grasp "
        "approach direction. From its model registry it selects the model fitting the "
        "query — here a prior categorical distribution over approach directions — and "
        "samples the direction from it."
    )
    rules: Line = Line(
        "The hole to insert the cube into is inferred by the rule-based reasoning "
        "backend, which matches the cube's known shape against the holes held in "
        "working memory and selects the hole whose outline fits."
    )
    resolved: Line = Line(
        "With every open field answered, the resolved plan is executed on the robot."
    )
    attribution: Line = Line(
        "Next, temporal and action-attribution queries, enabled by an event "
        "segmentation framework running alongside the agent program. Which objects "
        "moved is answered from the motion events and their tracked objects; which of "
        "them the robot moved, from the agent-interaction events restricted to those "
        "objects."
    )
    perturbations: Line = Line(
        "Finally, we evaluate the system over many real-world runs in which the "
        "objects are perturbed during execution, and the program adapts. Every run is "
        "recorded by the architecture's episodic memory: the environment, sensor "
        "readings, tasks, the executed plan and the detected events. The same queries "
        "are then answered by the long-term memory backend over all recorded episodes: "
        "in which episodes did the cube move, and in which did the robot pick it up?"
    )
    closing: Line = Line("Thank you for watching.")
