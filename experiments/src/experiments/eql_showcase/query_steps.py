"""
The queries the robot asks while it resolves a plan and carries it out, one step each,
held until the viewer moves on when it steps through them.

Every query asked where the steps observe is kept with the code that asks it, the
question it asks in English, what answers it and its answers, so a person can follow
what the robot asks and why it acts as it does.
"""

from __future__ import annotations

import ast
import linecache
import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from enum import StrEnum
from functools import lru_cache
from pathlib import Path

from typing_extensions import Any, Callable, Dict, Iterator, List

from coraplex.plans.plan_node import ActionNode
from cramera.knowledge.query_verbalization import QueryVerbalization
from cramera.live.query_steps import QueryStepControl
from cramera.paths import repository_root
from krrood.entity_query_language._monitoring import monitored
from krrood.entity_query_language._stack import StackFrame
from krrood.entity_query_language.backends import (
    EntityQueryLanguageGenerativeBackend,
    ProbabilisticBackend,
)
from krrood.entity_query_language.query_observation import (
    AskedQuery,
    QueryLanguagePackage,
    QueryObservation,
    QueryObserver,
)
from semantic_digital_twin.datastructures.joint_state import JointState
from semantic_digital_twin.robots.robot_parts import AbstractRobotPart, Arm
from semantic_digital_twin.world_description.world_entity import (
    KinematicStructureEntity,
    SemanticAnnotation,
)

from experiments.eql_showcase.open_slots import (
    Faculty,
    Insertion,
    OpenSlotAnswerer,
    Reasoning,
    SideGrasp,
    SlotBackend,
)
from experiments.eql_showcase.perceived_twin import SeenHole
from experiments.eql_showcase.performed_actions import PerformedActions

# %% where a step happens


class SituationLabel(StrEnum):
    """
    What the robot is said to be doing where no plan or action names it.
    """

    EXPANDING = "expanding the plan into motions"
    """
    A plan is being expanded into the motions that carry it out.
    """


class Phase(StrEnum):
    """
    What the robot is doing when it asks a query.
    """

    RESOLUTION = "resolution"
    """
    Answering the parts a plan leaves open, before it moves.
    """

    EXPANSION = "expansion"
    """
    Expanding a resolved plan into the motions that carry it out, before it moves.
    """

    EXECUTION = "execution"
    """
    Carrying a resolved plan out.
    """


class StepMoment(StrEnum):
    """
    The moments of a query a step is held at.
    """

    ASKED = "asked"
    """
    The query was asked; nothing answers it yet.
    """

    ANSWERED = "answered"
    """
    The query's answering ended.
    """


@dataclass
class StepSituation:
    """
    What the robot was doing when it asked a query.
    """

    phase: Phase
    """
    Whether it was resolving or carrying out a plan.
    """

    during: str
    """
    The plan being resolved or the action being carried out, as said to a person.
    """

    @classmethod
    def of_performance(cls, performed: PerformedActions) -> StepSituation | None:
        """
        :param performed: The plans the robot performs.
        :return: The action being carried out, or the plan being expanded into motions
            before any action runs, or None while no plan is performed.
        """
        actions = performed.running(ActionNode)
        if actions:
            return cls(Phase.EXECUTION, type(actions[0].designator).__name__)
        nodes = performed.running()
        if nodes:
            return cls(Phase.EXPANSION, SituationLabel.EXPANDING)
        return None


# %% the code a query is written in


@dataclass
class SourceExcerpt:
    """
    The lines of the repository a query is written in, the statement writing it in
    focus.
    """

    file: str
    """
    The file, relative to the repository's root.
    """

    function: str
    """
    The function the statement is in.
    """

    first_line: int
    """
    The number of the first line shown.
    """

    lines: List[str]
    """
    The lines shown.
    """

    focus_first_line: int
    """
    The number of the first line of the statement.
    """

    focus_last_line: int
    """
    The number of the last line of the statement.
    """

    @classmethod
    def of_frame(
        cls, frame: StackFrame, context_lines: int = 2, longest_statement: int = 16
    ) -> SourceExcerpt:
        """
        :param frame: The frame the statement runs in.
        :param context_lines: How many lines around the statement are shown.
        :param longest_statement: How many lines of a long statement are shown.
        :return: The statement the frame runs and the lines around it.
        """
        first, last = cls.statement_lines(frame.filename, frame.lineno)
        last = min(last, first + longest_statement - 1)
        shown_first = max(1, first - context_lines)
        shown_last = last + context_lines
        root = repository_root()
        path = Path(frame.filename)
        return cls(
            file=str(path.relative_to(root) if path.is_relative_to(root) else path),
            function=frame.function_name,
            first_line=shown_first,
            lines=[
                linecache.getline(frame.filename, number).rstrip("\n")
                for number in range(shown_first, shown_last + 1)
            ],
            focus_first_line=first,
            focus_last_line=last,
        )

    @staticmethod
    @lru_cache(maxsize=None)
    def statements_of(filename: str) -> tuple[tuple[int, int], ...]:
        """
        :param filename: A Python source file.
        :return: The first and last line of every statement in it.
        """
        tree = ast.parse("".join(linecache.getlines(filename)))
        return tuple(
            (node.lineno, node.end_lineno)
            for node in ast.walk(tree)
            if isinstance(node, ast.stmt)
            and not isinstance(
                node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
            )
        )

    @classmethod
    def statement_lines(cls, filename: str, line: int) -> tuple[int, int]:
        """
        :param filename: A Python source file.
        :param line: A line of it.
        :return: The first and last line of the innermost statement holding the line.
        """
        holding = [
            (first, last)
            for first, last in cls.statements_of(filename)
            if first <= line <= last
        ]
        return min(holding, key=lambda lines: lines[1] - lines[0], default=(line, line))

    def to_payload(self) -> Dict[str, Any]:
        """
        :return: The excerpt as JSON for the viewer.
        """
        return {
            "file": self.file,
            "function": self.function,
            "firstLine": self.first_line,
            "lines": self.lines,
            "focus": [self.focus_first_line, self.focus_last_line],
        }


