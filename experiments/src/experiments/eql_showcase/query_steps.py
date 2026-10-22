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
import re
import sys
import threading
import time
from contextlib import contextmanager
from dataclasses import MISSING, asdict, dataclass, field, fields
from enum import StrEnum
from functools import lru_cache
from pathlib import Path

from typing_extensions import Any, Callable, Dict, Iterator, List

from coraplex.plans.designator import Designator
from coraplex.plans.plan_node import ActionNode, DesignatorNode
from coraplex.robot_plans.actions.base import ActionDescription
from cramera.knowledge.query_verbalization import QueryVerbalization
from cramera.live.query_steps import HeldStep, QueryStepControl, StepMoment
from cramera.paths import repository_root
from krrood.entity_query_language._monitoring import monitored
from krrood.entity_query_language import factories
from krrood.entity_query_language._stack import StackFrame
from krrood.entity_query_language.backends import (
    EntityQueryLanguageGenerativeBackend,
    ProbabilisticBackend,
)
from krrood.entity_query_language.core.variable import (
    InstantiatedVariable,
    Literal,
    Variable,
)
from krrood.entity_query_language.operators.comparator import Comparator
from krrood.entity_query_language.query.match import Match
from krrood.entity_query_language.query.query import Query
from krrood.entity_query_language.query_observation import (
    AskedQuery,
    QueryLanguagePackage,
    QueryObservation,
    QueryObserver,
)
from krrood.entity_query_language.verbalization.pipeline import verbalize_expression
from semantic_digital_twin.spatial_types.spatial_types import Pose

