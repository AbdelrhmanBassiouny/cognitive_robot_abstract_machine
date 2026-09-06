"""
EQL-native Single-Class Ripple Down Rules.

The rule tree is an EQL query DAG over a shared case variable, grown in place rather than
regenerated from source. Classification is plain
EQL evaluation; fitting grows the DAG in place, anchored on the rule that fired:

* a rule fired with the wrong conclusion -> add a **refinement** there, so it overrides
* no rule fired                          -> add an **alternative** at the conditions root

Single-class means conclusions are mutually exclusive: each case resolves to one value.
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, field, replace
from functools import cached_property

from typing_extensions import (
    Any,
    FrozenSet,
    Iterator,
    List,
    Optional,
    Self,
    Sequence,
    Set,
    TYPE_CHECKING,
    Type,
)

from krrood.entity_query_language.core.base_expressions import SymbolicExpression
from krrood.entity_query_language.core.mapped_variable import CanBehaveLikeAVariable
from krrood.entity_query_language.core.variable import Variable
from krrood.entity_query_language.exceptions import SelfReferentialInsertionError
from krrood.entity_query_language.factories import add, entity, variable
from krrood.entity_query_language.query.query import Query
from krrood.entity_query_language.rdr.backward_inference import (
    BackwardInferenceIndex,
    ConclusionSufficientConditionSets,
)
from krrood.entity_query_language.rdr.conclusion_domain import (
    ConclusionDomain,
    resolve_conclusion_domain,
)
from krrood.entity_query_language.rdr.condition_resolver import (
    ConditionResolver,
    ResolutionMode,
    ResolvedCondition,
)
from krrood.entity_query_language.rdr.corner_case import CornerCaseStore
from krrood.entity_query_language.rdr.exceptions import (
    ConditionsNotInsertable,
    ExpertRequired,
    RDRDidNotConvergeError,
)
from krrood.entity_query_language.rdr.expert import Expert
from krrood.entity_query_language.rdr.interface import CaseContext
from krrood.entity_query_language.rdr.observer import (
    ClassificationTrace,
    ConclusionObserver,
    classify_case,
    trace_case,
)
from krrood.entity_query_language.rdr.progress import (
    NullProgressReporter,
    ProgressDescription,
    ProgressReporter,
)
from krrood.entity_query_language.rdr.rule_tree import (
    StatedRule,
    insert_alternative,
    insert_refinement,
)
from krrood.entity_query_language.rdr.rule_tree_view import (
    DEFAULT_HEAD,
    DEFAULT_TAIL,
    render_rule_tree,
)
from krrood.entity_query_language.rdr.serialization import (
    ModelSaver,
    TemporaryModelSaver,
)
from krrood.entity_query_language.rdr.underspecified import UnderspecifiedMatch
from krrood.entity_query_language.scope import (
    attach_definition_scope,
    capture_caller_scope,
)

if TYPE_CHECKING:
    from krrood.entity_query_language.query.match import Match


@dataclass
class EQLSingleClassRDR:
    """
    A single-class RDR whose rule tree is an EQL expression DAG grown in place.
    """

    case_type: Type
    """
    The type of case the RDR classifies (e.g. ``Animal``).
    """

    conclusion_attribute_name: str
    """
    The underspecified attribute the RDR predicts (e.g. ``"species"``).
    """

    case_variable: Variable = field(init=False)
    """
    The shared EQL variable the whole rule tree ranges over.
    """

    conclusion_variable: CanBehaveLikeAVariable = field(init=False)
    """
    The attribute expression the rules conclude on (``case_variable.<attribute>``).
    """

    query: Optional[Query] = field(init=False, default=None)
    """
    The root rule-tree query; ``None`` until the first rule is added.
    """

    corner_cases: CornerCaseStore = field(default_factory=CornerCaseStore)
    """
    Maps each rule's condition-node id to the case that triggered its creation.
    """

    condition_resolver: Optional[ConditionResolver] = None
    """
    Derives a differentiating condition from the rule tree before the expert is asked.

    ``None`` asks the expert for every new rule. Only the refinement branch resolves;
    see :meth:`_resolve_condition`.
    """

    resolution_mode: ResolutionMode = ResolutionMode.AUTOMATIC
    """
    Whether a resolved condition is inserted directly or offered to the expert as a
    hint.

    Has no effect while :attr:`condition_resolver` is ``None``.
    """

    model_saver: ModelSaver = field(default_factory=TemporaryModelSaver)
    """
    Persists the RDR when a fit finishes, including when it ends by raising.

    Writes to a temporary file by default, so an interrupted fit leaves the rules it had
    authored somewhere recoverable rather than nowhere.
    """

    progress_reporter: ProgressReporter = field(default_factory=NullProgressReporter)
    """
    Reports how far :meth:`fit` has worked through its cases.

    Displays nothing by default.
    """

    _backward_index: BackwardInferenceIndex = field(
        default_factory=BackwardInferenceIndex, repr=False
    )
    """
    Caches backward-inference queries.

    Invalidated on every rule insertion.
    """

    def __post_init__(self) -> None:
        self.case_variable = variable(self.case_type, domain=[])
        self.conclusion_variable = getattr(
            self.case_variable, self.conclusion_attribute_name
        )
        # Snapshot the namespace the RDR was created in, so an interactive expert can be
        # driven with the same scope.
        attach_definition_scope(self.case_variable, capture_caller_scope())

    @classmethod
    def from_underspecified(
        cls,
        underspecified_query: Match,
        model_saver: Optional[ModelSaver] = None,
    ) -> Self:
        """
        Build an RDR from an underspecified ``Match`` query, whose lone ``...``
        attribute defines what the RDR predicts.

        :param underspecified_query: For example ``an(Animal)(species=...)``.
        :param model_saver: Where the rules are persisted, defaulting to the same
            temporary store the constructor uses. Rules concluding something the
            serializer cannot write pass :class:`NullModelSaver` here.
        :return: An RDR predicting the query's single underspecified attribute.
        """
        statement = UnderspecifiedMatch(underspecified_query)
        return cls(
            statement.case_type,
            statement.target_attribute_name,
            model_saver=model_saver or TemporaryModelSaver(),
        )

    # %% classification

    def classify(self, case: Any) -> Any:
        """
        :param case: The case to classify.
        :return: The inferred conclusion, or ``...`` when no rule fires.
        """
        if self.query is None:
            return ...
        return self._observe(case).conclusion

    def _observe(self, case: Any) -> ConclusionObserver:
        """
        :param case: The case to classify.
        :return: The observer that watched the classification, for debugging and
            explanation.
        """
        return classify_case(
            self.query, self.case_variable, self.conclusion_variable, case
        )

    def _trace(self, case: Any) -> ClassificationTrace:
        """
        :param case: The case to classify.
        :return: A trace of which rules fired, were evaluated, and were skipped.
        """
        return trace_case(
            self.query,
            self.case_variable,
            self.conclusion_variable,
            case,
            self.conditions_root,
        )

    def render_tree(
        self,
        case: Any,
        *,
        head: int = DEFAULT_HEAD,
        tail: int = DEFAULT_TAIL,
        use_color: bool = True,
    ) -> str:
        """
        Render the rule tree for ``case``, colouring each rule fired / evaluated /
        skipped.

        :param case: The case to classify and explain.
        :param head: Rules to show before the elision marker.
        :param tail: Rules to show after it, ending on the firing rule.
        :param use_color: Whether to colour rows by status.
        :return: The rendered tree, or ``""`` when the RDR has no rules yet.
        """
        if self.query is None:
            return ""
        return render_rule_tree(
            self._trace(case), head=head, tail=tail, use_color=use_color
        )

    # %% fitting one case

    @contextmanager
    def _saved_when_the_rules_change(self) -> Iterator[None]:
        """
        Persist the RDR once the enclosing change finishes, whether it returned or
        raised.

        A fit that dies partway has still authored real rules, and this is what keeps
        them: the save runs on the way out either way, and an exception carries on
        unchanged.

        A tree with no rules is not saved. There is nothing in it to recover, and the
        serializer rejects it — which, raised from here, would replace whatever ended
        the fit with a complaint about saving it.
        """
        try:
            yield
        finally:
            if self.query is not None:
                self.model_saver.save(self)

    def fit_case(
        self, case: Any, target: Any = ..., expert: Optional[Expert] = None
    ) -> Any:
        """
        Ensure the RDR classifies ``case`` as ``target``, growing the rule tree when it
        does not.

        With no ``target`` the expert supplies both the conclusion and its conditions;
        otherwise only the conditions are asked for, since the conclusion is known.

        :param case: The case to fit.
        :param target: The known correct conclusion, or ``...`` when there is no ground
            truth.
        :param expert: Supplies the new rule's conditions, and its conclusion when
            ``target`` is absent. Only needed when a rule has to be inserted.
        :return: The conclusion now associated with ``case``.
        :raises ExpertRequired: When a rule must be inserted but no expert was supplied.
        """
        with self._saved_when_the_rules_change():
            return self._fit_case(case, target, expert)

    def _fit_case(
        self, case: Any, target: Any = ..., expert: Optional[Expert] = None
    ) -> Any:
        """
        The body of :meth:`fit_case`, without the save.

        :meth:`fit` drives this directly so a dataset costs one save rather than one per
        case.

        :param case: The case to fit.
        :param target: The known correct conclusion, or ``...`` when there is no ground
            truth.
        :param expert: Supplies the new rule's conditions, and its conclusion when
            ``target`` is absent.
        :return: The conclusion now associated with ``case``.
        :raises ExpertRequired: When a rule must be inserted but no expert was supplied.
        """
        context = self._build_context(case, target)
        if context.has_target and context.current_conclusion == target:
            return target

        if expert is None:
            raise ExpertRequired(case=case)

        if context.has_target:
            return self._fit_against_target(context, expert)
        return self._fit_by_labelling(context, expert)

    def _build_context(self, case: Any, target: Any) -> CaseContext:
        """
        Gather everything the expert and the resolvers need about one case.

        :param case: The case being fitted.
        :param target: The known correct conclusion, or ``...``.
        :return: The context, carrying the current conclusion the tree produces, the
            trace that produced it, and the corner case of whichever rule fired.
        """
        trace = None if self.query is None else self._trace(case)
        return CaseContext(
            case_instance=case,
            case_variable=self.case_variable,
            current_conclusion=trace.conclusion if trace is not None else ...,
            target_conclusion=target,
            trace=trace,
            conclusion_domain=self.conclusion_domain,
            corner_case=self.corner_cases.get(
                trace.firing_anchor_id if trace is not None else None
            ),
        )

    def _fit_against_target(self, context: CaseContext, expert: Expert) -> Any:
        """
        Fit a case whose correct conclusion is known, resolving the condition
        automatically where possible and asking the expert otherwise.

        :param context: The case context being fitted, carrying its target conclusion.
        :param expert: Supplies the conditions when they cannot be resolved.
        :return: The target conclusion.
        """
        resolved = self._resolve_condition(context)
        if resolved is not None and self.resolution_mode is ResolutionMode.AUTOMATIC:
            condition = resolved.expression
        else:
            condition = expert.ask_for_conditions(
                replace(context, suggested_condition=resolved)
            )
        self._insert_rule(context, condition, context.target_conclusion, expert)
        return context.target_conclusion

    def _fit_by_labelling(self, context: CaseContext, expert: Expert) -> Any:
        """
        Fit a case with no ground truth, letting the expert label it and justify the
        label.

        :param context: The case context being fitted, with no target conclusion.
        :param expert: Supplies both the conclusion and its conditions.
        :return: The conclusion the expert chose, which may be the one already standing.
        """
        answer = expert.ask_for_rule(context)
        if answer.conditions is None:
            # The expert kept the current conclusion, so there is nothing to insert.
            return answer.conclusion
        self._insert_rule(context, answer.conditions, answer.conclusion, expert)
        return answer.conclusion

    def _resolve_condition(self, context: CaseContext) -> Optional[ResolvedCondition]:
        """
        Ask the configured resolver for a condition separating the case from the corner
        case of the rule that wrongly fired.

        Which situations a resolver can handle, and what it reads to decide, are its own
        business — this only settles whether there is a resolver to ask.

        :param context: The case context being fitted.
        :return: The resolved condition, or ``None`` to fall back to the expert.
        """
        if self.condition_resolver is None:
            return None
        return self.condition_resolver.resolve(self, context)

    def _insert_rule(
        self,
        context: CaseContext,
        condition: SymbolicExpression,
        conclusion: Any,
        expert: Expert,
    ) -> None:
        """
        Add a rule concluding ``conclusion`` under ``condition``.

        A condition that is the firing rule's own anchor cannot be spliced — it would
        close a cycle in the DAG — so in
        :attr:`~krrood.entity_query_language.rdr.condition_resolver.ResolutionMode.HINT`
        mode the expert is asked again with that failure shown. In
        :attr:`~krrood.entity_query_language.rdr.condition_resolver.ResolutionMode.AUTOMATIC`
        mode nobody is watching to answer differently, so it surfaces.

        :param context: The case context the new rule is written for.
        :param condition: The condition the new rule fires on.
        :param conclusion: The conclusion the new rule draws.
        :param expert: Asked for a replacement condition when the splice is rejected.
        :raises ConditionsNotInsertable: When the splice is rejected and the expert is not
            being consulted.
        """
        while True:
            try:
                self._splice_rule(context, condition, conclusion)
                return
            except SelfReferentialInsertionError as error:
                rejection = ConditionsNotInsertable(anchor=error.anchor)
                if self.resolution_mode is not ResolutionMode.HINT:
                    raise rejection from error
                condition = expert.ask_for_conditions(context, prior_errors=[rejection])

    def _splice_rule(
        self, context: CaseContext, condition: SymbolicExpression, conclusion: Any
    ) -> None:
        """
        Seed the rule tree, extend it with an alternative, or refine the rule that
        fired, then record the case the new rule was written for.

        :param context: The case context the new rule is written for.
        :param condition: The condition the new rule fires on.
        :param conclusion: The conclusion the new rule draws.
        """
        if not context.has_current_conclusion:
            new_node = self._add_alternative(condition, conclusion)
        else:
            new_node = insert_refinement(
                context.trace.firing_anchor,
                condition,
                self.conclusion_variable,
                conclusion,
            )

        self.corner_cases.record(new_node, context.case_instance)
        self._backward_index.invalidate()

    def _add_alternative(
        self, condition: SymbolicExpression, conclusion: Any
    ) -> SymbolicExpression:
        """
        Seed the rule tree with its first rule, or add one to be tried after every rule
        already in it.

        :param condition: The condition the new rule fires on.
        :param conclusion: The conclusion the new rule draws.
        :return: The newly created condition node.
        """
        if self.query is None:
            self.query = entity(self.case_variable).where(condition)
            with self.query:
                add(self.conclusion_variable, conclusion)
            self.query.build()
            return self.query._conditions_root_
        return insert_alternative(
            self.query._conditions_root_,
            condition,
            self.conclusion_variable,
            conclusion,
        )

    # %% rules stated outright

    def state_rules(self, rules: Sequence[StatedRule]) -> Self:
        """
        Take rules already worked out, in the order they are to be tried.

        Fitting derives a rule from a case, which is what an expert correcting a wrong
        answer has to offer; an author who already knows the rules has instead to invent
        a case each one would be derived from. So the rules are taken as they are, and
        the tree they make is the same tree fitting grows -- a case one of them gets
        wrong is still corrected by fitting it.

        The first rule whose condition holds is the one that answers, so stating a
        narrow rule before the general one it overlaps is how the narrow one is
        preferred.

        :param rules: The rules to state, most specific first.
        :return: This RDR, for chaining.
        """
        with self._saved_when_the_rules_change():
            for rule in rules:
                self._add_alternative(rule.condition, rule.conclusion)
            self._backward_index.invalidate()
        return self

    # %% fitting a dataset

    def fit(
        self,
        cases: List[Any],
        targets: Optional[List[Any]] = None,
        expert: Optional[Expert] = None,
    ) -> Self:
        """
        Fit the RDR over ``cases``.

        With ``targets`` the fit is convergent: after each pass any case a later rule
        retroactively broke is fitted again, until every case is correct. Without them
        there is no ground truth to converge against, so the expert labels each case
        once.

        :param cases: The cases to fit.
        :param targets: The ground-truth conclusions paired with ``cases``, or ``None``
            to have the expert label them.
        :param expert: Supplies the new rules' conditions, and their conclusions when
            ``targets`` is ``None``.
        :return: This RDR, for chaining.
        :raises RDRDidNotConvergeError: When the set of misclassified cases repeats,
            meaning the tree oscillates instead of converging.
        """
        paired_targets = targets if targets is not None else [...] * len(cases)
        self.progress_reporter.start(len(cases), ProgressDescription.FITTING)
        with self._saved_when_the_rules_change():
            try:
                if targets is None:
                    for case, target in zip(cases, paired_targets):
                        self._fit_case(case, target, expert)
                        self.progress_reporter.update()
                else:
                    self._fit_until_converged(cases, paired_targets, expert)
            finally:
                self.progress_reporter.finish()
        return self

    def _fit_until_converged(
        self,
        cases: List[Any],
        targets: List[Any],
        expert: Optional[Expert],
    ) -> None:
        """
        Fit every misclassified case, repeatedly, until none is left.

        A rule inserted for one case can intercept a case fitted earlier, so each pass
        recomputes which cases are still wrong. Reaching a set of wrong cases that an
        earlier pass already left means the passes have entered a cycle, and no further
        pass can leave it.

        The comparison is against *every* earlier pass, not just the one before: a fit
        that alternates between two sets of wrong cases never repeats itself on
        consecutive passes, and would loop forever under the narrower test.

        :param cases: All cases, including those already classified correctly.
        :param targets: The ground-truth conclusions paired with ``cases``.
        :param expert: Supplies the new rules' conditions.
        :raises RDRDidNotConvergeError: When a pass leaves a set of wrong cases an
            earlier pass already left.
        """
        pending = list(range(len(cases)))
        pending_after_earlier_passes: Set[FrozenSet[int]] = set()
        completed_passes = 0

        while True:
            for index in pending:
                self._fit_case(cases[index], targets[index], expert)
                self.progress_reporter.update()

            pending = [
                index
                for index in range(len(cases))
                # A case with no ground truth has nothing to converge against.
                if targets[index] is not ...
                and self.classify(cases[index]) != targets[index]
            ]
            if not pending:
                return

            completed_passes += 1
            if frozenset(pending) in pending_after_earlier_passes:
                raise RDRDidNotConvergeError(
                    clashing_cases=[cases[index] for index in pending],
                    passes=completed_passes,
                )
            pending_after_earlier_passes.add(frozenset(pending))

            self.progress_reporter.reset(len(pending))

    # %% reading the rule tree

    @property
    def conditions_root(self) -> Optional[SymbolicExpression]:
        """
        The root of the rule tree's condition DAG, or ``None`` while it is empty.
        """
        return self.query._conditions_root_ if self.query is not None else None

    @cached_property
    def conclusion_domain(self) -> ConclusionDomain:
        """
        The allowable-value domain of the predicted attribute, resolved from its type.
        """
        return resolve_conclusion_domain(self.case_type, self.conclusion_attribute_name)

    def sufficient_conditions_for(
        self, conclusion: Any
    ) -> ConclusionSufficientConditionSets:
        """
        Walk the rule tree backwards to enumerate every path that produces
        ``conclusion``.

        Each path contributes one sufficient condition set; together they are a
        disjunction of the ways the rule tree can reach that conclusion.

        :param conclusion: The conclusion value to work backwards from.
        :return: The sufficient condition sets for ``conclusion``.
        """
        return self._backward_index.query(self.conditions_root, conclusion)
