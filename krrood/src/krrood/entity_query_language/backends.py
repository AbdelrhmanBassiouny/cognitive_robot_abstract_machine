from __future__ import annotations

import enum
from abc import abstractmethod, ABC
from dataclasses import dataclass, field
from functools import cached_property
from operator import eq
from types import EllipsisType, NoneType
from typing import Generic, Iterable, Type, TypeVar

import random_events.variable
from random_events.product_algebra import Event
from sqlalchemy.orm import sessionmaker
from typing_extensions import Any, ClassVar, Dict, List, Optional, Set, Tuple

from krrood import logger
from krrood.entity_query_language.verbalization.vocabulary.english import Directive

from krrood.entity_query_language.core.base_expressions import (
    Selectable,
    SymbolicExpression,
)
from krrood.entity_query_language.operators.causal import (
    Cause,
    CauseEffectVariables,
    ScoredIntervention,
)
from krrood.entity_query_language.operators.probabilistic_queries import (
    ProbabilisticQuery,
)
from krrood.entity_query_language.operators.aggregators import Average
from krrood.entity_query_language.core.mapped_variable import (
    Attribute,
    CanBehaveLikeAVariable,
)
from krrood.entity_query_language.core.variable import (
    InstantiatedVariable,
    Literal,
    Variable,
)
from krrood.entity_query_language.predicate import Relation, Triple
from krrood.entity_query_language.operators.comparator import Comparator
from krrood.entity_query_language.evaluable import Evaluable
from krrood.entity_query_language.exceptions import (
    BackendCannotEvaluateCause,
    BackendCannotResolveCondition,
    NoCauseVariablesForRanking,
    NoCausesEffectConditionForCause,
    NoSolutionFound,
    GenerativeBackendQueryIsNotUnderspecifiedVariable,
    SelectiveBackendCannotResolveEllipsisMatch,
    UnderspecifiedStatementInfeasibleForEntityQueryLanguageGeneration,
)
from krrood.entity_query_language.factories import (
    ConditionType,
    an,
    and_,
    entity,
    set_of,
    variable,
)
from krrood.entity_query_language.query.match import Match, AttributeMatch
from krrood.entity_query_language.query.query import Entity, Query
from krrood.entity_query_language.rdr.answer_vocabulary import AnswerName
from krrood.entity_query_language.rdr.expert import Expert
from krrood.entity_query_language.rdr.interface import (
    AnswerRequest,
    CaseContext,
    FunctionInterface,
)
from krrood.entity_query_language.rdr.serialization import NullModelSaver
from krrood.entity_query_language.rdr.single_class import EQLSingleClassRDR
from krrood.ormatic.eql_interface import eql_to_sql
from krrood.patterns.subclass_safe_generic import SubClassSafeGeneric

try:
    from probabilistic_model.probabilistic_circuit.causal.causal_circuit import (
        CausalCircuit,
    )
    from krrood.parametrization.exceptions import (
        DoRequiresCausalCircuitModel,
        MultipleEffectVariablesNotSupported,
    )
    from krrood.parametrization.model_registries import (
        ModelRegistry,
        FullyFactorizedRegistry,
    )
    from krrood.parametrization.parameterizer import (
        UnderspecifiedParameters,
        SelectedAttributesParameters,
    )
except ImportError as e:
    logger.debug(f"Couldn't import probabilistic model needed classes: {e}")
    CausalCircuit = NoneType
    DoRequiresCausalCircuitModel = NoneType
    MultipleEffectVariablesNotSupported = NoneType
    ModelRegistry = NoneType
    FullyFactorizedRegistry = NoneType
    SelectedAttributesParameters = NoneType
    UnderspecifiedParameters = NoneType

T = TypeVar("T")


@dataclass(frozen=True)
class AttributeEqualityToLiteral:
    """
    A condition fixing one attribute of the variable a query selects to a literal.

    This is the shape a backend translating a query into another engine's plan can
    usually act on directly, so it is read off a condition once here rather than by
    every such backend. An equality against anything but a literal is not one of these:
    the other side has to be evaluated before it names a value, which is the query's own
    work rather than the plan's.
    """

    attribute_name: str
    """
    The attribute the condition fixes, by the name the selected type gives it.
    """

    value: Any
    """
    The literal's value.
    """

    @classmethod
    def read_from(
        cls, condition: Evaluable, selection: Selectable
    ) -> Optional[AttributeEqualityToLiteral]:
        """
        Read a condition as an equality about the selected variable's own attribute.

        :param condition: The condition to read.
        :param selection: The variable the query selects.
        :return: The equality the condition states, or ``None`` when it states none --
            because it compares something else, compares by something other than
            equality, or compares against anything but a literal.
        """
        if not isinstance(condition, Comparator) or condition.operation is not eq:
            return None
        attribute, compared = condition._children_
        if not isinstance(attribute, Attribute) or not isinstance(compared, Literal):
            return None
        if attribute._chain_root_ is not selection:
            return None
        return cls(attribute._attribute_name_, compared._value_)


@dataclass
class QueryBackend(ABC):
    """
    Base class for all query backends.

    Query backends are objects that answer queries by different means.
    """

    opening_directive: ClassVar[Optional[Directive]] = None
    """
    The opening verb a verbalization uses when this backend evaluates the expression
    (``None`` keeps the query-type default).

    A backend declares its own performative so the verbalization layer never inspects
    concrete backend types.
    """

    raise_on_unresolvable_cause: bool = field(default=False, kw_only=True)
    """
    Whether to raise instead of warning when an expression contains a `Cause` (`cause`)
    intervention this backend cannot resolve causally.

    Defaults to ``False``: the `Cause` is then treated as an ordinary unspecified field
    (a warning is logged explaining why) rather than failing the query. Set ``True`` to
    fail loudly instead -- for example in tests that want to catch accidental `cause`
    misuse against a non-causal backend. Read only by :class:`SelectiveBackend` and
    :class:`EntityQueryLanguageGenerativeBackend`; :class:`ProbabilisticBackend` always
    raises when it cannot resolve a causal model, regardless of this flag.
    """

    @abstractmethod
    def evaluate(self, expression: Evaluable) -> Iterable[T]:
        """
        Generate answers that match the expression.

        :param expression: The expression to generate answers for.
        :return: An iterable of answers.
        """

    def _warn_or_raise_on_unresolved_cause_(self, expression: Evaluable) -> None:
        """
        Warn (or, if :attr:`raise_on_unresolvable_cause` is set, raise) when
        *expression* is a :class:`~krrood.entity_query_language.query.match.Match`
        containing a `Cause` this backend has no causal graph to resolve.

        :param expression: The expression about to be evaluated.
        """
        if not (isinstance(expression, Match) and expression._has_cause_attributes_):
            return
        if self.raise_on_unresolvable_cause:
            raise BackendCannotEvaluateCause(expression, backend_type=type(self))
        logger.warning(BackendCannotEvaluateCause(expression, backend_type=type(self)))


