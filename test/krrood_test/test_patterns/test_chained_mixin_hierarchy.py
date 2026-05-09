"""
Tests that DelegatorFor classes produced from a chain of non-taker mixin base classes
mirror the inheritance hierarchy instead of being all listed flat.

Dataset: chained_mixin_takers.py
    BaseA → ChildA → GrandchildA (role taker)

Expected mixin hierarchy:
    DelegatorForBaseA(ABC)
    DelegatorForChildA(DelegatorForBaseA, ABC)
    DelegatorForGrandchildA(DelegatorForChildA, ABC)   # NOT listing DelegatorForBaseA directly
"""

import pytest
import libcst as cst

from krrood.patterns.role.role_transformer import RoleTransformer, TransformationMode

TRANSFORMED = TransformationMode.TRANSFORMED.value
from test.krrood_test.dataset.role_and_ontology import chained_mixin_takers


@pytest.fixture(scope="module")
def mixin_source():
    transformer = RoleTransformer(chained_mixin_takers, file_name_prefix=TRANSFORMED)
    _, src = transformer.transform()[chained_mixin_takers]
    return src


def _classes(source: str) -> dict[str, cst.ClassDef]:
    tree = cst.parse_module(source)
    return {stmt.name.value: stmt for stmt in tree.body if isinstance(stmt, cst.ClassDef)}


def _base_names(cls_def: cst.ClassDef) -> list[str]:
    return [cst.parse_module("").code_for_node(b.value).strip() for b in cls_def.bases]


def _method_names(cls_def: cst.ClassDef) -> set[str]:
    return {stmt.name.value for stmt in cls_def.body.body if isinstance(stmt, cst.FunctionDef)}


# ---------------------------------------------------------------------------
# Existence
# ---------------------------------------------------------------------------


def test_all_rolefor_classes_generated(mixin_source):
    classes = _classes(mixin_source)
    assert "DelegatorForBaseA" in classes
    assert "DelegatorForChildA" in classes
    assert "DelegatorForGrandchildA" in classes


# ---------------------------------------------------------------------------
# Hierarchical bases
# ---------------------------------------------------------------------------


def test_base_rolefor_has_only_abc(mixin_source):
    """DelegatorForBaseA is the root: its only base should be ABC."""
    classes = _classes(mixin_source)
    bases = _base_names(classes["DelegatorForBaseA"])
    assert bases == ["ABC"], f"Expected ['ABC'], got {bases}"


def test_child_rolefor_inherits_base(mixin_source):
    """DelegatorForChildA must list DelegatorForBaseA as a base (not duplicate its methods)."""
    classes = _classes(mixin_source)
    bases = _base_names(classes["DelegatorForChildA"])
    assert "DelegatorForBaseA" in bases, f"DelegatorForChildA bases: {bases}"


def test_grandchild_rolefor_inherits_child_not_base_directly(mixin_source):
    """DelegatorForGrandchildA lists DelegatorForChildA but NOT DelegatorForBaseA (covered transitively)."""
    classes = _classes(mixin_source)
    bases = _base_names(classes["DelegatorForGrandchildA"])
    assert "DelegatorForChildA" in bases, f"DelegatorForGrandchildA bases: {bases}"
    assert "DelegatorForBaseA" not in bases, (
        f"DelegatorForBaseA should be transitively inherited, not listed directly; got: {bases}"
    )


def test_topological_order(mixin_source):
    """DelegatorForBaseA must appear before DelegatorForChildA, which must appear before DelegatorForGrandchildA."""
    base_pos = mixin_source.index("class DelegatorForBaseA")
    child_pos = mixin_source.index("class DelegatorForChildA")
    grand_pos = mixin_source.index("class DelegatorForGrandchildA")
    assert base_pos < child_pos < grand_pos, (
        f"Wrong order: DelegatorForBaseA at {base_pos}, DelegatorForChildA at {child_pos}, "
        f"DelegatorForGrandchildA at {grand_pos}"
    )


# ---------------------------------------------------------------------------
# Method placement — no duplication across the hierarchy
# ---------------------------------------------------------------------------


def test_base_method_only_in_base_rolefor(mixin_source):
    """base_method is defined on BaseA and must appear only in DelegatorForBaseA."""
    classes = _classes(mixin_source)
    assert "base_method" in _method_names(classes["DelegatorForBaseA"])
    assert "base_method" not in _method_names(classes["DelegatorForChildA"])
    assert "base_method" not in _method_names(classes["DelegatorForGrandchildA"])


def test_child_method_only_in_child_rolefor(mixin_source):
    """child_method is defined on ChildA and must appear only in DelegatorForChildA."""
    classes = _classes(mixin_source)
    assert "child_method" in _method_names(classes["DelegatorForChildA"])
    assert "child_method" not in _method_names(classes["DelegatorForBaseA"])
    assert "child_method" not in _method_names(classes["DelegatorForGrandchildA"])


def test_grandchild_method_only_in_grandchild_rolefor(mixin_source):
    """grandchild_method is defined on GrandchildA and must appear only in DelegatorForGrandchildA."""
    classes = _classes(mixin_source)
    assert "grandchild_method" in _method_names(classes["DelegatorForGrandchildA"])
    assert "grandchild_method" not in _method_names(classes["DelegatorForBaseA"])
    assert "grandchild_method" not in _method_names(classes["DelegatorForChildA"])


def test_grandchild_rolefor_has_abstract_role_taker(mixin_source):
    """DelegatorForGrandchildA must declare an abstract role_taker property."""
    classes = _classes(mixin_source)
    assert "delegatee" in _method_names(classes["DelegatorForGrandchildA"])


def test_each_segregated_rolefor_has_abstract_role_taker(mixin_source):
    """Both segregated DelegatorFor classes must declare an abstract role_taker property."""
    classes = _classes(mixin_source)
    assert "delegatee" in _method_names(classes["DelegatorForBaseA"])
    assert "delegatee" in _method_names(classes["DelegatorForChildA"])
