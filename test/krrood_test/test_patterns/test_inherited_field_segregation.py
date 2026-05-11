"""
Tests that a dataclass field defined on a grandparent mixin is delegated in the
DelegatorFor for the grandparent, not in the DelegatorFor for a taker that merely inherits
it transitively.

Dataset: inherited_field_takers.py
    FieldOrigin (defines shared_field)
        └─ IntermediateMixin  (inherits shared_field, no re-annotation)
               ├─ TakerA      (role taker – adds taker_a_field)
               └─ TakerB      (role taker – adds taker_b_field)

Expected mixin output:
    DelegatorForFieldOrigin      – contains `shared_field` property
    DelegatorForIntermediateMixin(DelegatorForFieldOrigin)  – no duplicate shared_field
    DelegatorForTakerA(DelegatorForIntermediateMixin)       – contains taker_a_field
    DelegatorForTakerB(DelegatorForIntermediateMixin)       – contains taker_b_field
"""

import pytest
import libcst as cst

from krrood.patterns.role.role_transformer import RoleTransformer, TransformationMode

TRANSFORMED = TransformationMode.TRANSFORMED.value
from ..dataset.role_and_ontology import inherited_field_takers


@pytest.fixture(scope="module")
def mixin_source():
    transformer = RoleTransformer(inherited_field_takers, file_name_prefix=TRANSFORMED)
    _, src = transformer.transform()[inherited_field_takers]
    return src


def _classes(source: str) -> dict[str, cst.ClassDef]:
    tree = cst.parse_module(source)
    return {
        stmt.name.value: stmt for stmt in tree.body if isinstance(stmt, cst.ClassDef)
    }


def _method_names(cls_def: cst.ClassDef) -> set[str]:
    return {
        stmt.name.value
        for stmt in cls_def.body.body
        if isinstance(stmt, cst.FunctionDef)
    }


def _base_names(cls_def: cst.ClassDef) -> list[str]:
    return [cst.parse_module("").code_for_node(b.value).strip() for b in cls_def.bases]


def test_rolefor_classes_generated(mixin_source):
    classes = _classes(mixin_source)
    assert "DelegatorForFieldOrigin" in classes
    assert "DelegatorForIntermediateMixin" in classes
    assert "DelegatorForTakerA" in classes
    assert "DelegatorForTakerB" in classes


def test_shared_field_only_in_grandparent_rolefor(mixin_source):
    """shared_field must be delegated in DelegatorForFieldOrigin, not in TakerA/B DelegatorFors."""
    classes = _classes(mixin_source)
    assert "shared_field" in _method_names(classes["DelegatorForFieldOrigin"])
    assert "shared_field" not in _method_names(classes["DelegatorForIntermediateMixin"])
    assert "shared_field" not in _method_names(classes["DelegatorForTakerA"])
    assert "shared_field" not in _method_names(classes["DelegatorForTakerB"])


def test_taker_fields_in_correct_rolefors(mixin_source):
    classes = _classes(mixin_source)
    assert "taker_a_field" in _method_names(classes["DelegatorForTakerA"])
    assert "taker_b_field" in _method_names(classes["DelegatorForTakerB"])
    assert "taker_a_field" not in _method_names(classes["DelegatorForFieldOrigin"])
    assert "taker_b_field" not in _method_names(classes["DelegatorForFieldOrigin"])


def test_inheritance_chain(mixin_source):
    """DelegatorForTakerA and DelegatorForTakerB each inherit from DelegatorForIntermediateMixin."""
    classes = _classes(mixin_source)
    assert "DelegatorForIntermediateMixin" in _base_names(classes["DelegatorForTakerA"])
    assert "DelegatorForIntermediateMixin" in _base_names(classes["DelegatorForTakerB"])
    assert "DelegatorForFieldOrigin" in _base_names(
        classes["DelegatorForIntermediateMixin"]
    )


def test_shared_field_not_duplicated(mixin_source):
    classes = _classes(mixin_source)
    classes_with_shared_field = [
        name
        for name, cls_def in classes.items()
        if "shared_field" in _method_names(cls_def)
    ]
    assert classes_with_shared_field == ["DelegatorForFieldOrigin"]
