"""
Tests for NameCollector and GeneratedModuleImportOrchestrator import generation.
"""

from __future__ import annotations

import libcst

from krrood.patterns.code_generation.import_orchestrator import NameCollector


# ── NameCollector ─────────────────────────────────────────────────────────────


class TestNameCollector:
    def _collect(self, source: str) -> set[str]:
        tree = libcst.parse_module(source)
        collector = NameCollector()
        tree.visit(collector)
        return collector.names

    def test_collects_type_annotation_in_param(self):
        names = self._collect("def f(x: MyType): pass\n")
        assert "MyType" in names

    def test_does_not_collect_param_name(self):
        names = self._collect("def f(entity: MyType): pass\n")
        assert "entity" not in names

    def test_collects_return_type(self):
        names = self._collect("def f() -> ReturnType: pass\n")
        assert "ReturnType" in names

    def test_collects_default_value_name(self):
        names = self._collect("def f(x: int = DEFAULT): pass\n")
        assert "DEFAULT" in names

    def test_does_not_collect_self(self):
        names = self._collect("def f(self): pass\n")
        assert "self" not in names

    def test_does_not_collect_cls(self):
        names = self._collect("def f(cls): pass\n")
        assert "cls" not in names

    def test_multiple_params_only_annotations_collected(self):
        names = self._collect(
            "def f(foo: TypeA, bar: TypeB, baz: TypeC): pass\n"
        )
        assert "TypeA" in names
        assert "TypeB" in names
        assert "TypeC" in names
        assert "foo" not in names
        assert "bar" not in names
        assert "baz" not in names

    def test_collects_names_in_function_body(self):
        names = self._collect("def f():\n    return SomeClass()\n")
        assert "SomeClass" in names

    def test_collects_base_class_name(self):
        names = self._collect("class Foo(BaseClass): pass\n")
        assert "BaseClass" in names

    def test_param_name_matching_import_not_collected(self):
        # Regression: parameter named 'entity' must not be collected even
        # when the source module exports a symbol with the same name.
        names = self._collect(
            "def _offline_root_T_entity(self, entity: KinematicStructureEntity)"
            " -> Matrix: pass\n"
        )
        assert "entity" not in names
        assert "KinematicStructureEntity" in names
        assert "Matrix" in names
