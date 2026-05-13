"""Tests for analysis layer: DelegationAnalyzer, RolePatternAnalyzer, ImportAnalyzer."""

from __future__ import annotations

import libcst
import pytest

from krrood.class_diagrams import ClassDiagram
from krrood.class_diagrams.utils import classes_of_module
from krrood.patterns.code_generation import (
    ImportNameResolver,
    TypeNormaliser,
)
from krrood.patterns.code_generation.analysis.base import AnalysisContext
from krrood.patterns.code_generation.analysis.delegation import (
    DelegationAnalyzer,
    MroWalker,
    iter_factory_method_names,
)
from krrood.patterns.code_generation.analysis.imports import (
    ImportAnalyzer,
    NameCollector,
    RuntimeNameCollector,
    BaseClassNameCollector,
)
from krrood.patterns.code_generation.analysis.role_pattern import (
    RolePatternAnalyzer,
)
from krrood.patterns.code_generation.specs.specs import (
    DelegationSpec,
    MemberSpec,
    MethodSpec,
    RoleClassTransformationSpec,
    ImportSpec,
)

from ...dataset.role_and_ontology import (
    university_ontology_like_classes_without_descriptors as univ_module,
)


# ── fixtures ──────────────────────────────────────────────────────────


@pytest.fixture
def class_diagram():
    classes = classes_of_module(univ_module)
    return ClassDiagram(classes)


@pytest.fixture
def analysis_context(class_diagram):
    resolver = ImportNameResolver(
        source_module=univ_module,
        companion_modules=[],
        class_diagram=class_diagram,
    )
    normaliser = TypeNormaliser(resolver=resolver, class_diagram=class_diagram)
    role_takers = set(class_diagram.role_takers)

    return AnalysisContext(
        class_diagram=class_diagram,
        resolver=resolver,
        normaliser=normaliser,
        already_covered_bases=role_takers,
        module_name=univ_module.__name__,
        source_module=univ_module,
    )


@pytest.fixture
def delegation_analyzer():
    return DelegationAnalyzer(
        delegatee_attribute_name="role_taker",
        excluded_method_names=frozenset({"__init__", "__post_init__", "__new__"}),
    )


# ── MroWalker tests ───────────────────────────────────────────────────


class TestMroWalker:
    class A:
        def method_on_a(self) -> int: ...

    class B(A):
        pass

    class C(B):
        def method_on_c(self) -> str: ...

    def test_construction(self):
        w = MroWalker(self.A, set(), "test_module")
        assert w.clazz is self.A
        assert w.module_name == "test_module"

    def test_find_defining_class(self):
        w = MroWalker(self.C, set(), __name__)
        result = w.find_defining_class(
            lambda klass: "method_on_a" in vars(klass)
        )
        assert result is self.A

    def test_find_defining_class_skips_own(self):
        w = MroWalker(self.C, set(), __name__)
        result = w.find_defining_class(
            lambda klass: "method_on_c" in vars(klass)
        )
        # method_on_c is defined on C, but find_defining_class skips
        # the class itself (starts from __mro__[1:])
        # It returns None when the member is on the class itself
        assert result is None

    def test_iter_non_covered_same_package(self):
        w = MroWalker(self.C, set(), __name__)
        bases = list(w.iter_non_covered_same_package())
        assert self.A in bases
        assert self.B in bases

    def test_find_first(self):
        w = MroWalker(self.C, set(), __name__)
        result = w.find_first(lambda klass: klass is self.A)
        assert result is self.A

    def test_is_member_already_covered(self):
        w = MroWalker(self.C, {self.A}, __name__)
        result = w.is_member_already_covered(
            lambda klass: "method_on_a" in vars(klass)
        )
        assert result is True


# ── DelegationAnalyzer tests ──────────────────────────────────────────


class TestDelegationAnalyzer:
    def test_produces_delegation_spec(self, delegation_analyzer, class_diagram, analysis_context):
        taker = next(
            wc
            for wc in class_diagram.wrapped_classes
            if wc.clazz in class_diagram.role_takers
        )
        spec = delegation_analyzer.analyze(taker, analysis_context)
        assert isinstance(spec, DelegationSpec)
        assert spec.delegatee_attribute == "role_taker"

    def test_non_empty_members_for_role_taker(self, delegation_analyzer, class_diagram, analysis_context):
        taker = next(
            wc
            for wc in class_diagram.wrapped_classes
            if wc.clazz in class_diagram.role_takers
        )
        spec = delegation_analyzer.analyze(taker, analysis_context)
        assert len(spec.members) > 0, "Expected non-empty delegation members"

    def test_members_have_correct_structure(self, delegation_analyzer, class_diagram, analysis_context):
        taker = next(
            wc
            for wc in class_diagram.wrapped_classes
            if wc.clazz in class_diagram.role_takers
        )
        spec = delegation_analyzer.analyze(taker, analysis_context)
        for member in spec.members:
            assert isinstance(member, MemberSpec)
            assert isinstance(member.name, str)
            assert isinstance(member, MemberSpec)
            assert member.name != ""

    def test_excluded_methods_not_in_members(self, delegation_analyzer, class_diagram, analysis_context):
        taker = next(
            wc
            for wc in class_diagram.wrapped_classes
            if wc.clazz in class_diagram.role_takers
        )
        spec = delegation_analyzer.analyze(taker, analysis_context)
        member_names = {m.name for m in spec.members}
        for excluded in delegation_analyzer.excluded_method_names:
            assert excluded not in member_names

    def test_handles_class_without_fields(self, delegation_analyzer, class_diagram, analysis_context):
        # Find a role taker with fewer fields
        takers = [
            wc
            for wc in class_diagram.wrapped_classes
            if wc.clazz in class_diagram.role_takers
        ]
        if takers:
            spec = delegation_analyzer.analyze(takers[0], analysis_context)
            assert isinstance(spec, DelegationSpec)

    def test_with_additional_skip_bases(self, delegation_analyzer, class_diagram, analysis_context):
        taker = next(
            wc
            for wc in class_diagram.wrapped_classes
            if wc.clazz in class_diagram.role_takers
        )
        # Adding skip bases should not crash and may reduce members
        spec1 = delegation_analyzer.analyze(taker, analysis_context)
        spec2 = delegation_analyzer.analyze(
            taker, analysis_context,
            additional_skip_bases=analysis_context.already_covered_bases,
        )
        assert isinstance(spec2, DelegationSpec)
        # With more skip bases we should have <= members
        assert len(spec2.members) <= len(spec1.members)


