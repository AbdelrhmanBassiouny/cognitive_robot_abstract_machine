"""
Delegation analyzer: walks MROs and produces :class:`DelegationSpec` values.

This is the pure-analysis equivalent of :class:`DelegationGenerator`.  It
classifies members (fields, properties, methods, factories) and determines
which defining ancestor each should be attributed to, but produces
:class:`MemberSpec` data objects instead of CST nodes.
"""

from __future__ import annotations

import dataclasses
import inspect
from dataclasses import dataclass, field
from typing import Any, Callable, Iterator

from krrood.class_diagrams.class_diagram import WrappedClass
from krrood.class_diagrams.utils import (
    GenericTypeSubstitution,
    get_property_return_type,
    same_package,
)
from krrood.class_diagrams.wrapped_field import WrappedField
from krrood.patterns.code_generation.analysis.base import (
    AnalysisContext,
    CodeAnalyzer,
)
from krrood.patterns.code_generation.specs.specs import (
    DelegationSpec,
    FieldSpec,
    MemberSpec,
    MethodSpec,
    ParameterSpec,
    PropertySpec,
)


def _is_original_field_definer(klass: type, field_name: str) -> bool:
    """Return True if *klass* is where *field_name* is first introduced in its MRO."""
    if field_name not in vars(klass).get("__annotations__", {}):
        return False
    return not any(
        field_name in vars(ancestor).get("__annotations__", {})
        for ancestor in klass.__mro__[1:]
        if ancestor is not object
    )


# ── MroWalker (preserved from delegation_generator.py) ───────────────


@dataclasses.dataclass
class MroWalker:
    """Encapsulates MRO-walking logic with package and coverage checks.

    Provides common iteration patterns over a class's MRO that are used
    throughout the delegation analyzer to find defining ancestors,
    iterate non-covered same-package bases, etc.
    """

    clazz: type
    already_covered_bases: set[type]
    module_name: str
    is_excluded_defining_class: Callable[[type], bool] | None = None

    def _should_skip(self, klass: type) -> bool:
        return klass is object

    def _is_excluded(self, klass: type) -> bool:
        if self.is_excluded_defining_class is None:
            return False
        return self.is_excluded_defining_class(klass)

    def _is_same_package(self, klass: type) -> bool:
        return klass.__module__ == self.module_name or same_package(
            klass.__module__, self.module_name
        )

    def find_defining_class(self, is_member: Callable[[type], bool]) -> type | None:
        for klass in self.clazz.__mro__[1:]:
            if self._should_skip(klass):
                return None
            if is_member(klass):
                if self._is_excluded(klass):
                    return None
                if klass in self.already_covered_bases:
                    return None
                if self._is_same_package(klass):
                    return klass
                return None
        return None

    def is_member_already_covered(self, is_member: Callable[[type], bool]) -> bool:
        for klass in self.clazz.__mro__[1:]:
            if self._should_skip(klass):
                return False
            if is_member(klass):
                if self._is_excluded(klass):
                    return False
                return klass in self.already_covered_bases
        return False

    def iter_non_covered_same_package(
        self, stop_at: type | None = None
    ) -> Iterator[type]:
        for klass in self.clazz.__mro__[1:]:
            if self._should_skip(klass) or klass is stop_at:
                return
            if klass in self.already_covered_bases:
                continue
            if self._is_same_package(klass):
                yield klass

    def find_first(self, predicate: Callable[[type], bool]) -> type | None:
        for klass in self.clazz.__mro__[1:]:
            if self._should_skip(klass):
                return None
            if predicate(klass):
                return klass
        return None

    def find_nearest_covered(self, stop_at: type) -> type | None:
        for klass in self.clazz.__mro__[1:]:
            if self._should_skip(klass) or klass is stop_at:
                return None
            if klass in self.already_covered_bases:
                return klass
        return None


# ── DelegationAnalyzer ───────────────────────────────────────────────


