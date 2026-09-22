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

@dataclass(frozen=True)
class ResultRow:
    """
    One row of the results table: what was measured and its value with its unit.
    """

    measure: str
    value: str


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

    run_values_note: str = "values from the recorded run; Fig. 1 in the paper is illustrative"
    """
    The footnote on the resolved plan: the grasp the probabilistic backend chose and the
    cube's pose are the recorded run's, and the paper's figure shows stand-ins.
    """

    grid_header: str = "13 trials in 7 episodes on the real robot; six conditions shown"
    """
    The one line over the grid of perturbed runs (Section VI-E).
    """

    long_term_header: str = "asked of long term memory, over the 7 episodes recorded on the real robot"
    """
    What the long term memory query is asked over.
    """

    results_title: str = "On the real robot: 13 trials in 7 episodes"
    """
    Over the results table.
    """

    results: Tuple[ResultRow, ...] = (
        ResultRow("Executed plans that reached their goal", "4 of 4"),
        ResultRow("Questions answered correctly", "213 of 213"),
        ResultRow("Mean latency per predicate, working memory", "0.10 s"),
    )
    """
    The results table (Table V and Section VI): every number is the paper's.
    """

    code_label: str = "Code and recorded episodes"
    """
    Over the link on the end card.
    """


# %% what is said


@dataclass(frozen=True)
class NarrationLines:
    """
    What the narrator says, one line per part of the video, in the order they are heard.

    Every line starts with the part it names and may run on into what follows it; the
    code refuses a line that is still being said when the next begins.
    """

    # the title is on the slide and is not read out; what the video shows is said over it
    summary: Line = Line(
        "It shows how one query interface connects perception, memory, probabilistic "
        "reasoning, logical inference, and robot action."
    )
    # "that means:" made the voice break before "that"; the bare colon pauses once, after it
    plan_pick_up: Line = Line(
        "We demonstrate this with a plan written as a nested query over an action and "
        "world domain language: pick up the cyan cube resting on the board,"
    )
    plan_insertion: Line = Line(
        "and insert it into a hole. The cube, the approach direction and the hole are "
        "left open, and resolved from the innermost query outward."
    )
    perception_query: Line = Line(
        "A backend choice orders the backends that declare themselves capable of "
        "answering the given query by preference; and in this case, finding the cube "
        "falls to the perception backend."
    )
    perception_views: Tuple[Line, ...] = (
        Line("The table is rectified to the plane the detectors read;"),
        Line("support restricts the view to the lid;"),
        Line("colour segments what is cyan on it;"),
        Line("and the cube is what remains."),
    )
    working_memory_query: Line = Line(
        "The working memory backend verifies the support condition in simulation."
    )
    working_memory: Line = Line(
        "A geometric check for interference between the cube's bottom and the board's "
        "top confirms that the cube rests on the lid."
    )
    probabilistic_query: Line = Line(
        "Only the probabilistic backend can choose the approach direction."
    )
    probabilistic: Line = Line(
        "From its model registry it selects a prior over approach directions and "
        "samples from it."
    )
    rules_query: Line = Line("The hole is inferred by the ripple down rules backend.")
    rules: Line = Line(
        "It matches the cube's known shape against the holes in working memory and "
        "selects the one whose outline fits."
    )
    resolved: Line = Line("With every field answered, the plan is executed on the robot.")
    # said over the film of the robot acting, each as what it names is seen; the last
    # is the paper's result (Section VI-E)
    execution_perceived: Line = Line(
        "The robot perceives the scene as it stands and reaches for the cube it found,"
    )
    execution_grasp: Line = Line("grasps it from the left, as the backend sampled,")
    execution_carry: Line = Line("carries it over the board,")
    execution_insertion: Line = Line("and inserts it through the square hole the rules concluded.")
    execution_outcome: Line = Line("Every executed plan reached its goal.")
    attribution: Line = Line(
        "Who moved what is answered from the event segmentation running alongside the "
        "agent program."
    )
    # said as the first query over event classes comes up (contribution 2)
    event_classes: Line = Line(
        "These are the event segmentation's own classes, and the control programs' "
        "classes are the knowledge base's concepts: the query needs no integration "
        "code."
    )
    attribution_sorting: Line = Line(
        "Which objects moved comes from the motion events; which of them the robot "
        "moved, from the agent interaction events over those objects."
    )
    attribution_pushed: Line = Line(
        "In a second trial the robot stands idle while a person pushes the cube."
    )
    attribution_pushed_answer: Line = Line(
        "The cube moved, and no action of the robot moved it."
    )
    grid: Line = Line(
        "We evaluate the system over 13 trials on the real robot.",
        spoken="We evaluate the system over thirteen trials on the real robot.",
    )
    stands_still: Line = Line(
        "A person moves the board while the robot stands still: the scene moved, but "
        "the robot did not move it."
    )
    # the perturbations come before the robot acts; the plan is completed from the
    # scene as perception then finds it, and nothing is re-planned
    shoved: Line = Line(
        "Before the robot acts, a person shoves a piece. Perception captures the scene "
        "as it then stands, and the plan is completed from that."
    )
    long_term_memory: Line = Line(
        "Every run is an episode, and the same kind of query goes to long term memory: "
        "in which episodes did the robot pick the cube up?"
    )
    # the results table: the paper's numbers are on screen, not read out as numerals
    results: Line = Line(
        "Every executed plan reached its goal, and every scored question was answered "
        "correctly."
    )
    closing: Line = Line("Code and recorded episodes are at the link.")

    @property
    def every(self) -> Tuple[Line, ...]:
        """
        Every line, in the order it is heard.
        """
        lines: List[Line] = []
        for value in vars(self).values():
            lines.extend(value if isinstance(value, tuple) else [value])
        return tuple(lines)
