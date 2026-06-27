"""
Predicates and symbolic function utilities for the Entity Query Language.

This module defines predicate classes for boolean checks and a decorator to build symbolic expressions
from regular Python functions when variables are present.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import MISSING, dataclass, fields
from functools import wraps

from typing_extensions import (
    Callable,
    Iterator,
    Optional,
    Any,
    Self,
    Type,
    Tuple,
    ClassVar,
    Mapping,
    Sized,
    TYPE_CHECKING,
    Dict,
    Union,
)

if TYPE_CHECKING:
    from krrood.entity_query_language.verbalization.fragments.base import Fragment

from krrood.entity_query_language.utils import T, merge_args_and_kwargs
from krrood.entity_query_language.core.variable import (
    Variable,
    InstantiatedVariable,
    Literal,
)
from krrood.entity_query_language.core.base_expressions import (
    Selectable,
    SymbolicExpression,
)
from krrood.entity_query_language.core.base_expressions import Selectable
from krrood.patterns.code_parsing_utils import (
    get_accessed_attribute_name_in_return_statement_of_property,
)
from krrood.symbol_graph.symbol_graph import Symbol


def symbolic_function(
    function: Callable[..., T],
) -> Union[Callable[..., Variable[T]], T]:
    """
    Function decorator that constructs a symbolic expression representing the function call
     when inside a symbolic_rule context.

    When symbolic mode is active, calling the method returns a Call instance which is a SymbolicExpression bound to
    representing the method call that is not evaluated until the evaluate() method is called on the query/rule.

    :param function: The function to decorate.
    :return: The decorated function.
    """

    @wraps(function)
    def wrapper(*args, **kwargs) -> Optional[Any]:
        all_kwargs = merge_args_and_kwargs(function, args, kwargs)
        if _any_of_the_kwargs_is_a_variable(all_kwargs):
            return InstantiatedVariable(
                _type_=function,
                _kwargs_=all_kwargs,
            )
        return function(*args, **kwargs)

    return wrapper


def functional_form(symbolic_callable: Type[T]) -> Callable[..., Any]:
    """:return: a function that calls *symbolic_callable* -- the class-form counterpart of the
    :func:`symbolic_function` decorator.

    It returns a symbolic expression when any argument is a variable (so it composes in a query) and
    the directly computed value otherwise. Binding an existing function name to
    ``functional_form(TheClass)`` lets a migration to the class form keep that name's behaviour
    unchanged -- the logic moves into the class's ``__call__`` and the name just constructs it.
    """

    def call(*args: Any, **kwargs: Any) -> Any:
        result = symbolic_callable(*args, **kwargs)
        return result() if isinstance(result, symbolic_callable) else result

    return call


@dataclass(frozen=True)
class Field:
    """One predicate field as ``_verbalization_fragment_`` sees it.

    It carries both the field's already-rendered (and source-linked) :attr:`fragment` and the raw
    :attr:`value` bound to it (a :class:`Literal`'s value unwrapped). A part-of-speech element takes
    whichever it needs — :class:`Noun` uses the fragment, :class:`OneOf` uses the value — so the
    author just passes ``fields[name]`` and the right thing happens, never an explicit accessor.
    """

    fragment: "Fragment"
    """The field's rendered, source-linked fragment — what :class:`Noun` uses."""

    value: Any
    """The raw Python value bound to the field (a literal's value) — what :class:`OneOf` enumerates."""

    def as_fragment(self) -> "Fragment":
        """:return: the field's rendered fragment, so a :class:`Field` is a clause constituent like
        the part-of-speech elements — ``clause(field)`` and ``Noun(field)`` both work."""
        return self.fragment


@dataclass(frozen=True)
class RenderedFields(Mapping):
    """The arguments passed to :meth:`Verbalizable._verbalization_fragment_`.

    A mapping of *field name → :class:`Field`*. Each ``fields["x"]`` carries both the rendered
    fragment and the raw value, so it can be passed straight to a part-of-speech element — ``Noun``
    takes the fragment, ``OneOf`` takes the value — without the author choosing between them.
    """

    fragments: "Mapping[str, Fragment]"
    """The rendered fragment for each field, keyed by field name."""

    raw: "Mapping[str, SymbolicExpression]"
    """The raw child expression for each field, keyed by field name."""

    def __getitem__(self, field_name: str) -> Field:
        raw = self.raw[field_name]
        value = raw._value_ if isinstance(raw, Literal) else raw
        return Field(fragment=self.fragments[field_name], value=value)

    def __iter__(self) -> Iterator[str]:
        return iter(self.fragments)

    def __len__(self) -> int:
        return len(self.fragments)


@dataclass(frozen=True)
class Operand:
    """One operand of a symbolic callable, as its :meth:`Verbalizable._verbalization_fragment_` sees it.

    It wraps the operand's EXISTING child expression — never a freshly constructed variable, so
    coreference is preserved — together with the renderer that turns an expression into a
    :class:`Fragment` in the current context. Used directly it renders the operand
    (``Noun(operands.body)``); navigated it renders a DERIVED expression on the SAME variable
    (``operands.tip.name`` → *"the name of …"*), reusing EQL's attribute navigation.

    An author never constructs one: it is handed to the fragment as an attribute of the typed
    :class:`OperandView` (``operands.tip``), so the IDE resolves ``tip`` to the field and ``name`` to
    the field type's attribute (autocompletion, go-to-definition).
    """

    _expression_: Any
    """The EXISTING child expression this operand wraps (or a derived expression after navigation)."""

    _render_: "Callable[[Any], Fragment]"
    """Renders an expression to a fragment in the current context (coreference, determiners)."""

    def as_fragment(self) -> "Fragment":
        """:return: the operand's rendered fragment, so an :class:`Operand` is a clause constituent
        like the part-of-speech elements — ``Noun(operands.body)`` and ``clause(operands.body)`` work."""
        return self._render_(self._expression_)

    @property
    def _value_of_operand_(self) -> Any:
        """:return: the raw Python value bound to the operand (a literal's value unwrapped) — what
        :class:`OneOf` enumerates. Named with surrounding underscores so it is not mistaken for a
        navigated attribute (``operands.x.value`` navigates to ``x.value``, it does not read this)."""
        return (
            self._expression_._value_
            if isinstance(self._expression_, Literal)
            else self._expression_
        )

    def __getattr__(self, attribute_name: str) -> "Operand":
        """:return: the operand for a navigated attribute, built on the SAME underlying expression so
        coreference holds — ``operands.tip.name`` is the name of the existing tip, not a new variable.

        Only public names navigate; a dunder/private name raises :class:`AttributeError` so copying,
        pickling and the real fields are unaffected.
        """
        if attribute_name.startswith("_"):
            raise AttributeError(attribute_name)
        return Operand(getattr(self._expression_, attribute_name), self._render_)


@dataclass(frozen=True)
class OperandView:
    """The typed view of a symbolic callable's operands handed to ``_verbalization_fragment_``.

    Each attribute is the :class:`Operand` for that field — ``operands.body`` — navigable to derived
    expressions (``operands.tip.name``) and usable directly as a clause constituent. The author types
    the parameter as the callable instance (``operands: Self``), so the IDE autocompletes the operand
    fields and their attributes and go-to-definition works; at runtime each resolves to the EXISTING
    child expression. Iterating yields the operands in field order (used by the default surfaces).
    """

    _child_expressions_: "Mapping[str, Any]"
    """The EXISTING child expression for each operand field, keyed by field name."""

    _render_: "Callable[[Any], Fragment]"
    """Renders an expression to a fragment in the current context."""

    def _operand_for_(self, field_name: str) -> Operand:
        return Operand(self._child_expressions_[field_name], self._render_)

    def __getattr__(self, field_name: str) -> Operand:
        if field_name.startswith("_"):
            raise AttributeError(field_name)
        return self._operand_for_(field_name)

    def __getitem__(self, field_name: str) -> Operand:
        return self._operand_for_(field_name)

    def __iter__(self) -> Iterator[Operand]:
        return (self._operand_for_(name) for name in self._child_expressions_)


@dataclass(frozen=True)
class _PreviewExpression:
    """A stand-in operand expression for :meth:`SymbolicCallable.preview_verbalization`.

    It has no query behind it, so navigation just records a dotted path (``tip`` → ``tip.name``)
    that the preview renders verbatim — letting a developer see which derived attribute a fragment
    reads without building a query.
    """

    _path_: str
    """The dotted access path so far (the field name, then each navigated attribute)."""

    def __getattr__(self, attribute_name: str) -> "_PreviewExpression":
        if attribute_name.startswith("_"):
            raise AttributeError(attribute_name)
        return _PreviewExpression(f"{self._path_}.{attribute_name}")

    def __iter__(self) -> Iterator[Any]:
        # So a fragment using OneOf over an operand previews without a real collection behind it.
        return iter(())


@dataclass(eq=False)
class Verbalizable(ABC):
    """
    A mixin for classes that want to add custom verbalization, such that when a query that is using them is verbalized,
    the final output text is more correct or intuitivie.
    """

    @classmethod
    @abstractmethod
    def _verbalization_fragment_(cls, operands: "OperandView") -> Fragment:
        """
        Structured verbalization for this operation — a clause built from typed operands.

        Build the clause from the typed part-of-speech vocabulary
        (:func:`~…vocabulary.parts_of_speech.clause` with ``Noun`` / ``Verb`` / ``Copula`` /
        ``Preposition`` / ``Adjective``), composing the *operands* — each ``operands.<field>`` is the
        operand for that field, rendered when used (``Noun(operands.person_1)``) and navigable to a
        derived expression on the SAME variable (``operands.tip.name``, so coreference holds). State
        only the **affirmative, present-tense** form: a ``Verb`` is given as its lemma, and the
        realisation passes inflect it (*"work"* → *"works"*) and agree its number. Returning a typed
        clause rather than a string keeps the operation composable — a wrapping ``Not`` negates it
        automatically (do-support *"does not love"*; copula suppletion *"is not reachable"*) and
        coreference still reduces the operands.

        Type the parameter as ``Self`` so the IDE resolves each ``operands.<field>`` to the field's
        declared type — autocompleting its attributes and following go-to-definition into them.

        Example::

            @dataclass(eq=False)
            class Loves(Predicate):
                person_1: Person
                person_2: Person

                @classmethod
                def _verbalization_fragment_(cls, operands: Self):
                    return clause(Noun(operands.person_1), Verb("love"), Noun(operands.person_2))

        :param operands: The typed view of the operation's operands (``operands.<field>``).
        :return: The operation's verbalization fragment.
        """


@dataclass(eq=False)
class SymbolicCallable(Symbol, Verbalizable, ABC):
    """A user-defined, self-verbalizing symbolic operation.

    It is CALLED with arguments, is represented as an :class:`InstantiatedVariable` in a query when
    any argument is symbolic, and renders itself through :meth:`Verbalizable._verbalization_fragment_`.
    Its two concrete kinds — :class:`Predicate` (a boolean operation) and :class:`SymbolicFunction`
    (a value operation) — each supply a name-based DEFAULT fragment, so a subclass reads sensibly with
    no extra code and overrides only when that default is wrong. Inspect the default (or an override)
    with :meth:`preview_verbalization` to decide. The symbolic-construction machinery lives here once
    rather than in each kind.
    """

    _cache_instances_: ClassVar[bool] = False
    """Instances are not cached -- they do not persist."""

    def __new__(cls, *args, **kwargs):
        all_kwargs = merge_args_and_kwargs(
            cls.__init__, args, kwargs, ignore_first=True
        )
        if _any_of_the_kwargs_is_a_variable(all_kwargs):
            return InstantiatedVariable(
                _type_=cls,
                _kwargs_=all_kwargs,
            )
        return super().__new__(cls)

    @classmethod
    def _construct_normally_(cls, **kwargs) -> "SymbolicCallable":
        """
        Construct a concrete instance directly, bypassing the symbolic ``__new__`` redirect.

        Normally, calling ``cls(**kwargs)`` when any kwarg is a :class:`Selectable` redirects
        construction to an :class:`~krrood.entity_query_language.core.variable.InstantiatedVariable`
        so the call can be represented as a symbolic expression in a query graph.  During evaluation,
        however, the bound values themselves may be :class:`Selectable` objects (e.g. in a
        meta-query that reasons about EQL nodes).  In that case the redirect is wrong — we want the
        real instance so its :meth:`__call__` can be evaluated immediately.

        :meth:`_construct_normally_` is the escape hatch for that situation.  It calls
        ``object.__new__`` directly (skipping ``__new__`` entirely) and then ``__init__``, so the
        caller always receives a fully initialised concrete instance regardless of what the kwargs
        contain.
        """
        instance = object.__new__(cls)
        instance.__init__(**kwargs)
        return instance

    @classmethod
    def _bound_value_(cls, **kwargs) -> Any:
        """:return: the value this operation contributes to a query result when its arguments have
        concrete values -- the constructed instance itself by default (a :class:`Predicate`'s truth is
        then read from that instance). A value operation overrides this to its COMPUTED value.

        ..note:: This is the class-form counterpart of calling a ``@symbolic_function``: for a function
            the query binds ``function(**values)``; for a callable class it binds this.
        """
        return cls._construct_normally_(**kwargs)

    @classmethod
    def preview_verbalization(cls) -> str:
        """:return: the surface this operation renders to, with each argument shown as a placeholder
        named after its field — so a developer SEES the reading :meth:`Verbalizable._verbalization_fragment_`
        produces (the inherited name-based default, or an override) and can decide whether to override
        it, without constructing a whole query.

        >>> Length.preview_verbalization()
        'the length of iterable'
        """
        # Imported locally to avoid the core -> verbalization import cycle (as Triple does).
        from krrood.entity_query_language.verbalization.fragments.base import WordFragment
        from krrood.entity_query_language.verbalization.rendering.realization import (
            realize_subtree,
        )
        from krrood.entity_query_language.verbalization.vocabulary.parts_of_speech import (
            Noun,
        )

        # The surface is built from the operands a typical call passes: the fields a subclass declares
        # (the fields inherited from SymbolicCallable are infrastructure), excluding those with a
        # default (configuration usually left out of the call, so out of the rendered operands).
        infrastructure = {field.name for field in fields(SymbolicCallable)}
        field_names = [
            field.name
            for field in fields(cls)
            if field.name not in infrastructure
            and field.default is MISSING
            and field.default_factory is MISSING
        ]

        def render(expression: _PreviewExpression) -> "Fragment":
            return Noun(WordFragment(text=expression._path_)).as_fragment()

        operands = OperandView(
            _child_expressions_={
                name: _PreviewExpression(name.replace("_", " ").strip())
                for name in field_names
            },
            _render_=render,
        )
        return realize_subtree(cls._verbalization_fragment_(operands))

    @abstractmethod
    def __call__(self) -> Any:
        """
        Evaluate the operation for the supplied values.
        """


@dataclass(eq=False)
class Predicate(SymbolicCallable, ABC):
    """
    The super predicate class that represents a filtration operation or asserts a relation.
    """

    @abstractmethod
    def __call__(self) -> bool:
        """
        Evaluate the predicate for the supplied values.
        """

    def __bool__(self):
        """
        Bool casting a predicate evaluates it.
        """
        return bool(self.__call__())

    @classmethod
    def _verbalization_fragment_(cls, operands: "OperandView") -> "Fragment":
        """Default boolean surface — a clause read off the class name: copular for an ``Is…`` name
        (``IsReachable`` → *"<subject> is reachable"*), verb-first otherwise (``ConnectsTo`` →
        *"<subject> connects to <object>"*). The class-form counterpart of a boolean
        ``@symbolic_function``'s reading, so every predicate reads sensibly without extra code.

        ..warning:: This name-based default is a best guess — correct only when the class name reads
            as the predicate. When it does not, override this method with a
            :func:`~…vocabulary.parts_of_speech.clause` built from the part-of-speech vocabulary.
            Call :meth:`SymbolicCallable.preview_verbalization` to SEE the exact surface and decide.
        """
        # Imported locally to avoid the core -> verbalization import cycle (as Triple does).
        from krrood.entity_query_language.verbalization.vocabulary.parts_of_speech import (
            predicate_clause,
        )

        subject, *objects = operands
        return predicate_clause(cls.__name__, subject, *objects)


@dataclass(eq=False)
class SymbolicFunction(SymbolicCallable, ABC):
    """A user-defined operation that computes a VALUE, with its own verbalization.

    Like :class:`Predicate` it is a self-verbalizing symbolic callable, but its :meth:`__call__`
    returns a value (not a truth value), so its :meth:`Verbalizable._verbalization_fragment_` names
    that value as a NOUN PHRASE rather than a clause. The default reads *"the &lt;name&gt; of
    &lt;arguments&gt;"* off the class name; override it when that is not the surface you want.
    """

    @classmethod
    def _bound_value_(cls, **kwargs) -> Any:
        """:return: the COMPUTED value -- a value operation is constructed AND called, so a query binds
        what it computes (exactly as a ``@symbolic_function`` is called), not the instance.
        """
        return cls._construct_normally_(**kwargs)()

    @classmethod
    def _verbalization_fragment_(cls, operands: "OperandView") -> "Fragment":
        """Default value surface — *"the <name> of <arguments>"* read off the class name
        (``NodeId`` → *"the node id of …"*), the class-form counterpart of a value
        ``@symbolic_function``'s reading, so every value function reads sensibly without extra code.

        ..warning:: This name-based default is a best guess — correct only when the class name already
            reads as the noun the value is. When the reading is wrong, override this method with a
            phrase built from the part-of-speech vocabulary. Call
            :meth:`SymbolicCallable.preview_verbalization` to SEE the exact surface and decide.
        """
        # Imported locally to avoid the core -> verbalization import cycle (as Triple does).
        from krrood.entity_query_language.verbalization.vocabulary.parts_of_speech import (
            value_function_phrase,
        )

        return value_function_phrase(cls.__name__, *operands)

    @abstractmethod
    def __call__(self) -> Any:
        """
        Compute the value for the supplied arguments.
        """


@dataclass(eq=False)
class Triple(Predicate):
    """
    A Triple is a type predicate that represents a relation between two entities.
    To know if your predicate is a Triple or not ask yourself can I say "subject" "predicate_name" "object" and it
    makes sense? if so then yes. Check the verbalization function below as a reference.
    """

    @property
    @abstractmethod
    def subject(self) -> Any:
        """
        The subject of the predicate.
        """

    @property
    @abstractmethod
    def object(self) -> Any:
        """
        The object of the predicate.
        """

    @classmethod
    def _verbalization_fragment_(cls, operands: "OperandView") -> Fragment:
        """
        Verbalization of a Triple is a subject - predicate - object, where the predicate is read off
        the class name (``ConnectsTo`` → *"connects to"*; a copular ``IsAbove`` → *"is above"*) by
        :func:`~…vocabulary.parts_of_speech.predicate_clause`. A verb-first name is a :class:`Verb`
        (its lemma), so a wrapping ``Not`` negates with do-support (*"does not connect to"*).

        The subject/object field names are read off the ``subject``/``object`` properties, so the
        operands are looked up by those names (``operands[subject_name]``) rather than as attributes.
        """
        # Imported locally: the verbalization layer depends on the core predicate types, so a
        # module-level import here would close an import cycle.
        from krrood.entity_query_language.verbalization.vocabulary.parts_of_speech import (
            predicate_clause,
        )

        subject_name = get_accessed_attribute_name_in_return_statement_of_property(
            cls.subject, cls
        )
        object_name = get_accessed_attribute_name_in_return_statement_of_property(
            cls.object, cls
        )
        return predicate_clause(
            cls.__name__, operands[subject_name], operands[object_name]
        )


@dataclass(eq=False)
class HasType(Triple):
    """
    Represents a predicate to check if a given variable is an instance of a specified type.

    This class is used to evaluate whether the domain value belongs to a given type by leveraging
    Python's built-in `isinstance` functionality. It provides methods to retrieve the domain and
    range values and perform direct checks.
    """

    variable: Any
    """
    The variable whose type is being checked.
    """
    types_: Type
    """
    The type or tuple of types against which the `variable` is validated.
    """

    def __call__(self) -> bool:
        return isinstance(self.variable, self.types_)

    @property
    def subject(self):
        return self.variable

    @property
    def object(self) -> Any:
        return self.types_

    @classmethod
    def _verbalization_fragment_(cls, operands: Self) -> Fragment:
        # Imported locally to avoid the core → verbalization import cycle (see :class:`Triple`).
        from krrood.entity_query_language.verbalization.vocabulary.parts_of_speech import (
            Adjective,
            clause,
            Copula,
            Noun,
        )

        return clause(
            Noun(operands.variable),
            Copula(),
            Adjective("of type"),
            Noun(operands.types_),
        )


@dataclass(eq=False)
class HasTypes(HasType):
    """
    Represents a specialized data structure holding multiple types.

    This class is a data container designed to store and manage a tuple of
    types. It inherits from the `HasType` class and extends its functionality
    to handle multiple types efficiently. The primary goal of this class is to
    allow structured representation and access to a collection of type
    information with equality comparison explicitly disabled.
    """

    types_: Tuple[Type, ...]
    """
    A tuple containing Type objects that are associated with this instance.
    """

    @classmethod
    def _verbalization_fragment_(cls, operands: Self) -> "Fragment":
        """Say membership over the admissible types — *"<variable> is one of A, B, or C"*. The
        :class:`OneOf` element handles the bounded listing (linking, *"or"*, the count cap), so the
        types are read from the operand's value (an ``isinstance`` over the tuple is membership, not the
        tuple value an equality would mean)."""
        # Imported locally to avoid the core → verbalization import cycle (see :class:`Triple`).
        from krrood.entity_query_language.verbalization.vocabulary.parts_of_speech import (
            clause,
            Copula,
            Noun,
            OneOf,
        )

        return clause(Noun(operands.variable), Copula(), OneOf(operands.types_))


@dataclass(eq=False)
class Length(SymbolicFunction):
    """The number of items in an iterable, as a value operation.

    Its surface is the inherited :class:`SymbolicFunction` default — *"the length of <iterable>"* —
    so it needs no ``_verbalization_fragment_`` of its own.
    """

    iterable: Sized
    """The iterable whose length is computed."""

    def __call__(self) -> int:
        return len(self.iterable)


length = functional_form(Length)
"""Backward-compatible functional form of :class:`Length` (keeps the ``length(iterable)`` call)."""


def _any_of_the_kwargs_is_a_variable(bindings: Dict[str, Any]) -> bool:
    """
    :param bindings: A kwarg like dict mapping strings to objects
    :return: ``True`` if any value in ``bindings`` is a :class:`~krrood.entity_query_language.core.base_expressions.SymbolicExpression`, ``False`` otherwise.
    """
    return any(isinstance(binding, SymbolicExpression) for binding in bindings.values())