@dataclass
class SelectiveBackend(QueryBackend, ABC):
    """
    Selective backends are backends that select elements from existing data.

    These can take any query as input.
    """

    opening_directive: ClassVar[Optional[Directive]] = Directive.FIND
    """
    Selecting from existing data reads as *"Find …"*.
    """

    def evaluate(self, expression: Evaluable) -> Iterable[T]:
        if isinstance(expression, Match) and expression._has_ellipsis_attributes_:
            raise SelectiveBackendCannotResolveEllipsisMatch(expression)
        self._warn_or_raise_on_unresolved_cause_(expression)
        yield from self._evaluate(expression)

    @abstractmethod
    def _evaluate(self, expression: Evaluable) -> Iterable[T]: ...


@dataclass
class GenerativeBackend(QueryBackend, ABC):
    """
    Generative backends are backends that generate new elements.

    Generative backends have to take match expressions as input, since they need to construct new objects, and currently
    {py:class}`~krrood.entity_query_language.query.match.Match` is the only way to do so.
    """

    opening_directive: ClassVar[Optional[Directive]] = Directive.GENERATE
    """
    Generating new elements reads as *"Generate …"*.
    """

    def evaluate(self, expression: Evaluable) -> Iterable[T]:
        if not isinstance(expression, Match):
            raise GenerativeBackendQueryIsNotUnderspecifiedVariable(expression)
        yield from self._evaluate(expression)

    @abstractmethod
    def _evaluate(self, expression: Match[T]) -> Iterable[T]: ...


# %% relations a statement asserts about the thing it looks for

# A relation is stated the way anything partial is stated in the entity query language:
# a match over the relation's own class, holding whichever operands the statement
# already knows and leaving the thing sought unstated. What follows is how such a
# statement is read out of a query and asserted about something once it is found.


def relation_asserted_about(stated: Match[Relation], subject: Any) -> Relation:
    """
    A relation stated about the thing sought, asserted about one thing.

    This is how a relation stated before anything was found is asked of what was found
    afterwards, and how one stated about nothing in particular is written into a
    statement about a variable.

    :param stated: The relation as stated, with nothing standing in its subject's place.
    :param subject: What stands where the thing sought would.
    """
    return stated.stating(**{stated.type.subject_name(): subject}).construct_instance()


def object_stated_by(stated: Match[Triple]) -> Optional[Any]:
    """
    What a relation stated about the thing sought relates it to.

    :param stated: The relation as stated, of the kind that relates two things.
    :return: The thing on the other side of it, or ``None`` where the statement leaves
        that side open -- *standing on something* rather than on anything named.
    """
    return stated.kwargs.get(stated.type.object_name())


def relations_stated_in(
    statement: Match, described_things: Optional[Dict[Any, Any]] = None
) -> List[Match[Relation]]:
    """
    Every relation a statement asserts about the thing it is looking for, in the order
    it states them.

    :param statement: The statement to read.
    :param described_things: What the statement describes rather than hands over, each
        already resolved to the thing that answers its description.
    """
    read = (
        relation_stated_by(condition, statement.variable, described_things)
        for condition in statement._where_conditions_
    )
    return [relation for relation in read if relation is not None]


def relation_stated_by(
    condition: Evaluable,
    selection: Selectable,
    described_things: Optional[Dict[Any, Any]] = None,
) -> Optional[Match[Relation]]:
    """
    Read a condition as a relation asserted about the thing being looked for.

    :param condition: The condition to read.
    :param selection: The thing the statement is looking for.
    :param described_things: What the statement describes rather than hands over, each
        already resolved to the thing that answers its description, so a relation stated
        about one of them is read as a relation to that thing.
    :return: The relation the condition asserts, as a match over the relation's own
        class with the thing sought left unstated, or ``None`` when it asserts none --
        because it is not a relation, because it is asserted about something else, or
        because something it relates the selection to is not known yet.
    """
    relation_type = relation_type_stated_by(condition, selection)
    if relation_type is None:
        return None
    operands = {
        name: _thing_stood_for(value, described_things or {})
        for name, value in condition._kwargs_.items()
        if name != relation_type.subject_name()
    }
    if any(isinstance(value, SymbolicExpression) for value in operands.values()):
        return None
    return an(relation_type)(**operands)


def relation_type_stated_by(
    condition: Evaluable, selection: Selectable
) -> Optional[Type[Relation]]:
    """
    :param condition: The condition to read.
    :param selection: The thing the statement is looking for.
    :return: The kind of relation the condition asserts about that thing, or ``None``
        when it asserts none about it -- whether or not everything it relates that thing
        to is known yet.
    """
    if not isinstance(condition, InstantiatedVariable):
        return None
    relation_type = condition._type_
    if not isinstance(relation_type, type) or not issubclass(relation_type, Relation):
        return None
    if condition._kwargs_.get(relation_type.subject_name()) is not selection:
        return None
    return relation_type


def _thing_stood_for(operand: Any, described_things: Dict[Any, Any]) -> Any:
    """
    :param operand: What the statement puts in one of the relation's places.
    :param described_things: What the statement describes rather than hands over.
    :return: The thing that operand stands for, or the operand itself where it stands
        for nothing the statement described. Read by identity rather than by equality,
        since a thing the world holds need be neither hashable nor comparable to a
        variable.
    """
    for variable_, thing in described_things.items():
        if operand is variable_ or _selects(operand, variable_):
            return thing
    return operand


def _selects(operand: Any, variable_: Any) -> bool:
    """
    :param operand: What the statement puts in one of the relation's places.
    :param variable_: The variable standing for a thing the statement describes.
    :return: Whether that operand is a statement of its own selecting that variable,
        which is the other way a statement puts a thing it describes in a relation's
        place.
    """
    return isinstance(operand, Query) and any(
        selected is variable_ for selected in operand._selected_variables_
    )

