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
class Chapter:
    """
    One of the video's chapters: a contribution of the paper, stated as its claim.
    """

    number: int
    """
    Which chapter, from one.
    """

    claim: str
    """
    The claim, as it is shown large when the chapter starts and then kept in its pill.
    """


CHAPTERS: Tuple[Chapter, ...] = (
    Chapter(1, "Backends complete what an underspecified query leaves open"),
    Chapter(2, "One query language reaches events and plans, without integration code"),
    Chapter(3, "Evaluated on a real robot"),
)
"""
The three chapters, in order: the paper's contributions.
"""


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

    chapters: Tuple[Chapter, ...] = CHAPTERS
    """
    The chapters, in order.
    """

    principle: str = "Backends differ in source and mechanism, never in the description."
    """
    The paper's principle, as the hero frame carries it in large type; the narrator
    says the paper's full sentence.
    """

    statement_label: str = "the statement"
    """
    What stands above the divider of the hero frame: the query.
    """

    backends_label: str = "backends"
    """
    What stands below the divider of the hero frame.
    """

    grasp_gloss: str = (
        "a grasp with the left hand, from the top, approach direction still to be chosen"
    )
    """
    The example query in plain words, unlabelled beside it.
    """

    backend_choice: str = (
        "holds backends in an order of preference and answers with the first capable one"
    )
    """
    What a backend choice does, under its name in the taxonomy (Section IV-B).
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

    # said over the title, which is not read out, and running on into the first chapter
    opening: Line = Line(
        "One query interface connects perception, memory, probabilistic reasoning, "
        "logical inference, and robot action."
    )
    query: Line = Line(
        "Here, a query for a grasp: left hand, from the top; the approach direction, "
        "written as `...`, is left open.",
        spoken="Here, a query for a grasp: left hand, from the top; the approach "
        "direction, written as three dots, is left open.",
    )
    # what a backend choice does is written under its name on the slide, not read out
    backends: Line = Line(
        "Selective backends retrieve what is known; generative backends infer new "
        "instances; a backend choice orders them."
    )
    # the paper's own sentence (Section IV-A), said whole over the hero frame
    principle: Line = Line(
        "Backends differ in their source of information and their mechanism, never in "
        "the description, so the query representation stays unchanged."
    )
    plan: Line = Line(
        "The plan is one nested query: pick up the cyan cube resting on the board, and "
        "insert it into a hole. Cube, approach direction and hole are left open."
    )
    perception_query: Line = Line("Finding the cube falls to the perception backend.")
    perception_views: Tuple[Line, ...] = (
        Line("The table is rectified to the plane the detectors read;"),
        Line("support restricts the view to the lid;"),
        Line("colour segments what is cyan on it;"),
        Line("and the cube is what remains."),
    )
    working_memory: Line = Line(
        "The working memory backend verifies in simulation that the cube rests on the "
        "lid."
    )
    probabilistic_query: Line = Line(
        "Only the probabilistic backend is capable of choosing the grasp approach "
        "direction."
    )
    probabilistic: Line = Line(
        "From its model registry it selects the model fitting the query — a prior "
        "over approach directions — and samples from it."
    )
    rules_query: Line = Line("The hole is inferred by the ripple down rules backend.")
    rules: Line = Line(
        "It matches the cube's known shape against the holes in working memory and "
        "selects the one whose outline fits."
    )
    resolved: Line = Line(
        "With every field answered, the resolved plan is executed on the robot."
    )
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
        "Who moved what is answered from an event segmentation framework running "
        "alongside the agent program."
    )
    # said as the first query over event classes comes up (contribution 2)
    event_classes: Line = Line(
        "These are classes of the event segmentation itself. The classes of the control "
        "programs are the concepts of the knowledge base, so the query needs no code "
        "written for integration."
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
        "Every run is recorded as an episode, and the same kind of query goes to long "
        "term memory: in which episodes did the robot pick the cube up?"
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
