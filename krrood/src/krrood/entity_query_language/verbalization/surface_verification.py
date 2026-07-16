"""
Exhaustive verbalization-surface verification for any package.

Point a :class:`SymbolicSurfaceSnapshot` at a package and a committed list of
:class:`VerbalizationSurface` entries. Its three ``assert_*`` methods, used as the bodies of three
tests, check that every concrete symbolic callable the package defines (1) implements its own
verbalization fragment, (2) has a declared surface, and (3) renders exactly its declared sentence —
so a new predicate or function, or a changed shared surface builder, cannot slip through unreviewed.

The same three-line test works for any package that defines
:class:`~krrood.entity_query_language.predicate.SymbolicCallable` subclasses (krrood itself,
``semantic_digital_twin``, ``coraplex``, …): the discovery, placeholder operands, and rendering all
live here.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from dataclasses import fields as dataclass_fields
from types import ModuleType

from typing_extensions import Any, Dict, Mapping, Sequence, Tuple, Type

from krrood.class_diagrams.class_diagram import WrappedClass
from krrood.class_diagrams.wrapped_field import WrappedField
from krrood.entity_query_language.factories import variable
from krrood.entity_query_language.predicate import SymbolicCallable, Verbalizable
from krrood.entity_query_language.verbalization.pipeline import verbalize_expression
from krrood.ormatic.utils import classes_of_package


@dataclass(frozen=True)
class VerbalizationSurface:
    """
    One symbolic callable and the sentence it verbalizes to — a committed snapshot
    entry.
    """

    callable_class: Type[SymbolicCallable]
    """
    The symbolic function or predicate whose surface this records.
    """

    sentence: str
    """
    The approved sentence it renders with the snapshot's placeholder operands.
    """


@dataclass(frozen=True)
class SymbolicSurfaceSnapshot:
    """
    Exhaustive verbalization-surface check for the symbolic callables a package defines.

    Discovers every concrete :class:`~krrood.entity_query_language.predicate.SymbolicCallable` in
    :attr:`package`, renders each with placeholder operands, and checks the rendering against the
    committed :attr:`surfaces`. Use the three ``assert_*`` methods as the bodies of three tests.
    """

    package: ModuleType
    """
    The package whose symbolic callables are discovered and checked.
    """

    surfaces: Sequence[VerbalizationSurface]
    """
    The committed expected surfaces, one per covered class.
    """

    operand_overrides: Mapping[Type[SymbolicCallable], Mapping[str, Any]] = field(
        default_factory=dict
    )
    """
    Concrete operands for classes whose fragment reads a field's raw VALUE rather than
    treating it as a symbolic operand (e.g. a ``Type`` field the surface names), keyed
    by the class.

    A ``Type`` field cannot be resolved by annotation alone — it may be a symbolic
    operand in one class and a named value in another — so the value is stated here per
    class.
    """

    def discovered_callables(self) -> Tuple[Type[SymbolicCallable], ...]:
        """:return: every concrete symbolic callable the package defines (abstract only in its
        verbalization fragment, if at all), sorted by qualified name."""
        discovered = {
            cls
            for cls in classes_of_package(self.package, recursive=True)
            if isinstance(cls, type)
            and issubclass(cls, SymbolicCallable)
            and set(cls.__abstractmethods__) <= {"_verbalization_fragment_"}
        }
        return tuple(sorted(discovered, key=self.qualified_name))

    @staticmethod
    def qualified_name(cls: Type) -> str:
        """:return: *cls*'s fully qualified name."""
        return f"{cls.__module__}.{cls.__qualname__}"

    @staticmethod
    def has_fragment(cls: Type[SymbolicCallable]) -> bool:
        """:return: whether *cls* decided its surface by implementing its own fragment."""
        return (
            cls._verbalization_fragment_.__func__
            is not Verbalizable._verbalization_fragment_.__func__
        )

    def placeholder_operands(self, cls: Type[SymbolicCallable]) -> Dict[str, Any]:
        """:return: one placeholder operand per init dataclass field — an override where registered,
        else a fresh variable of the field's type endpoint as the class diagram resolves it
        (``object`` when the endpoint is not a plain class), so the surface reads the operand as *"a
        <TypeName>"*."""
        overrides = self.operand_overrides.get(cls, {})
        wrapped_class = WrappedClass(clazz=cls)
        operands: Dict[str, Any] = {}
        for field_ in dataclass_fields(cls):
            if not field_.init:
                continue
            if field_.name in overrides:
                operands[field_.name] = overrides[field_.name]
                continue
            endpoint = WrappedField(wrapped_class, field_).type_endpoint
            placeholder_type = (
                endpoint
                if isinstance(endpoint, type) and endpoint is not Any
                else object
            )
            operands[field_.name] = variable(placeholder_type, [])
        return operands

    def rendered_surface(self, cls: Type[SymbolicCallable]) -> str:
        """:return: the sentence *cls* renders with placeholder operands."""
        return verbalize_expression(cls(**self.placeholder_operands(cls)))

    def assert_every_callable_has_a_fragment(self) -> None:
        """
        Assert every discovered symbolic callable implements its own fragment — there is
        no undecided surface.

        A new predicate or function that ships without one fails here.
        """
        fragment_less = sorted(
            self.qualified_name(cls)
            for cls in self.discovered_callables()
            if not self.has_fragment(cls)
        )
        assert not fragment_less, (
            "These symbolic callables have no verbalization fragment and must implement "
            f"_verbalization_fragment_: {fragment_less}."
        )

    def assert_surfaces_cover_every_callable(self) -> None:
        """
        Assert the declared surfaces are exactly the discovered callables — a new class
        with no entry, or an entry for a class that no longer exists, is a red test.
        """
        discovered = {
            self.qualified_name(cls)
            for cls in self.discovered_callables()
            if self.has_fragment(cls)
        }
        declared = {
            self.qualified_name(surface.callable_class) for surface in self.surfaces
        }
        missing = sorted(discovered - declared)
        stale = sorted(declared - discovered)
        assert discovered == declared, (
            f"Declared surfaces are out of sync. Discovered classes with no entry (add one): "
            f"{missing}. Entries whose class is no longer discovered (remove them): {stale}."
        )

    def assert_declared_surfaces_render_as_stated(self) -> None:
        """
        Assert every declared sentence matches what its class renders, so any wording
        change is re-approved by updating the entry and reviewing the diff.
        """
        mismatches = {
            self.qualified_name(surface.callable_class): self.rendered_surface(
                surface.callable_class
            )
            for surface in self.surfaces
            if self.has_fragment(surface.callable_class)
            and self.rendered_surface(surface.callable_class) != surface.sentence
        }
        assert not mismatches, (
            "Verbalization surfaces changed. Update the sentence for each of these in the snapshot "
            f"module: {mismatches}."
        )