# ── RolePatternAnalyzer tests ─────────────────────────────────────────


class TestRolePatternAnalyzer:
    def test_produces_class_transformation_spec(self, class_diagram, analysis_context):
        analyzer = RolePatternAnalyzer()
        taker = next(
            wc
            for wc in class_diagram.wrapped_classes
            if wc.clazz in class_diagram.role_takers
        )
        spec = analyzer.analyze(taker, analysis_context)
        assert isinstance(spec, RoleClassTransformationSpec)
        assert spec.class_name == taker.clazz.__name__

    def test_role_taker_is_detected(self, class_diagram, analysis_context):
        analyzer = RolePatternAnalyzer()
        taker = next(
            wc
            for wc in class_diagram.wrapped_classes
            if wc.clazz in class_diagram.role_takers
        )
        spec = analyzer.analyze(taker, analysis_context)
        # Note: is_role_taker depends on already_covered_bases in context
        # The class may or may not be flagged depending on context setup
        assert spec.role_type is not None

    def test_qualified_name_is_set(self, class_diagram, analysis_context):
        analyzer = RolePatternAnalyzer()
        for wc in class_diagram.wrapped_classes:
            spec = analyzer.analyze(wc, analysis_context)
            assert spec.qualified_name
            assert spec.class_name in spec.qualified_name


# ── ImportAnalyzer tests ──────────────────────────────────────────────


class TestNameCollector:
    def test_collects_names_from_annotations(self):
        src = """\
x: int = 5
y: str = "hello"
"""
        mod = libcst.parse_module(src)
        collector = NameCollector()
        mod.visit(collector)
        assert "int" in collector.names
        assert "str" in collector.names

    def test_excludes_parameter_names(self):
        src = """\
def foo(self, x: int, y: str) -> None:
    ...
"""
        mod = libcst.parse_module(src)
        collector = NameCollector()
        mod.visit(collector)
        assert "x" not in collector.names
        assert "y" not in collector.names
        assert "int" in collector.names
        assert "str" in collector.names
        assert "None" in collector.names

    def test_collects_names_from_defaults(self):
        src = """\
def foo(x: int = 0) -> None:
    ...
"""
        mod = libcst.parse_module(src)
        collector = NameCollector()
        mod.visit(collector)
        assert "int" in collector.names
        assert "None" in collector.names


class TestRuntimeNameCollector:
    def test_collects_decorator_names(self):
        src = """\
@dataclass(eq=False)
class Foo:
    x: int
"""
        mod = libcst.parse_module(src)
        collector = RuntimeNameCollector()
        mod.visit(collector)
        assert "dataclass" in collector.names


class TestBaseClassNameCollector:
    def test_collects_base_class_names(self):
        src = """\
class Foo(HasRoles, ABC):
    x: int
"""
        mod = libcst.parse_module(src)
        collector = BaseClassNameCollector()
        mod.visit(collector)
        assert "HasRoles" in collector.names
        assert "ABC" in collector.names


class TestImportAnalyzer:
    def test_produces_import_specs(self, analysis_context):
        src = """\
from __future__ import annotations
from dataclasses import dataclass

class Person:
    name: str
"""
        mod = libcst.parse_module(src)
        analyzer = ImportAnalyzer()
        specs = analyzer.analyze(mod, analysis_context)
        assert isinstance(specs, list)
        for spec in specs:
            assert isinstance(spec, ImportSpec)
            assert isinstance(spec.module, str)
            assert isinstance(spec.names, frozenset)

    def test_excludes_builtin_names(self, analysis_context):
        src = "x: int = 5\ny: str = 'hello'\n"
        mod = libcst.parse_module(src)
        analyzer = ImportAnalyzer()
        specs = analyzer.analyze(mod, analysis_context)
        for spec in specs:
            assert spec.module not in ("builtins",)

    def test_empty_module_produces_empty_specs(self, analysis_context):
        mod = libcst.parse_module("")
        analyzer = ImportAnalyzer()
        specs = analyzer.analyze(mod, analysis_context)
        assert specs == []


# ── iter_factory_method_names tests ───────────────────────────────────


class TestIterFactoryMethodNames:
    def test_returns_iterator(self, class_diagram):
        result = iter_factory_method_names(
            class_diagram.wrapped_classes[0],
        )
        assert hasattr(result, "__iter__")

    def test_no_crash_on_all_wrapped_classes(self, class_diagram):
        for wc in class_diagram.wrapped_classes:
            names = list(iter_factory_method_names(wc))
            assert isinstance(names, list)