class Look(ABC):
    """
    One question put to perception: what is being sought, and the situation it is sought
    in.

    A detector states the looks it can answer as a condition over one of these, and a
    rule tree binds one to decide which detector answers it, so a look is where
    everything either of them may read is said -- what is sought, what the world states
    about it, and what the sensor offers. Which of those a look carries differs with the
    family of detectors asked, so each family states its own look and this declares
    nothing beyond being one.
    """


@dataclass(frozen=True)
class LookRequest(Generic[T], Look):
    """
    What a statement asks a look for.

    A look is not free, and whoever makes one usually wants less than everything the
    world holds. This is the part of a statement a look can act on: the kind of thing
    asked for, whichever of its attributes the statement fixes outright, and whatever
    the statement says it stands in relation to.
    """

    type_: Type[T]
    """
    The kind of thing asked for.
    """

    stated_attributes: List[AttributeEqualityToLiteral] = field(default_factory=list)
    """
    Every attribute the statement fixes to a literal.

    Each is a narrowing and never a promise: a look that cannot act on one may answer
    with more than was asked for, so every one of them is checked again over what came
    back.
    """

    stated_relations: List[Match[Relation]] = field(default_factory=list)
    """
    Every relation the statement asserts between the thing sought and something known.

    A narrowing on the same terms as an attribute, said in the world's own vocabulary
    rather than by naming a field.
    """

    described_things: Dict[Any, Any] = field(default_factory=dict)
    """
    Everything the statement describes rather than hands over, each resolved to the one
    thing that answers its description, keyed by the variable standing for it.

    A statement can say what it is looking for by relating it to something it describes
    -- the surface the world calls the board's lid, the hole the cube fits -- and those
    descriptions are answered out of the world the statement gave them before any look
    is taken, so what the relation says is a relation to something concrete.
    """

    def related_by(self, relation_type: Type[Triple]) -> Optional[Any]:
        """
        :param relation_type: The relation to read.
        :return: What the statement says the thing sought stands in that relation to, or
            ``None`` when it asserts no such relation, or asserts one that names nothing
            on the other side.
        """
        stated = self.stated_relations_of(relation_type)
        if not stated:
            return None
        return object_stated_by(stated[0])

    def stated_relations_of(
        self, relation_type: Type[Relation]
    ) -> List[Match[Relation]]:
        """
        :param relation_type: The kind of relation to read.
        :return: Every relation of that kind the statement asserts about the thing
            sought, in the order it states them.
        """
        return [
            stated
            for stated in self.stated_relations
            if issubclass(stated.type, relation_type)
        ]

    def admits(self, instance: Any) -> bool:
        """
        Whether an instance is of the kind this look was asked for.

        A look may answer with more kinds than were asked for, and the kind a variable
        declares is not one of the conditions a statement re-checks, so whoever asked
        applies this to what came back.

        :param instance: One thing the look found.
        """
        return isinstance(instance, self.type_)

    def value_stated_for(self, attribute_name: str) -> Optional[Any]:
        """
        :param attribute_name: The attribute to read.
        :return: The value the statement fixes that attribute to, or ``None`` when it
            leaves it open.
        """
        for stated in self.stated_attributes:
            if stated.attribute_name == attribute_name:
                return stated.value
        return None


LookT = TypeVar("LookT", bound=Look)


@dataclass(eq=False)
class PerceptionDetector(Generic[LookT], SubClassSafeGeneric, ABC):
    """
    Something that answers a look, and states for itself which looks it can answer.

    What a detector can answer is its own statement rather than a caller's knowledge of
    which detector is which, so a detector is never chosen for a look it declared it
    cannot answer, and one added later brings its own condition with it.

    The kind of look a detector answers is the type parameter it binds, so what its
    conditions may read is part of its signature: bind the situation a look is decided
    from -- what is being sought, what the world says about it, what the sensor
    provides -- and state conditions over that.
    """

    __hash__ = object.__hash__
    """
    A detector is the one it is: two configured alike are not the same detector, and a
    rule concludes the detector itself rather than a name for one, so it is compared and
    hashed by identity.

    Restated here because the generic base compares by value, which unsets hashing.
    """

    @abstractmethod
    def capability(self, look: LookT) -> ConditionType:
        """
        The looks this detector can answer, as a condition over a look.

        Written as an entity query language condition rather than as a predicate on a
        value, so the same statement both decides one look and becomes a rule in the
        tree that chooses among the detectors that can answer it.

        :param look: The variable to state the condition over, of the kind this detector
            binds.
        :return: The condition, which holds exactly for the looks this detector answers.
        """

    @classmethod
    def look_type(cls) -> Type[LookT]:
        """
        The kind of look this detector answers, read off the type parameter it binds.
        """
        return cls.get_generic_type_parameters()[0]

    @cached_property
    def stated_look(self) -> LookT:
        """
        The variable this detector states its own capability over.

        The statement is made once and one look at a time is bound to this to ask it.
        """
        return variable(self.look_type(), domain=[])

    @cached_property
    def answerable_looks(self) -> Query:
        """
        The looks this detector can answer, stated once over :attr:`stated_look`.
        """
        return an(entity(self.stated_look).where(self.capability(self.stated_look)))

    def asked_about(self, look: LookT) -> Query:
        """
        This detector's own capability, asked about one look.

        Evaluating the query answers with the look where this detector declares it can
        answer it and with nothing where it cannot, so whoever asks decides what to make
        of it -- a verdict, the looks of a batch this detector takes, a drawing of the
        condition, or a statement to narrow further.

        .. note:: The query is the detector's own standing statement rather than a copy
            of it, so changing it changes what the detector declares about itself.

        :param look: The look to put to it.
        """
        self.stated_look._update_domain_([look])
        return self.answerable_looks