@dataclass
class DelegationAnalyzer(CodeAnalyzer):
    """Analyzes a class's MRO to determine what members need delegation.

    Produces a :class:`DelegationSpec` describing every field, property, and
    method that should be delegated, grouped by the ancestor class that
    originally defines each member.

    This replaces the analysis half of :class:`DelegationGenerator`.  CST
    node generation has moved to :class:`RoleTransformationPlanner`.
    """

    delegatee_attribute_name: str = "delegatee"
    """Attribute name on the delegating class that holds the delegatee."""

    excluded_method_names: frozenset[str] = field(default_factory=frozenset)
    """Method names to always exclude from delegation."""

    excluded_member_predicate: Callable[[str, type], bool] | None = None
    """Optional predicate to exclude specific members."""

    is_excluded_defining_class: Callable[[type], bool] | None = None
    """Optional predicate to exclude entire defining classes."""

    def _mro_walker(self, clazz: type, context: AnalysisContext) -> MroWalker:
        return MroWalker(
            clazz=clazz,
            already_covered_bases=context.already_covered_bases,
            module_name=context.module_name,
            is_excluded_defining_class=self.is_excluded_defining_class,
        )

    def _normalise(self, type_obj: Any, context: AnalysisContext) -> str:
        return context.normaliser.normalise(type_obj)

    def analyze(
        self,
        target: WrappedClass,
        context: AnalysisContext,
        *,
        already_delegated_field_names: list[str] | None = None,
        additional_skip_bases: set[type] | None = None,
    ) -> DelegationSpec:
        """Analyze *target* and return a :class:`DelegationSpec`.

        :param target: The wrapped class to analyze for delegation needs.
        :param context: Shared analysis context.
        :param already_delegated_field_names: Field names already covered by
            a parent delegation mixin.
        :param additional_skip_bases: Extra base classes whose methods should
            not be delegated.
        """
        members: list[MemberSpec] = []
        taker_fields = already_delegated_field_names or []
        skip_bases = context.already_covered_bases | (additional_skip_bases or set())

        self._analyze_fields(target, taker_fields, context, members)
        self._analyze_properties(target, context, members)
        self._analyze_methods(target, context, members, skip_bases)

        return DelegationSpec(
            delegatee_attribute=self.delegatee_attribute_name,
            members=members,
            excluded_names=self.excluded_method_names,
        )

    # ── field analysis ────────────────────────────────────────────

    def _analyze_fields(
        self,
        wrapped_class: WrappedClass,
        taker_fields: list[str],
        context: AnalysisContext,
        members: list[MemberSpec],
    ) -> None:
        for field_ in wrapped_class.fields:
            if field_.name in taker_fields:
                self._maybe_narrowing_for_covered_field(
                    field_, wrapped_class, context, members
                )
                continue
            walker = self._mro_walker(wrapped_class.clazz, context)
            defining_base = walker.find_defining_class(
                lambda klass: _is_original_field_definer(klass, field_.name)
            )
            if defining_base is not None:
                self._analyze_inherited_field(field_, defining_base, context, members)
            elif _is_original_field_definer(wrapped_class.clazz, field_.name):
                type_name = self._normalise(field_.field.type, context)
                members.append(
                    FieldSpec(
                        name=field_.name,
                        return_type=type_name,
                        defining_class=None,
                    )
                )
            else:
                self._maybe_narrowing_for_covered_field(
                    field_, wrapped_class, context, members
                )

    def _analyze_inherited_field(
        self,
        field_: WrappedField,
        defining_base: type,
        context: AnalysisContext,
        members: list[MemberSpec],
    ) -> None:
        base_type = field_.type_at_definer(defining_base)
        type_name = self._normalise(base_type, context)
        members.append(
            FieldSpec(
                name=field_.name,
                return_type=type_name,
                defining_class=defining_base,
            )
        )

    # ── property analysis ─────────────────────────────────────────

    def _analyze_properties(
        self,
        wrapped_class: WrappedClass,
        context: AnalysisContext,
        members: list[MemberSpec],
    ) -> None:
        walker = self._mro_walker(wrapped_class.clazz, context)
        for prop_name, prop_value in inspect.getmembers(
            wrapped_class.clazz, inspect.isdatadescriptor
        ):
            if not isinstance(prop_value, property):
                continue
            if (
                self.excluded_member_predicate is not None
                and self.excluded_member_predicate(prop_name, wrapped_class.clazz)
            ):
                continue

            defining_base = walker.find_defining_class(
                lambda klass: prop_name in vars(klass)
            )
            return_type = get_property_return_type(prop_value)
            type_name = self._normalise(return_type, context) if return_type else None

            members.append(
                PropertySpec(
                    name=prop_name,
                    return_type=type_name,
                    defining_class=defining_base,
                )
            )

    # ── method analysis ───────────────────────────────────────────

    def _analyze_methods(
        self,
        wrapped_class: WrappedClass,
        context: AnalysisContext,
        members: list[MemberSpec],
        skip_bases: set[type],
    ) -> None:
        skip_base_names: set[str] = set()
        for base in wrapped_class.clazz.__mro__[1:]:
            if base in skip_bases:
                skip_base_names.update(dir(base))

        walker = self._mro_walker(wrapped_class.clazz, context)
        for method_name, method in inspect.getmembers(
            wrapped_class.clazz,
            predicate=lambda obj: inspect.isfunction(obj) or inspect.ismethod(obj),
        ):
            if method_name in self.excluded_method_names:
                continue
            if (
                self.excluded_member_predicate is not None
                and self.excluded_member_predicate(method_name, wrapped_class.clazz)
            ):
                continue
            if method_name in skip_base_names:
                continue

            defining_base = walker.find_defining_class(
                lambda klass: method_name in vars(klass)
            )

            # Classify method type
            try:
                sig = inspect.signature(method)
            except (ValueError, TypeError):
                sig = None

            params: list[ParameterSpec] = []
            return_type: str | None = None

            if sig is not None:
                for param_name, param in sig.parameters.items():
                    if param_name == "self" or param_name == "cls":
                        continue
                    ann = None
                    if param.annotation is not inspect.Parameter.empty:
                        ann = self._normalise(param.annotation, context)
                    params.append(
                        ParameterSpec(
                            name=param_name,
                            type_annotation=ann,
                            has_default=param.default is not inspect.Parameter.empty,
                        )
                    )
                if sig.return_annotation is not inspect.Signature.empty:
                    return_type = self._normalise(sig.return_annotation, context)

            members.append(
                MethodSpec(
                    name=method_name,
                    return_type=return_type,
                    parameters=params,
                    defining_class=defining_base,
                )
            )

    # ── narrowing helpers (simplified) ────────────────────────────

    def _maybe_narrowing_for_covered_field(
        self,
        field_: Any,
        wrapped_class: WrappedClass,
        context: AnalysisContext,
        members: list[MemberSpec],
    ) -> None:
        """Detect TypeVar narrowing for fields already covered by a base mixin."""
        # Use original field definer logic to detect genuine narrowing
        defining_base = MroWalker(wrapped_class.clazz, set(), "").find_first(
            lambda klass: _is_original_field_definer(klass, field_.name)
        )
        if defining_base is None:
            return

        base_type = field_.type_at_definer(defining_base)
        substitution = GenericTypeSubstitution.from_specialization(
            wrapped_class.clazz, defining_base
        )
        if substitution.has_genuine_substitutions:
            result = substitution.apply(base_type)
            if result.resolved:
                type_name = self._normalise(result.resolved_type, context)
                members.append(
                    FieldSpec(
                        name=field_.name,
                        return_type=type_name,
                        defining_class=None,  # re-declared directly on the taker
                    )
                )


