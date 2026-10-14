"""
The EQL showcase: a robot demonstration's world, its detected events and its own
actions, offered to the cramera viewer's EQL panel with ready-made questions.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path

import yaml
from typing_extensions import Dict, List, Optional, Tuple

from coraplex.plans.plan import Plan
from cramera.knowledge.presets import Preset
from cramera.knowledge.query_domain import QueryDomain
from cramera.knowledge.queryable_knowledge import QueryableKnowledge, QueryScope
from cramera.live.bridge import Bridge
from cramera.live.detections import DetectedEvents
from segmind.event_logger import EventLogger
from semantic_digital_twin.world import World

from experiments.eql_showcase.commands import (
    ResolutionStep,
    ResolutionSteps,
    RobotCommand,
    RobotCommander,
)
from experiments.eql_showcase.episodic_memory import RunDatabase, SqlEvaluation
from experiments.eql_showcase.performed_actions import (
    PerformedAction,
    PerformedActions,
    RecordedRun,
)

QUESTIONS_FILE = Path(__file__).with_name("questions.yaml")
"""
The file the showcase's ready-made questions are read from.
"""

SHOWCASE_TITLE = "EQL showcase"
"""
The name the viewer shows for the showcase's questions.
"""

# %% the ready-made questions


class QuestionField(StrEnum):
    """
    Key one question is written under in the questions file.
    """

    SCOPE = "scope"
    TEXT = "text"
    CODE = "code"
    COMMANDS_THE_ROBOT = "commands_the_robot"


class ShowcaseVariable(StrEnum):
    """
    Name a showcase question binds one of its ready-made variables to.
    """

    ACTION = "action"
    RUN = "run"
    STEP = "step"
    COMMAND = "command"
    ROBOT = "robot"


@dataclass(frozen=True)
class ShowcaseQuestion:
    """
    One question the showcase offers, and the query that answers it.
    """

    scope: QueryScope
    """
    The body of knowledge the question is asked of.
    """

    text: str
    """
    The question as its button reads.
    """

    code: str
    """
    The EQL query answering the question.
    """

    commands_the_robot: bool = False
    """
    Whether this is a command to the robot rather than a question, offered only while
    the robot can take commands.
    """

    @classmethod
    def from_json(cls, data: Dict[str, str]) -> ShowcaseQuestion:
        """
        One question as the questions file writes it.

        :param data: The question's entry in the questions file.
        """
        return cls(
            scope=QueryScope(data[QuestionField.SCOPE]),
            text=data[QuestionField.TEXT],
            code=data[QuestionField.CODE].strip(),
            commands_the_robot=bool(data.get(QuestionField.COMMANDS_THE_ROBOT, False)),
        )

    def preset(self) -> Preset:
        """
        The question as a button of the EQL panel.
        """
        return Preset(text=self.text, code=self.code, scope=self.scope)


@dataclass(frozen=True)
class ShowcaseQuestions:
    """
    The questions the showcase offers, in the order they are listed.
    """

    questions: Tuple[ShowcaseQuestion, ...]
    """
    Every question, in the order the questions file lists them.
    """

    @classmethod
    def from_file(cls, path: Path = QUESTIONS_FILE) -> ShowcaseQuestions:
        """
        The questions a questions file lists.

        :param path: The questions file to read.
        """
        entries = yaml.safe_load(path.read_text())
        return cls(tuple(ShowcaseQuestion.from_json(entry) for entry in entries))

    def presets(
        self, scopes: List[QueryScope], robot_takes_commands: bool = False
    ) -> List[Preset]:
        """
        The buttons for the questions about the given bodies of knowledge.

        :param scopes: The bodies of knowledge the questions may be asked of.
        :param robot_takes_commands: Whether commands to the robot are offered too.
        """
        return [
            question.preset()
            for question in self.questions
            if question.scope in scopes
            and (robot_takes_commands or not question.commands_the_robot)
        ]


# %% the showcase


@dataclass
class EqlShowcase:
    """
    A running demonstration's knowledge, offered to the viewer's EQL panel.

    The world and the robot's actions in the run in progress are asked about as they are
    now; the detected events once the demonstration segments what happens; the runs
    already finished, in SQL, once the showcase keeps a database of them.
    """

    world: World
    """
    The world the demonstration acts in.
    """

    database: Optional[RunDatabase] = None
    """
    The database the finished runs are kept in, or None to keep no runs.
    """

    performed_actions: PerformedActions = field(default_factory=PerformedActions)
    """
    The actions of every plan the demonstration has performed.
    """

    detected_events: Optional[DetectedEvents] = None
    """
    What the demonstration's detectors saw, once it segments events.
    """

    questions: ShowcaseQuestions = field(default_factory=ShowcaseQuestions.from_file)
    """
    The ready-made questions offered as buttons.
    """

    commander: Optional[RobotCommander] = None
    """
    What carries out the commands given from the viewer, once the robot can take them.
    """

    @property
    def resolution_steps(self) -> ResolutionSteps:
        """
        Every candidate considered for the open parts of the plans performed so far.
        """
        return ResolutionSteps(self.performed_actions.plans)

    def observe_plan(self, plan: Plan) -> None:
        """
        Remember a plan the demonstration performs, so questions about what the robot
        did range over its actions.

        :param plan: The plan about to be performed.
        """
        self.performed_actions.plans.append(plan)

    def observe_events(self, event_logger: EventLogger) -> None:
        """
        Offer what the demonstration's detectors log to questions about detected events.

        :param event_logger: The logger the detectors write their events to.
        """
        self.detected_events = DetectedEvents(event_logger)

    def remember_run(self, demonstration: str) -> None:
        """
        Keep the run in progress among the finished runs, if the showcase keeps any and
        the robot did anything in it.

        :param demonstration: The name of the demonstration that ran.
        """
        actions = list(self.performed_actions)
        if self.database is None or not actions:
            return
        self.database.remember(RecordedRun.of_actions(demonstration, actions))

    def knowledge(self) -> List[QueryableKnowledge]:
        """
        Every body of knowledge the showcase offers: the finished runs only while it
        keeps a database of them, the detected events only once the demonstration
        segments them.
        """
        current_state = QueryableKnowledge.of_world(self.world)
        current_state.domains.extend(
            [
                QueryDomain(
                    ShowcaseVariable.ACTION, PerformedAction, self.performed_actions
                ),
                QueryDomain(
                    ShowcaseVariable.STEP, ResolutionStep, self.resolution_steps
                ),
            ]
        )
        if self.commander is not None:
            current_state.domains.append(
                QueryDomain(
                    ShowcaseVariable.COMMAND, RobotCommand, self.commander.commands
                )
            )
            current_state.extra_names[ShowcaseVariable.ROBOT] = self.commander
        knowledge = [current_state]
        if self.database is not None:
            knowledge.append(
                QueryableKnowledge(
                    scope=QueryScope.EPISODIC_MEMORY,
                    domains=[
                        QueryDomain(ShowcaseVariable.RUN, RecordedRun),
                        QueryDomain(ShowcaseVariable.ACTION, PerformedAction),
                    ],
                    evaluation=SqlEvaluation(self.database),
                )
            )
        if self.detected_events is not None:
            knowledge.extend(self.detected_events.knowledge())
        return knowledge

    def presets(self) -> List[Preset]:
        """
        The buttons for every question the offered knowledge can answer, followed by the
        detected events' own.
        """
        offered = [item.scope for item in self.knowledge()]
        presets = self.questions.presets(offered, self.commander is not None)
        if self.detected_events is not None:
            presets.extend(self.detected_events.presets())
        return presets

    def unlisted_presets(self) -> List[Preset]:
        """
        The questions recognized when asked, but not shown as buttons.
        """
        if self.detected_events is None:
            return []
        return self.detected_events.unlisted_presets()

    def register_with(self, bridge: Bridge) -> None:
        """
        Offer the showcase's knowledge and questions to the viewer, replacing whatever
        was offered before.

        :param bridge: The bridge serving the viewer.
        """
        bridge.register_query_source(
            self.knowledge(), SHOWCASE_TITLE, self.presets(), self.unlisted_presets()
        )