@dataclass
class DetectorChoice(Generic[LookT], SubClassSafeGeneric, ABC):
    """
    Which detector of one family answers a look, decided by a tree of rules.

    Every family faces the same question twice over. What a detector can answer at all
    is its own
    :meth:`~krrood.entity_query_language.backends.PerceptionDetector.capability`, so it
    is never chosen for a look it declared it cannot answer. Which of the ones that can
    should is what the rules decide, and that is knowledge about when a detector is
    worth its cost rather than part of what it says about itself.

    The rules a family starts with are stated outright
    (:meth:`rules_stated_at_the_start`); a look they get wrong is corrected by
    :meth:`add_rule`, which asks each detector for its own condition and narrows it by
    :meth:`situation_answered_by`.
    """

    rules: EQLSingleClassRDR = field(init=False, repr=False, compare=False)
    """
    The rules themselves, as one tree that outlives the looks it decides.

    Nothing is persisted when a rule is added: a rule concludes the detector itself
    rather than a name for one, and the engine writes a model file as Python source,
    which can spell an enum member or a number but not a collaborator. The rules are
    recovered by stating them again from the detectors, which is what building this
    does.
    """

    expert: Expert = field(init=False, repr=False, compare=False)
    """
    Asked for a new rule's condition, which it reads off
    :meth:`state_the_condition_this_rule_needs`.
    """

    def __post_init__(self) -> None:
        """
        Build the tree from the family's own statement and state the rules it starts
        with.
        """
        self.expert = Expert(
            interface=FunctionInterface(
                answer_function=self.state_the_condition_this_rule_needs
            )
        )
        self.rules = EQLSingleClassRDR.from_underspecified(
            self.underspecified_look(), model_saver=NullModelSaver()
        )
        self.rules.state_rules(self.rules_stated_at_the_start())

    @abstractmethod
    def underspecified_look(self) -> Match:
        """
        The statement the rules are built from: a look of this family whose detector is
        left open, for example ``a(TargetOnSurface)(detector=...)``.

        What is described and what is to be worked out are read off this, so neither is
        named again anywhere else.
        """

    @abstractmethod
    def rules_stated_at_the_start(self) -> Entity:
        """
        What this family already knows about which detector answers which look, written
        as the rule tree it is.

        Each condition is stated over :attr:`look` and concludes on
        :attr:`chosen_detector`, and the first alternative whose condition holds is the
        one that answers.
        """

    @abstractmethod
    def nothing_answers(self, look: LookT) -> Exception:
        """
        The family's own account of a look no rule reaches, which is raised rather than
        answering with nothing.

        :param look: The look nothing answered.
        """

    @property
    def look(self) -> LookT:
        """
        The variable every rule of this family is stated over.
        """
        return self.rules.case_variable

    @property
    def chosen_detector(self) -> CanBehaveLikeAVariable:
        """
        The attribute every rule of this family concludes on.
        """
        return self.rules.conclusion_variable

    def state_the_condition_this_rule_needs(
        self, context: CaseContext, requests: List[AnswerRequest]
    ) -> Dict[AnswerName, Any]:
        """
        Answer the engine's question about a new rule with what the detector says it can
        answer, narrowed by the situation these rules choose it in.

        :param context: The look being fitted, and the detector it is fitted to.
        :param requests: The answers asked for, which this reads nothing from.
        :return: The conditions answer.
        """
        capability = context.target_conclusion.capability(context.case_variable)
        situation = self.situation_answered_by(
            context.target_conclusion, context.case_variable, context.case_instance
        )
        if situation is None:
            return {AnswerName.CONDITIONS: capability}
        return {AnswerName.CONDITIONS: and_(situation, capability)}

    def situation_answered_by(
        self,
        detector: PerceptionDetector[LookT],
        look: LookT,
        example: LookT,
    ) -> Optional[ConditionType]:
        """
        What these rules know about when a detector is worth running, over and above
        what it says it can answer.

        Nothing, unless a family says otherwise: a capability that already tells the
        detectors apart leaves the rules nothing to add.

        :param detector: The detector a rule is being stated for.
        :param look: The variable the condition is stated over.
        :param example: The look the rule is being stated from.
        :return: The situation, or ``None`` where the rules hold none.
        """
        return None

    def add_rule(self, look: LookT, detector: PerceptionDetector[LookT]) -> None:
        """
        State a kind of look the rules do not yet cover.

        The rule joins the tree already in use, so such a look is answered by *detector*
        from the next call onwards without any of the rules already stated being
        rewritten. That is what a tree of rules is for, and it is the path an expert
        correcting a choice takes.

        :param look: The kind of look that was not covered.
        :param detector: The detector that answers it.
        """
        self.rules.fit_case(look, detector, self.expert)

    def detector_for(self, look: LookT) -> PerceptionDetector[LookT]:
        """
        The detector that answers one look.

        :param look: The look to decide.
        :raises Exception: The family's own :meth:`nothing_answers`, if no rule reaches
            this look.
        """
        concluded = self.rules.classify(look)
        if concluded is ...:
            raise self.nothing_answers(look)
        return concluded

    def render_tree(self, look: LookT) -> str:
        """
        The rules as a tree, with the rule that answers one look marked out.

        :param look: The look to read the tree for.
        """
        return self.rules.render_tree(look, use_color=False)