# %% what an answer is about in the scene


@dataclass
class AnswerBodies:
    """
    The bodies of the scene an answer is about, which light up while it is shown.
    """

    answer: Any
    """
    The answer.
    """

    def bodies(self) -> List[KinematicStructureEntity]:
        """
        :return: The bodies and regions the answer is about.
        """
        answer = self.answer
        if isinstance(answer, KinematicStructureEntity):
            return [answer]
        if isinstance(answer, JointState):
            return [connection.child for connection in answer.connections]
        if isinstance(answer, Insertion):
            return [answer.piece.root, answer.hole.region]
        if isinstance(answer, SideGrasp):
            return [] if answer.piece is None else [answer.piece.root]
        if isinstance(answer, SeenHole):
            return [answer.region]
        if isinstance(answer, Arm):
            return answer.end_effector.bodies
        if isinstance(answer, SemanticAnnotation):
            return answer.bodies
        return []

    def framed(self) -> List[KinematicStructureEntity]:
        """
        :return: The bodies the scene is framed on while the answer is shown; none
            for a part of the robot, which stays in view.
        """
        if isinstance(self.answer, (JointState, AbstractRobotPart)):
            return []
        return self.bodies()


# %% one query asked


@dataclass(eq=False)
class QueryStep:
    """
    One query the robot asked, as the viewer steps through it.
    """

    number: int
    """
    The query's place among every query asked, from 0.
    """

    asked: AskedQuery = field(repr=False)
    """
    The query asked.
    """

    situation: StepSituation
    """
    What the robot was doing when it asked it.
    """

    asker_number: int | None
    """
    The number of the step whose answering asked this one, if any.
    """

    started: float = field(default_factory=time.perf_counter, repr=False)
    """
    When the query was asked, by the performance counter.
    """

    seconds: float | None = None
    """
    How long answering took, once answered.
    """

    reasoning: Reasoning | None = field(default=None, repr=False)
    """
    How the backend that answered reasoned, drawn for a person, if it draws one.
    """

    def answered(self) -> None:
        """
        Note that the query's answering ended, and how the backend reasoned.
        """
        self.seconds = time.perf_counter() - self.started
        backend = self.asked.backend
        if isinstance(backend, SlotBackend):
            self.reasoning = backend.reasoning_for(self.asked.query, self.asked.answers)

    @property
    def moment(self) -> StepMoment:
        """
        How far the query has come.
        """
        return StepMoment.ANSWERED if self.asked.is_answered else StepMoment.ASKED

    @property
    def faculty(self) -> Faculty:
        """
        The kind of knowledge that answers the query.
        """
        backend = self.asked.backend
        if isinstance(backend, SlotBackend):
            return backend.faculty
        if isinstance(backend, ProbabilisticBackend):
            return Faculty.PROBABILISTIC
        if any(
            expression._conclusions_
            for expression in self.asked.query._all_expressions_
        ):
            return Faculty.RULES
        return Faculty.WORKING_MEMORY

    def written_at(self) -> SourceExcerpt | None:
        """
        :return: The code that writes the query, or that asks it where the query does
            not record where it was written.
        """
        frame = self.writing_frame()
        return None if frame is None else SourceExcerpt.of_frame(frame)

    def writing_frame(self) -> StackFrame | None:
        """
        :return: The innermost call outside the query language that wrote the query,
            else the one that asked it.
        """
        stack = monitored.get_stack(self.asked.query)
        written = (
            None
            if stack is None
            else next(
                (
                    frame
                    for frame in stack
                    if not (frame.module_name or "").startswith(
                        QueryLanguagePackage.NAME
                    )
                ),
                None,
            )
        )
        return written or self.asked.asking_frame

    def to_payload(self) -> Dict[str, Any]:
        """
        :return: The step as JSON for the viewer.
        """
        question = QueryVerbalization.of_expression(
            self.asked.query, self.asked.backend
        )
        written = self.written_at()
        asking = self.asked.asking_frame
        answers = self.asked.answers
        return {
            "number": self.number,
            "asker": self.asker_number,
            "depth": self.asked.depth,
            "phase": self.situation.phase.value,
            "during": self.situation.during,
            "moment": self.moment.value,
            "question": None if question is None else question.to_payload(),
            "code": None if written is None else written.to_payload(),
            "askedFrom": (
                None
                if asking is None
                else {
                    "function": asking.function_name,
                    "module": asking.module_name,
                    "line": asking.lineno,
                }
            ),
            "faculty": self.faculty.value,
            "backend": type(self.asked.backend).__name__,
            "generates": isinstance(
                self.asked.backend, EntityQueryLanguageGenerativeBackend
            ),
            "answers": [OpenSlotAnswerer.name_of(answer) for answer in answers],
            "highlight": [
                str(body.name)
                for answer in answers
                for body in AnswerBodies(answer).bodies()
            ],
            "frame": [
                str(body.name)
                for answer in answers
                for body in AnswerBodies(answer).framed()
            ],
            "reasoning": (
                None if self.reasoning is None else self.reasoning.to_payload()
            ),
            "milliseconds": (
                None if self.seconds is None else round(self.seconds * 1000, 1)
            ),
        }