from experiments.eql_showcase.open_slots import (
    AnswerBodies,
    ContactReading,
    ContactReasoning,
    Faculty,
    OpenSlotAnswerer,
    PlanResolution,
    Reasoning,
    SlotBackend,
    SlotIdentifier,
)
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

    SETUP = "setup"
    """
    Setting up the twin and the robot, before any plan exists.
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

    enclosing: List[EnclosingStatement] = field(default_factory=list)
    """
    The statements the robot is answering or carrying out, outermost first.
    """

    @classmethod
    def of_performance(cls, performed: PerformedActions) -> StepSituation | None:
        """
        :param performed: The plans the robot performs.
        :return: The action being carried out, or the plan being expanded into motions
            before any action runs, with the actions being expanded or carried out, or
            None while no plan is performed.
        """
        actions = performed.running(ActionNode)
        if actions:
            return cls(
                Phase.EXECUTION,
                type(actions[0].designator).__name__,
                EnclosingStatement.of_actions(performed),
            )
        nodes = performed.running()
        if nodes:
            return cls(
                Phase.EXPANSION,
                SituationLabel.EXPANDING,
                EnclosingStatement.of_actions(performed),
            )
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


class CandidateVerdict(StrEnum):
    """
    Whether a value a query selected among answers it.
    """

    ANSWERS = "answers the query"
    """
    The value satisfies every condition of the query.
    """

    DOES_NOT_ANSWER = "does not answer it"
    """
    The value fails a condition of the query.
    """


# %% the variables of a query


class VariableRole(StrEnum):
    """
    What a variable of a query, or a part of a statement, is to it.
    """

    SOUGHT = "sought"
    """
    What the query answers with.
    """

    RANGES_OVER = "ranges over"
    """
    A variable the query tries values of while it looks for answers.
    """

    GIVEN = "given"
    """
    A value the code asking the query fixed.
    """

    OPEN = "open"
    """
    A part left open, for a backend to answer.
    """

    BEING_ANSWERED = "being answered"
    """
    An open part whose answering is under way.
    """

    ANSWERED = "answered"
    """
    An open part a backend has answered.
    """


@dataclass
class QueryVariable:
    """
    A variable of a query or a part of a statement, and what it holds.
    """

    name: str
    """
    The name the code gives it, else the part of the statement it is.
    """

    role: VariableRole
    """
    What it is to the query.
    """

    values: List[str] = field(default_factory=list)
    """
    What it holds, as said to a person: the answers of a sought variable, the value
    given, or the answer of an answered part.
    """

    kind: str | None = None
    """
    The type of what it holds, where the query states one.
    """

    looked_at: int | None = None
    """
    How many values of its domain the query looked at, for a variable it ranges over.
    """

    @classmethod
    def of_asked(cls, asked: AskedQuery, most_shown: int = 8) -> List[QueryVariable]:
        """
        :param asked: An asked query.
        :param most_shown: How many variables are kept at most.
        :return: Its sought variable first, then those it ranges over and the values
            it was given.
        """
        query = asked.query
        answers = [cls.said(answer) for answer in asked.answers]
        if isinstance(query, Match):
            variables = cls.of_statement(query, answers)
        elif isinstance(query, Query):
            variables = cls.of_query(query, answers)
        else:
            variables = []
        merged: Dict[tuple[str, VariableRole], QueryVariable] = {}
        for variable in variables:
            kept = merged.setdefault((variable.name, variable.role), variable)
            if kept is not variable:
                kept.values.extend(
                    value for value in variable.values if value not in kept.values
                )
        return list(merged.values())[:most_shown]

    @classmethod
    def of_statement(cls, statement: Match, answers: List[str]) -> List[QueryVariable]:
        """
        :param statement: A statement of a type and its attributes.
        :param answers: Its answers so far, as said to a person.
        :return: What it seeks, then each attribute it states, given or left open.
        """
        sought = cls(
            cls.name_in_code(statement) or cls.noun_of(statement._type_.__name__),
            VariableRole.SOUGHT,
            answers,
            statement._type_.__name__,
        )
        return [
            sought,
            *[
                cls(
                    name,
                    VariableRole.OPEN if value is ... else VariableRole.GIVEN,
                    (
                        []
                        if value is ...
                        else [
                            (
                                verbalize_expression(value)
                                if isinstance(value, Match)
                                else cls.said(value)
                            )
                        ]
                    ),
                )
                for name, value in statement._kwargs_.items()
            ],
        ]

    @classmethod
    def of_query(cls, query: Query, answers: List[str]) -> List[QueryVariable]:
        """
        :param query: A query over variables.
        :param answers: Its answers so far, as said to a person.
        :return: Its sought variable, the variables it ranges over and the values
            its conditions compare them with.
        """
        selected = query.selected_variable
        variables = [
            cls(
                cls.name_in_code(selected) or cls.noun_of(str(selected._name_)),
                VariableRole.SOUGHT,
                answers,
                cls.type_name(selected._type_),
            )
        ]
        for expression in query._all_expressions_:
            if isinstance(expression, Literal):
                continue
            if isinstance(expression, Variable) and expression is not selected:
                variables.append(
                    cls(
                        cls.name_in_code(expression)
                        or cls.noun_of(str(expression._name_)),
                        VariableRole.RANGES_OVER,
                        kind=cls.type_name(expression._type_),
                        looked_at=len(
                            expression._re_enterable_domain_generator_.materialized_values
                        ),
                    )
                )
            variables.extend(cls.given_in(expression))
        return variables

    @classmethod
    def given_in(cls, expression: Any) -> List[QueryVariable]:
        """
        :param expression: A part of a query.
        :return: The values the code fixed in it: what a comparison compares with,
            named by what it is compared to, and what a predicate is given, named by
            its parameter.
        """
        if isinstance(expression, Comparator):
            return [
                cls(
                    str(other._name_).split(".")[-1],
                    VariableRole.GIVEN,
                    [cls.said(given._value_)],
                )
                for given, other in (
                    (expression.right, expression.left),
                    (expression.left, expression.right),
                )
                if isinstance(given, Literal) and not isinstance(other, Literal)
            ]
        if isinstance(expression, InstantiatedVariable):
            return [
                cls(parameter, VariableRole.GIVEN, [cls.said(given._value_)])
                for parameter, given in expression._kwargs_.items()
                if isinstance(given, Literal)
            ]
        return []

    @staticmethod
    def name_in_code(expression: Any) -> str | None:
        """
        :param expression: A variable or statement of a query.
        :return: The name the code that wrote it assigned it to, if it did.
        """
        stack = monitored.get_stack(expression)
        writing = (
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
        if writing is None:
            return None
        first, last = SourceExcerpt.statement_lines(writing.filename, writing.lineno)
        source = "".join(
            linecache.getline(writing.filename, number)
            for number in range(first, last + 1)
        ).strip()
        if not source:
            # code compiled from a string, such as a query typed in the viewer
            return None
        statement = ast.parse(source).body[0]
        if not (
            isinstance(statement, ast.Assign)
            and isinstance(statement.targets[0], ast.Name)
        ):
            return None
        # the name is the query's only where the statement builds the query itself
        built_by = statement.value
        while isinstance(built_by, (ast.Call, ast.Attribute)):
            built_by = (
                built_by.func if isinstance(built_by, ast.Call) else built_by.value
            )
        if isinstance(built_by, ast.Name) and built_by.id in vars(factories):
            return statement.targets[0].id
        return None

    @staticmethod
    def noun_of(type_name: str) -> str:
        """
        :param type_name: The name of a type, in capitalised words.
        :return: The name in lower-case words joined by underscores, as code names a
            variable of the type.
        """
        return re.sub(r"(?<!^)(?=[A-Z])", "_", type_name).lower()

    @staticmethod
    def type_name(kind: Any) -> str | None:
        """
        :param kind: The type a variable states, if any.
        :return: Its name.
        """
        return kind.__name__ if isinstance(kind, type) else None

    @classmethod
    def said(cls, value: Any, longest: int = 48) -> str:
        """
        :param value: A value a query holds.
        :param longest: How many characters are kept at most.
        :return: The value as said to a person.
        """
        if isinstance(value, (list, tuple, set)):
            return ", ".join(cls.said(item) for item in value)
        if isinstance(value, Pose):
            return "at " + ", ".join(
                f"{coordinate:.2f}" for coordinate in value.position.to_np()[:3]
            )
        said = OpenSlotAnswerer.name_of(value)
        if said.startswith(type(value).__name__ + "("):
            # a value without a name of its own is said by its type
            return type(value).__name__
        return said if len(said) <= longest else said[: longest - 1] + "…"


class EnclosingKind(StrEnum):
    """
    The statements a query can be asked as a part of.
    """

    PLAN = "plan being resolved"
    """
    A plan stated with parts left open, whose parts the backends answer.
    """

    ACTION = "action"
    """
    An action being expanded into motions or carried out.
    """

    MOTION = "motion"
    """
    A motion being turned into the motion state chart that carries it out.
    """


@dataclass
class EnclosingStatement:
    """
    A statement the robot is answering or carrying out while it asks a query.
    """

    kind: EnclosingKind
    """
    What kind of statement it is.
    """

    title: str
    """
    What it is, as said to a person.
    """

    statement: str | None
    """
    What it states, in English, if it is written as a statement.
    """

    variables: List[QueryVariable]
    """
    Its parts, each given, answered, being answered or open.
    """

    @classmethod
    def of_resolution(cls, resolution: PlanResolution) -> List[EnclosingStatement]:
        """
        :param resolution: A plan being resolved.
        :return: The plan as stated, each part with what it holds so far, if it was
            stated as a statement.
        """
        statement = resolution.statement
        if statement is None:
            return []
        return [
            cls(
                EnclosingKind.PLAN,
                resolution.name,
                verbalize_expression(statement),
                [
                    cls.part_of(resolution, name, value)
                    for name, value in statement._kwargs_.items()
                ],
            )
        ]

    @staticmethod
    def part_of(resolution: PlanResolution, name: str, stated: Any) -> QueryVariable:
        """
        :param resolution: A plan being resolved.
        :param name: A part of the plan.
        :param stated: The part as stated.
        :return: What the part holds so far.
        """
        answered = [
            part
            for part in resolution.parts
            if part.slot_id.split(SlotIdentifier.CONDITIONS_SEPARATOR)[0] == name
        ]
        asking = resolution.asking
        if (
            asking is not None
            and asking.split(SlotIdentifier.CONDITIONS_SEPARATOR)[0] == name
        ):
            return QueryVariable(name, VariableRole.BEING_ANSWERED)
        if answered:
            return QueryVariable(name, VariableRole.ANSWERED, answered[-1].answers[:1])
        if stated is ... or isinstance(stated, Match):
            return QueryVariable(name, VariableRole.OPEN)
        return QueryVariable(name, VariableRole.GIVEN, [QueryVariable.said(stated)])

    @classmethod
    def of_actions(cls, performed: PerformedActions) -> List[EnclosingStatement]:
        """
        :param performed: The plans the robot performs.
        :return: The actions running, then the actions and motions the current thread
            is expanding or turning into motions, outermost first, each with the parts
            it was given.
        """
        designators = [
            node.designator for node in reversed(performed.running(ActionNode))
        ]
        on_the_stack = []
        frame = sys._getframe(1)
        while frame is not None:
            performing = frame.f_locals.get("self")
            if isinstance(performing, DesignatorNode):
                performing = performing.designator
            if isinstance(performing, Designator) and not any(
                designator is performing for designator in designators + on_the_stack
            ):
                on_the_stack.append(performing)
            frame = frame.f_back
        designators.extend(reversed(on_the_stack))
        return [cls.of_designator(designator) for designator in designators]

    @classmethod
    def of_designator(cls, designator: Designator) -> EnclosingStatement:
        """
        :param designator: An action or motion.
        :return: It, with each part it was given that it has no default for.
        """
        return cls(
            (
                EnclosingKind.ACTION
                if isinstance(designator, ActionDescription)
                else EnclosingKind.MOTION
            ),
            type(designator).__name__,
            None,
            [
                QueryVariable(
                    stated.name,
                    VariableRole.GIVEN,
                    [QueryVariable.said(vars(designator)[stated.name])],
                )
                for stated in fields(designator)
                if stated.init
                and stated.default is MISSING
                and stated.default_factory is MISSING
            ],
        )


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
    When answering the query started, by the performance counter.
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
            return
        candidates = self.candidates()
        if candidates:
            self.reasoning = ContactReasoning(
                [
                    ContactReading(
                        candidate,
                        candidate in self.asked.answers,
                        (
                            CandidateVerdict.ANSWERS
                            if candidate in self.asked.answers
                            else CandidateVerdict.DOES_NOT_ANSWER
                        ),
                    )
                    for candidate in candidates
                ],
                "",
            )

    def answer_bodies(self, answer: Any) -> AnswerBodies:
        """
        :param answer: One of the query's answers.
        :return: What the answer is about in the scene, as the backend answering the
            query, or the nearest query that asked it, knows it.
        """
        asked = self.asked
        while asked is not None:
            if isinstance(asked.backend, SlotBackend):
                return asked.backend.answer_bodies(answer)
            asked = asked.asker
        return AnswerBodies(answer)

    def candidates(self, most_shown: int = 16) -> List[Any]:
        """
        :param most_shown: How many candidates are shown at most.
        :return: The values the query selected among as far as it looked, where it
            selects one variable, else nothing.
        """
        query = self.asked.query
        if not isinstance(query, Query):
            return []
        selected = query.selected_variable
        if not isinstance(selected, Variable):
            return []
        return selected._re_enterable_domain_generator_.materialized_values[:most_shown]

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
                for body in self.answer_bodies(answer).bodies()
            ],
            "frame": [
                str(body.name)
                for answer in answers
                for body in self.answer_bodies(answer).framed()
            ],
            "reasoning": (
                None if self.reasoning is None else self.reasoning.to_payload()
            ),
            "variables": [
                asdict(variable) for variable in QueryVariable.of_asked(self.asked)
            ],
            "enclosing": [asdict(statement) for statement in self.situation.enclosing],
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

    publish: Callable[[Dict[str, Any]], bool] | None = None
    """
    Shows the steps in the viewer and tells whether one showed them; without it, the
    steps are moved on through :meth:`advance` alone.
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
        # answering starts once the viewer has let the robot go on
        step.started = time.perf_counter()

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
            if not self._publish():
                # no viewer can move the robot on from a step it is not shown
                self.held = None
            self._change.wait_for(lambda: self.held is not step)

    def advance(self, held_at: HeldStep | None = None) -> None:
        with self._change:
            if held_at is not None and (
                self.held is None
                or HeldStep(self.held.number, self.held.moment) != held_at
            ):
                return
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

    def _publish(self) -> bool:
        """
        Show the steps in the viewer, if this run is shown in one.

        :return: Whether a viewer showed them, or that the steps are moved on without
            one.
        """
        return self.publish is None or self.publish(self.to_payload())

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