# ── factory method iteration (preserved for planner use) ─────────────


def iter_factory_method_names(
    wrapped_class: WrappedClass,
    *,
    excluded_method_names: frozenset[str] = frozenset(),
    excluded_member_predicate: Callable[[str, type], bool] | None = None,
    already_covered_bases: set[type] | None = None,
    is_excluded_defining_class: Callable[[type], bool] | None = None,
) -> Iterator[tuple[str, Callable]]:
    """Yield ``(name, method)`` for factory methods on *wrapped_class*.

    A factory method is a ``@classmethod`` that returns ``Self``.  This is a
    module-level helper so planners and analyzers can use it without
    instantiating a full :class:`DelegationAnalyzer`.
    """
    from krrood.patterns.role.meta_data import MethodType

    covered = already_covered_bases or set()

    for method_name, method in inspect.getmembers(
        wrapped_class.clazz,
        predicate=lambda obj: inspect.isfunction(obj) or inspect.ismethod(obj),
    ):
        if method_name in excluded_method_names:
            continue
        if excluded_member_predicate and excluded_member_predicate(
            method_name, wrapped_class.clazz
        ):
            continue

        # Only include methods defined directly or whose defining class is uncovered
        if method_name not in vars(wrapped_class.clazz):
            defining = None
            for klass in wrapped_class.clazz.__mro__[1:]:
                if klass is object:
                    break
                if method_name in vars(klass):
                    if is_excluded_defining_class and is_excluded_defining_class(klass):
                        break
                    if klass in covered:
                        break
                    defining = klass
                    break
            if defining is None:
                continue

        try:
            source = inspect.getsource(method)
        except OSError:
            continue

        from textwrap import dedent
        import libcst

        method_node = libcst.parse_module(dedent(source)).body[0]
        if not isinstance(method_node, libcst.FunctionDef):
            continue

        # Check for factory method: @classmethod + returns Self
        is_classmethod = False
        for deco in method_node.decorators:
            if (
                isinstance(deco.decorator, libcst.Name)
                and deco.decorator.value == "classmethod"
            ):
                is_classmethod = True
                break

        if not is_classmethod:
            continue

        returns = method_node.returns
        if (
            returns is not None
            and isinstance(returns.annotation, libcst.Name)
            and returns.annotation.value == "Self"
        ):
            yield method_name, method