# %% stepping through the queries


@dataclass
class QueryStepper(QueryObserver, QueryStepControl):
    """
    Keeps every query the robot asks as a step, and holds the robot at each step until
    the viewer moves on while it steps through them.
    """

    situation_of: Callable[[], StepSituation]
    """
    Tells what the robot is doing at the moment.
    """

    publish: Callable[[Dict[str, Any]], None] | None = None
    """
    Shows the steps in the viewer, if this run is shown in one.
    """

    steps: List[QueryStep] = field(default_factory=list)
    """
    Every query asked, in the order asked.
    """

    is_stepping: bool = False
    """
    Whether the robot is held at every step until the viewer moves on.
    """

    holds_nested: bool = True
    """
    Whether the robot is also held at queries asked while another is answered.
    """

    held: QueryStep | None = None
    """
    The step the robot is held at, if any.
    """

    shown_steps: int = 200
    """
    How many of the latest steps the viewer is shown.
    """

    _change: threading.Condition = field(
        default_factory=threading.Condition, init=False, repr=False
    )
    """
    Signalled whenever the viewer moves on or stops stepping.
    """

    _payloads: Dict[int, Dict[str, Any]] = field(
        default_factory=dict, init=False, repr=False
    )
    """
    The JSON of every answered step, which no longer changes.
    """

    _by_asked: Dict[int, QueryStep] = field(
        default_factory=dict, init=False, repr=False
    )
    """
    The step of each asked query, by the query's identity.
    """

    @contextmanager
    def observing(self) -> Iterator[None]:
        """
        Keep every query asked in the current thread as a step while the block runs.
        """
        with QueryObservation().observed_by(self):
            yield

    def on_query_asked(self, asked: AskedQuery) -> None:
        asker = None if asked.asker is None else self._by_asked.get(id(asked.asker))
        step = QueryStep(
            number=len(self.steps),
            asked=asked,
            situation=self.situation_of(),
            asker_number=None if asker is None else asker.number,
        )
        self.steps.append(step)
        self._by_asked[id(asked)] = step
        self._hold(step)

    def on_query_answered(self, asked: AskedQuery) -> None:
        step = self._by_asked.pop(id(asked), None)
        if step is None:
            return
        step.answered()
        self._payloads[step.number] = step.to_payload()
        self._hold(step)

    def _hold(self, step: QueryStep) -> None:
        """
        Show a step, and hold the robot at it until the viewer moves on while stepping.

        :param step: The step that changed.
        """
        with self._change:
            if self.is_stepping and (self.holds_nested or step.asked.depth == 0):
                self.held = step
            self._publish()
            self._change.wait_for(lambda: self.held is not step)

    def advance(self) -> None:
        with self._change:
            self.held = None
            self._publish()
            self._change.notify_all()

    def set_stepping(self, is_stepping: bool, holds_nested: bool) -> None:
        with self._change:
            self.is_stepping = is_stepping
            self.holds_nested = holds_nested
            if not is_stepping:
                self.held = None
            self._publish()
            self._change.notify_all()

    def _publish(self) -> None:
        """
        Show the steps in the viewer, if this run is shown in one.
        """
        if self.publish is not None:
            self.publish(self.to_payload())

    def to_payload(self) -> Dict[str, Any]:
        """
        :return: The latest steps and where the robot is held, as JSON for the viewer.
        """
        return {
            "stepping": self.is_stepping,
            "holdsNested": self.holds_nested,
            "held": None if self.held is None else self.held.number,
            "heldMoment": None if self.held is None else self.held.moment.value,
            "total": len(self.steps),
            "steps": [
                self._payloads.get(step.number) or step.to_payload()
                for step in self.steps[-self.shown_steps :]
            ],
        }