@dataclass
class PerceptionBackend(GenerativeBackend, ABC):
    """
    Answers a statement about the world by going and looking at it.

    Generative, because what a look reports is not in any domain the statement was
    handed: an object nothing has observed yet has no instance to select, and the look
    is what brings one into existence. Asking where a thing already believed in stands
    is the same act with its pose left open.

    What the look can act on narrows it, and what it cannot is checked over what came
    back, so no part of a statement is ever quietly dropped. The two halves cannot
    disagree, because a narrowing is checked again afterwards -- it is an economy, never
    the thing that makes the answer right.
    """

    opening_directive: ClassVar[Optional[Directive]] = Directive.LOOK_FOR
    """
    Going to look reads as *"Look for …"*, which is what tells it apart from recalling
    something already recorded.
    """

    narrowing_relations: ClassVar[Tuple[Type[Relation], ...]] = ()
    """
    The relations a look of this kind can narrow itself by.

    A relation named here is answered by the look rather than by evaluating it, because
    what a look reports is a sighting of a thing and not the thing itself, so the
    relation's own implementation has nothing to evaluate against. Naming it is
    therefore a promise to check it over the answer too, in :meth:`relations_hold`.
    """

    def _evaluate(self, expression: Match[T]) -> Iterable[T]:
        """
        Look for what the statement asks about, then check what came back against it.

        :param expression: The statement to answer.
        :raises BackendCannotResolveCondition: If a condition constrains anything other
            than the thing being looked for.
        """
        request = self.read_request(expression)
        self._hold_each_description_to_its_answer(request)
        found = [
            instance
            for instance in self.look(request)
            if request.admits(instance) and self.relations_hold(instance, request)
        ]
        expression.variable._update_domain_(found)
        kept = list(self._check_what_was_found(expression, request))
        self.discard([instance for instance in found if instance not in kept])
        yield from kept

    @staticmethod
    def _hold_each_description_to_its_answer(request: LookRequest[T]) -> None:
        """
        Leave each thing the statement describes standing for the one thing that answers
        its description.

        A relation to something described is checked over what the look reported, and a
        variable still ranging over everything it could have meant would let the check
        pass against something the statement ruled out.

        :param request: What the statement asks a look for.
        """
        for variable_, thing in request.described_things.items():
            variable_._update_domain_([thing])

    def discard(self, instances: List[T]) -> None:
        """
        Let go of what the statement rejected.

        A backend that brought what it found into a world of its own is left holding
        exactly the answer; one that brought it nowhere has nothing to let go of.

        :param instances: Everything the look reported that the statement rejected.
        """

    def relations_hold(self, instance: T, request: LookRequest[T]) -> bool:
        """
        Whether a found instance stands in the relations this look narrows itself by.

        A narrowing is never a promise -- a look already taken cannot be narrowed at all
        -- so what :attr:`narrowing_relations` names is checked here over what came
        back, which is what keeps the answer right whether or not the search honoured
        it.

        :param instance: One thing the look found.
        :param request: What the look was asked for.
        """
        return True

    @abstractmethod
    def look(self, request: LookRequest[T]) -> Iterable[T]:
        """
        Look at the world, and report what is there as instances.

        :param request: What the statement asks a look for. Acting on it is an economy
            rather than an obligation, since whatever it does not narrow is checked
            afterwards anyway.
        :return: Everything the look found.
        """

    @classmethod
    def read_request(cls, expression: Match[T]) -> LookRequest[T]:
        """
        Read what a statement asks a look for.

        :param expression: The statement to read.
        :return: The kind of thing it asks for, the attributes it fixes outright, and
            the relations it asserts about it. An attribute left as ``...`` fixes
            nothing: the statement is saying the look must supply it.
        """
        described_things = cls.things_described_by(expression)
        return LookRequest(
            type_=expression.variable._type_,
            stated_attributes=[
                AttributeEqualityToLiteral(
                    attribute_match.attribute_name, attribute_match.assigned_value
                )
                for attribute_match in expression.matches_with_variables
                if not isinstance(attribute_match.assigned_value, EllipsisType)
            ],
            stated_relations=relations_stated_in(expression, described_things),
            described_things=described_things,
        )

    @classmethod
    def things_described_by(cls, expression: Match[T]) -> Dict[Any, Any]:
        """
        Answer the descriptions a statement gives of things other than the one it is
        looking for.

        A statement can name what it wants by relating it to something it describes
        rather than hands over -- the surface the world calls the board's lid, the hole
        the cube fits. Nothing is looked for to answer those: they are things the world
        already holds, so the statement's own domain for each answers it, and the look
        is then narrowed by a relation to something concrete.

        :param expression: The statement to read.
        :return: The one thing answering each description, keyed by the variable
            standing for it. A description no single thing answers is left out, so the
            condition stating it stays one this backend cannot resolve.
        """
        described_things = {}
        for variable_, description in cls._descriptions_in(expression).items():
            answers = list(description._evaluate_natively_())
            if len(answers) == 1:
                described_things[variable_] = answers[0]
        return described_things

    @classmethod
    def _descriptions_in(cls, expression: Match[T]) -> Dict[Any, Evaluable]:
        """
        What the statement says about each thing other than the one it is looking for.

        Such a description is written one of two ways: as conditions stated beside the
        relation that mentions the thing, or as a statement of its own handed to that
        relation in the thing's place. Both say the same, so both are read as the query
        answering the description out of the domain the statement gave it.

        :param expression: The statement to read.
        :return: The query answering each description, keyed by the variable standing
            for the thing described. A variable the statement constrains but describes
            neither way is left out.
        """
        descriptions = {
            selected: description
            for description in cls._statements_handed_to(expression)
            for selected in description._selected_variables_
        }
        for variable_ in cls._variables_described_by(expression):
            about_it = [
                condition
                for condition in expression._where_conditions_
                if condition._constrained_variables_ == {variable_}
            ]
            if not about_it or variable_ in descriptions:
                continue
            descriptions[variable_] = an(entity(variable_)).where(*about_it)
        return descriptions

    @staticmethod
    def _statements_handed_to(expression: Match[T]) -> List[Query]:
        """
        :param expression: The statement to read.
        :return: Every statement of its own the conditions hand over in the place of a
            thing they mention.
        """
        return [
            reached
            for condition in expression._where_conditions_
            for reached in condition._descendants_
            if isinstance(reached, Query)
        ]

    @staticmethod
    def _variables_described_by(expression: Match[T]) -> Set[Any]:
        """
        :param expression: The statement to read.
        :return: Every variable the statement constrains other than the one it is
            looking for.
        """
        constrained = set()
        for condition in expression._where_conditions_:
            constrained |= condition._constrained_variables_
        return constrained - {expression.variable}

    def _check_what_was_found(
        self, expression: Match[T], request: LookRequest[T]
    ) -> Iterable[T]:
        """
        Keep only what the statement actually asked for, out of what the look reported.

        The attributes the statement leaves as ``...`` are the ones the look was there
        to supply, so they are not checked; everything else it states is. A relation
        this look narrows itself by is checked by :meth:`relations_hold` instead, since
        the look reports sightings rather than the things the relation is written over.

        :param expression: The statement being answered.
        :param request: What the look was asked for.
        :raises BackendCannotResolveCondition: If a ``where`` condition constrains any
            variable other than the thing being looked for, which a look can neither
            search for nor check afterwards -- unless it is a description this backend
            answered out of the world, or a relation to something so described, both of
            which are settled before the look.
        :return: Every found instance the statement admits.
        """
        described = set(request.described_things)
        remaining_conditions = []
        for condition in expression._where_conditions_:
            if self._look_answers(
                condition, expression.variable, request.described_things
            ):
                continue
            if not condition._constrained_variables_ - described:
                continue
            if condition._constrained_variables_ - {expression.variable} - described:
                raise BackendCannotResolveCondition(condition, type(self))
            remaining_conditions.append(condition)
        stated = [
            getattr(expression.variable, attribute.attribute_name) == attribute.value
            for attribute in request.stated_attributes
        ]
        found = entity(expression.variable)._quantify_(expression._quantifier_type_)
        if stated or remaining_conditions:
            found = found.where(*stated, *remaining_conditions)
        yield from found._evaluate_natively_()

    def _look_answers(
        self,
        condition: Evaluable,
        selection: Selectable,
        described_things: Optional[Dict[Any, Any]] = None,
    ) -> bool:
        """
        Whether a condition asserts one of the relations this look narrows itself by.

        :param condition: The condition to read.
        :param selection: The thing the statement is looking for.
        :param described_things: What the statement describes rather than hands over.
        """
        stated = relation_stated_by(condition, selection, described_things)
        return stated is not None and issubclass(stated.type, self.narrowing_relations)


@dataclass
class SQLAlchemyBackend(SelectiveBackend):
    """
    A backend that selects elements from a database that is available via SQLAlchemy.
    """

    session_maker: sessionmaker
    """
    The session maker used for the database interactions.
    """

    def _evaluate(self, expression: Query) -> Iterable:
        session = self.session_maker()
        translator = eql_to_sql(expression, session)
        yield from translator.evaluate()


@dataclass
class EntityQueryLanguageBackend(SelectiveBackend):
    """
    A backend that selects elements in this python process.

    This is just ordinary EQL: each expression evaluates itself natively (queries and matches both select over their domains).
    Constructing new instances is the job of a :class:`GenerativeBackend`.
    """

    def _evaluate(self, expression: Evaluable) -> Iterable:
        yield from expression._evaluate_natively_()


@dataclass
class EntityQueryLanguageGenerativeBackend(GenerativeBackend):
    """
    A generative backend that constructs new instances deterministically: it treats a
    match's unspecified leaves as variables, enumerates every combination over their
    (discrete) domains, constructs an instance per combination via the type's
    constructor, and keeps those that satisfy the match's ``where`` conditions.
    """

    def _evaluate(self, expression: Match[T]) -> Iterable[T]:
        self._warn_or_raise_on_unresolved_cause_(expression)
        variables: Dict[str, Variable] = {}
        for attribute_match in expression._matches_with_variables_:
            self._check_attribute_match_is_suitable_for_generation(attribute_match)
            variables[attribute_match.name_from_variable_access_path] = (
                self._convert_attribute_match_to_variable(attribute_match)
            )

        expression._variable_._update_domain_(
            self._generate_raw_results(expression, variables)
        )

        filtered_results = entity(expression._variable_)._quantify_(
            expression._quantifier_type_
        )
        if expression._where_conditions_:
            filtered_results = filtered_results.where(*expression._where_conditions_)
        yield from filtered_results._evaluate_natively_()

    @staticmethod
    def _check_attribute_match_is_suitable_for_generation(
        attribute_match: AttributeMatch,
    ) -> None:
        """
        Raise if an assignment in the match cannot be used to generate solutions.

        :param attribute_match: The attribute match to check.
        :raises UnderspecifiedStatementInfeasibleForEntityQueryLanguageGeneration: If a
            non-enum leaf is left fully unspecified (``...`` or ``cause``), which
            deterministic generation cannot enumerate (use the
            :class:`ProbabilisticBackend` instead).
        """
        if isinstance(
            attribute_match.assigned_value, (type(Ellipsis), Cause)
        ) and not issubclass(attribute_match.assigned_variable._type_, enum.Enum):
            raise UnderspecifiedStatementInfeasibleForEntityQueryLanguageGeneration(
                attribute_match
            )

    @staticmethod
    def _convert_attribute_match_to_variable(
        attribute_match: AttributeMatch,
    ) -> Selectable:
        """
        Convert an attribute match into a variable to enumerate, handling ellipsis (and,
        identically, ``cause``) assignments for enum fields and concrete values.

        :param attribute_match: The attribute match to convert.
        :return: A variable (or symbolic expression) representing the attribute match.
        """
        if isinstance(
            attribute_match.assigned_value, (type(Ellipsis), Cause)
        ) and issubclass(attribute_match.assigned_variable._type_, enum.Enum):
            return variable(
                attribute_match.assigned_variable._type_,
                list(attribute_match.assigned_variable._type_),
            )
        if isinstance(attribute_match.assigned_value, SymbolicExpression):
            return attribute_match.assigned_value
        return variable(
            type(attribute_match.assigned_value),
            [attribute_match.assigned_value],
        )

    def _generate_raw_results(
        self, expression: Match[T], variables: Dict[str, Variable]
    ) -> Iterable[T]:
        """
        Construct instances from the given match and enumerable variables.

        :param expression: The match expression to construct instances from.
        :param variables: The variables to enumerate, keyed by access- path name.
        :return: A generator yielding an instance per variable combination.
        """
        all_combinations = set_of(*variables.values())
        for combination in all_combinations._evaluate_natively_():
            for variable_name, value in zip(variables, combination.values()):
                mapped_variable = expression._get_mapped_variable_by_name(variable_name)
                mapped_variable._value_ = value
            expression._update_kwargs_from_literal_values()
            yield expression.construct_instance()


@dataclass
class ProbabilisticBackend(GenerativeBackend):
    """
    A backend that generates elements from a tractable probabilistic model using a model
    registry.
    """

    model_registry: ModelRegistry = field(default_factory=FullyFactorizedRegistry)
    """
    A model registry that can be used to resolve match statements to probabilistic
    models.
    """

    number_of_samples: int = field(kw_only=True, default=50)
    """
    The number of samples to generate.

    This is only used if the query does not specify a limit.
    """

    def evaluate(self, expression: Evaluable) -> Iterable[T]:
        if isinstance(expression, ProbabilisticQuery):
            yield expression._resolve_(self.model_registry)
            return
        bare_average = self._bare_average_selection(expression)
        if bare_average is not None:
            yield self._resolve_average(bare_average)
            return
        yield from super().evaluate(expression)

    @staticmethod
    def _bare_average_selection(expression: Evaluable) -> Optional[Average]:
        """
        :param expression: The expression being evaluated.
        :return: The :class:`~krrood.entity_query_language.operators.aggregators.Average`
            ``expression`` selects, if it is an otherwise-untouched
            :class:`~krrood.entity_query_language.query.query.Entity` selecting one
            (i.e. what ``average(x.A).evaluate(...)`` builds -- see
            :meth:`~krrood.entity_query_language.operators.aggregators.Aggregator.evaluate`)
            over an attribute chain, so it can be answered in closed form. ``None``
            otherwise, e.g. when the average is grouped, filtered, or over something
            other than an attribute.
        """
        if not isinstance(expression, Entity):
            return None
        aggregator = expression.selected_aggregator
        if not isinstance(aggregator, Average):
            return None
        if aggregator._leaf_attribute_ is None:
            return None
        if aggregator._distinct_:
            # native evaluation deduplicates values before averaging; the closed-form
            # expectation has no notion of that, so it must not silently stand in
            return None
        if any(
            builder is not None
            for builder in (
                expression._where_builder_,
                expression._grouped_by_builder_,
                expression._having_builder_,
                expression._ordered_by_builder_,
            )
        ):
            return None
        return aggregator

    def _resolve_average(self, average: Average) -> float:
        """
        Resolve a bare ``average(...)`` selection to the exact expectation of its
        attribute, via ``ProbabilisticModel.expectation``, instead of sampling and
        averaging rows.

        :param average: The average aggregator to resolve.
        :return: The expectation of the averaged attribute.
        """
        attribute = average._leaf_attribute_
        parameters = SelectedAttributesParameters((attribute,))
        model = self.model_registry.get_model(parameters)
        [random_event_variable] = parameters.variables.values()
        return model.expectation((random_event_variable,))[random_event_variable]

    def _evaluate(self, expression: Match[T]) -> Iterable[T]:

        # generate parameters from example instance values
        parameters = UnderspecifiedParameters(expression)

        model = self.model_registry.get_model(parameters)

        if parameters.search_cause_variables:
            cause_effect = self._resolve_cause_and_effect_variables(
                parameters, expression
            )
            if not isinstance(model, CausalCircuit):
                raise DoRequiresCausalCircuitModel(model)
            # search every candidate cause independently and keep the primary one's
            # already effect-truncated, already region-narrowed circuit -- see
            # _resolve_primary_intervention for why this needs no joint intervention
            primary = self._resolve_primary_intervention(
                model,
                cause_effect.cause_variables,
                cause_effect.effect_variable,
                parameters.truncation_assignments_from_where_conditions,
                expression,
                cause_effect.confounder_variables,
            )
            truncated = parameters.apply_krrood_variable_truncation(
                primary.narrowed_circuit
            )
        else:
            # apply literal-assignment conditions, then where-conditions, then
            # krrood-variable-assignment truncations -- see
            # UnderspecifiedParameters.resolve_conditioned_and_truncated_model, which
            # Distribution._resolve_ also reuses to answer a distribution(...) query
            # with exactly this same sequence, without the sampling step below.
            truncated = parameters.resolve_conditioned_and_truncated_model(model)

        if truncated is None:
            raise NoSolutionFound(expression._get_expression_())

        number_of_samples = (
            expression._get_expression_()._limit_ or self.number_of_samples
        )

        # sample and sort by log likelihood
        samples = truncated.sample(number_of_samples)
        log_likelihoods = truncated.log_likelihood(samples)
        samples = samples[log_likelihoods.argsort()[::-1]]

        # create new objects with the values from the samples
        for sample in samples:
            instance = parameters.construct_instance_from_model_sample(
                truncated.variables, sample
            )
            yield instance

    @staticmethod
    def _resolve_cause_and_effect_variables(
        parameters: UnderspecifiedParameters, expression: Match[T]
    ) -> CauseEffectVariables:
        """
        Resolve the cause candidates and the single effect variable a ``cause`` search
        optimizes for.

        Any number of cause candidates is fine -- each is searched independently (see
        :meth:`_resolve_primary_intervention`). Exactly one effect variable is required:
        :meth:`~probabilistic_model.probabilistic_circuit.causal.causal_circuit.CausalCircuit.backdoor_adjustment`
        has no multi-effect form to route several through.

        :param parameters: The parameters extracted from *expression*.
        :param expression: The match being evaluated.
        :raises NoCausesEffectConditionForCause: If no ``causes_effect(...)`` condition
            declared an effect.
        :raises MultipleEffectVariablesNotSupported: If more than one effect variable
            was found.
        :return: The resolved cause candidates and effect variable.
        """
        if not parameters.effect_variables_from_causes_effect:
            raise NoCausesEffectConditionForCause(expression._get_expression_())
        if len(parameters.effect_variables_from_causes_effect) > 1:
            raise MultipleEffectVariablesNotSupported(
                parameters.effect_variables_from_causes_effect
            )
        [effect_variable] = parameters.effect_variables_from_causes_effect
        return CauseEffectVariables(
            parameters.search_cause_variables,
            effect_variable,
            parameters.search_confounder_variables,
        )

    @classmethod
    def _resolve_primary_intervention(
        cls,
        model: CausalCircuit,
        cause_variables: List[random_events.variable.Variable],
        effect_variable: random_events.variable.Variable,
        effect_truncation_event: Optional[Event],
        expression: Match[T],
        confounder_variables: Iterable[random_events.variable.Variable] = (),
    ) -> ScoredIntervention:
        """
        Search every candidate cause variable independently for the region whose
        intervention best explains the effect, and return the highest-scoring candidate
        as the primary cause.

        This is the same per-candidate approach
        :meth:`~probabilistic_model.probabilistic_circuit.causal.causal_circuit.CausalCircuit.diagnose_failure`
        already uses to identify a ``primary_cause_variable`` -- trying one candidate at
        a time needs no joint, multi-variable intervention, which
        ``backdoor_adjustment`` does not support. See :meth:`rank_causes` for every
        candidate's score, not just this one.

        :param model: The causal circuit to search.
        :param cause_variables: The candidate cause variables, one or more.
        :param effect_variable: The declared effect variable.
        :param effect_truncation_event: The event the declared effect condition
            translates to, used to narrow each candidate's interventional joint to the
            effect before ranking its regions.
        :param expression: The match being evaluated, for error reporting.
        :param confounder_variables: Variables marked ``confounder`` in the query,
            passed through to ``backdoor_adjustment`` as its adjustment set.
        :raises NoSolutionFound: If no candidate has a region with positive probability.
        :return: The highest-scoring candidate.
        """
        scored_interventions = cls._score_all_interventions(
            model,
            cause_variables,
            effect_variable,
            effect_truncation_event,
            confounder_variables,
        )
        if not scored_interventions:
            raise NoSolutionFound(expression._get_expression_())
        return scored_interventions[0]

    @classmethod
    def _score_all_interventions(
        cls,
        model: CausalCircuit,
        cause_variables: List[random_events.variable.Variable],
        effect_variable: random_events.variable.Variable,
        effect_truncation_event: Optional[Event],
        confounder_variables: Iterable[random_events.variable.Variable] = (),
    ) -> List[ScoredIntervention]:
        """
        Score every candidate cause variable independently for the region whose
        intervention best explains the effect.

        Shared by :meth:`_resolve_primary_intervention` (which keeps only the top
        result) and :meth:`rank_causes` (which keeps them all) -- trying one candidate
        at a time needs no joint, multi-variable intervention, which
        ``backdoor_adjustment`` does not support.

        :param model: The causal circuit to search.
        :param cause_variables: The candidate cause variables, one or more.
        :param effect_variable: The declared effect variable.
        :param effect_truncation_event: The event the declared effect condition
            translates to, used to narrow each candidate's interventional joint to the
            effect before ranking its regions.
        :param confounder_variables: Variables marked ``confounder`` in the query,
            passed through to ``backdoor_adjustment`` as its adjustment set for every
            candidate.
        :return: Every candidate with a region of positive probability and a positive
            effect probability within it, highest-scoring first.
        """
        scored_interventions = [
            scored_intervention
            for cause_variable in cause_variables
            if (
                scored_intervention := cls._score_intervention(
                    model,
                    cause_variable,
                    effect_variable,
                    effect_truncation_event,
                    confounder_variables,
                )
            )
            is not None
        ]
        scored_interventions.sort(
            key=lambda candidate: candidate.effect_probability_given_region,
            reverse=True,
        )
        return scored_interventions

    def rank_causes(self, expression: Match[T]) -> List[ScoredIntervention]:
        """
        Rank every ``cause`` candidate in *expression* by how well its intervention
        explains the declared effect.

        Runs the same per-candidate search :meth:`_evaluate` uses internally for a
        multi-``cause`` query, but returns every scoreable candidate instead of only
        the primary one :meth:`_evaluate` picks -- useful when several plausible causes
        exist and how they compare matters, not just which one wins (for example, both
        ``arm`` and ``force`` scoring high for a pick failure). Leaves
        :meth:`_evaluate` and the primary-cause search it uses entirely unchanged; this
        is an additional, independent read of the same candidates.

        Any field marked ``confounder`` is passed to every candidate's search as
        ``backdoor_adjustment``'s adjustment set, so a variable that drives both a
        candidate and the effect does not inflate that candidate's score with mere
        correlation.

        :param expression: A match with one or more ``cause`` fields and a
            ``causes_effect(...)`` condition.
        :raises NoCauseVariablesForRanking: If *expression* has no ``cause`` fields.
        :raises NoCausesEffectConditionForCause: If no ``causes_effect(...)`` condition
            declared an effect.
        :raises MultipleEffectVariablesNotSupported: If more than one effect variable
            was found.
        :raises DoRequiresCausalCircuitModel: If the resolved model is not a
            :class:`~probabilistic_model.probabilistic_circuit.causal.causal_circuit.CausalCircuit`.
        :return: Every scoreable candidate, ranked highest-scoring first.
        """
        parameters = UnderspecifiedParameters(expression)
        if not parameters.search_cause_variables:
            raise NoCauseVariablesForRanking(expression._get_expression_())
        model = self.model_registry.get_model(parameters)
        if not isinstance(model, CausalCircuit):
            raise DoRequiresCausalCircuitModel(model)
        cause_effect = self._resolve_cause_and_effect_variables(parameters, expression)
        return self._score_all_interventions(
            model,
            cause_effect.cause_variables,
            cause_effect.effect_variable,
            parameters.truncation_assignments_from_where_conditions,
            cause_effect.confounder_variables,
        )

    @staticmethod
    def _score_intervention(
        model: CausalCircuit,
        cause_variable: random_events.variable.Variable,
        effect_variable: random_events.variable.Variable,
        effect_truncation_event: Optional[Event],
        confounder_variables: Iterable[random_events.variable.Variable] = (),
    ) -> Optional[ScoredIntervention]:
        """
        Compute ``cause_variable``'s best-region search result and score it by how
        *reliably* that region produces the effect: ``P(effect | do(cause_variable in
        best_region))``. Comparable across candidates because it is a conditional
        probability under each candidate's own interventional distribution, not scaled
        by how much of that candidate's domain the region happens to cover.

        This must be scored on the interventional joint restricted to *only* the region,
        before conditioning on the effect: scoring on the already effect-truncated
        circuit instead would read close to 100% for *any* region, including a
        candidate's entire, unrestricted domain (an uninformative candidate's only
        "region"), since conditioning on the effect first makes whatever region is
        examined trivially compatible with it by construction. The region itself is
        still chosen by searching the effect-truncated circuit -- that search still
        needs to know which values are compatible with the effect; only the *score* is
        measured against the region-only, effect-free distribution.

        # `_best_disjoint_region` is private: `causal_circuit.py` is a stable #
        dependency this glue code does not modify beyond what #
        doc/eql/user/causality.md documents. It is the disjoint counterpart of #
        `_best_region` (which `diagnose_failure` uses for `recommended_region`): #
        `_best_region`'s regions always collapse to the variable's whole domain, which #
        cannot discriminate between candidates -- `_best_disjoint_region` keeps #
        separate SumUnit branches separate, which this ranking needs.

        :param model: The causal circuit to search.
        :param cause_variable: The candidate cause variable.
        :param effect_variable: The declared effect variable.
        :param effect_truncation_event: The event the declared effect condition
            translates to.
        :param confounder_variables: Variables marked ``confounder`` in the query,
            passed through to ``backdoor_adjustment`` as its adjustment set.
        :return: The scored candidate, or ``None`` if it has no region with positive
            probability, or the effect has zero probability within that region.
        """
        interventional = model.backdoor_adjustment(
            cause_variable, effect_variable, list(confounder_variables)
        )

        # `.truncated()` fills in missing variables *in place* on the event it is
        # given, so reusing the same event object across several `.truncated()` calls
        # (each on a differently-shaped circuit) would leak one call's variables into
        # the next -- pass a fresh copy each time. `Event` defines its own
        # no-argument `__deepcopy__`, incompatible with the `copy` module's
        # memo-passing convention, so it is called directly rather than through
        # `copy.deepcopy`.
        if effect_truncation_event:
            effect_truncated, _ = interventional.truncated(
                effect_truncation_event.__deepcopy__()
            )
        else:
            effect_truncated = interventional
        if effect_truncated is None:
            return None

        best_region = model._best_disjoint_region(cause_variable, effect_truncated)
        if best_region is None:
            return None

        region_only, region_prior_probability = interventional.truncated(
            best_region.fill_missing_variables_pure(interventional.variables)
        )
        if region_only is None or region_prior_probability <= 0.0:
            return None

        if effect_truncation_event:
            narrowed, effect_given_region_probability = region_only.truncated(
                effect_truncation_event.__deepcopy__()
            )
        else:
            narrowed, effect_given_region_probability = region_only, 1.0
        if narrowed is None or effect_given_region_probability <= 0.0:
            return None
        return ScoredIntervention(
            cause_variable, float(effect_given_region_probability), narrowed
        )
