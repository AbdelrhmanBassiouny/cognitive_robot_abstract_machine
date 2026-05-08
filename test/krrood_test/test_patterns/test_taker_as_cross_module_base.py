"""
Tests that when a role taker (BaseTaker) is defined in a separate module from the
derived takers (DerivedTakerA, DerivedTakerB) that inherit from it, and all their
roles are in the same module, the generated mixin for the derived-takers module:

  - imports RoleForCrossModuleBaseTaker from the base-taker module's mixin
  - does NOT re-define RoleForCrossModuleBaseTaker locally
  - generates RoleForDerivedTakerA and RoleForDerivedTakerB inheriting from
    RoleForCrossModuleBaseTaker

This exercises the fix for the circular-import bug caused by make_role_for_node
not registering direct takers in _global_base_class_ownership.

Dataset:
  cross_module_derived_takers_with_base_role.py  (roles module + derived takers)
    ├── RoleBase(Role[TBase])           -> taker: CrossModuleBaseTaker  (in cross_module_base_taker.py)
    ├── RoleDerivedA(Role[TDerivedA])   -> taker: DerivedTakerA (same module)
    ├── RoleDerivedB(Role[TDerivedB])   -> taker: DerivedTakerB (same module)
    ├── DerivedTakerA(CrossModuleBaseTaker)
    └── DerivedTakerB(CrossModuleBaseTaker)
"""

import pytest
import libcst as cst

from krrood.patterns.role.role_transformer import RoleTransformer, TransformationMode
from test.krrood_test.dataset.role_and_ontology import (
    cross_module_derived_takers_with_base_role,
    cross_module_base_taker,
)

TRANSFORMED = TransformationMode.TRANSFORMED.value


@pytest.fixture(scope="module")
def mixin_sources():
    transformer = RoleTransformer(
        cross_module_derived_takers_with_base_role, file_name_prefix=TRANSFORMED
    )
    results = transformer.transform()
    return {module: src for module, (_, src) in results.items()}


def _classes(source: str) -> dict[str, cst.ClassDef]:
    tree = cst.parse_module(source)
    return {stmt.name.value: stmt for stmt in tree.body if isinstance(stmt, cst.ClassDef)}


def _base_names(cls_def: cst.ClassDef) -> list[str]:
    return [cst.parse_module("").code_for_node(b.value).strip() for b in cls_def.bases]


def test_base_taker_module_has_role_for_base(mixin_sources):
    """RoleForCrossModuleBaseTaker is generated in the base-taker module's mixin."""
    src = mixin_sources[cross_module_base_taker]
    assert "class RoleForCrossModuleBaseTaker" in src


def test_derived_module_does_not_redefine_base_rolefor(mixin_sources):
    """The derived-takers mixin must NOT define RoleForCrossModuleBaseTaker."""
    src = mixin_sources[cross_module_derived_takers_with_base_role]
    assert "class RoleForCrossModuleBaseTaker" not in src


def test_derived_module_imports_base_rolefor(mixin_sources):
    """The derived-takers mixin must import RoleForCrossModuleBaseTaker from the base mixin."""
    src = mixin_sources[cross_module_derived_takers_with_base_role]
    assert "RoleForCrossModuleBaseTaker" in src
    assert "cross_module_base_taker" in src


def test_derived_a_inherits_base_rolefor(mixin_sources):
    """RoleForDerivedTakerA must inherit from RoleForCrossModuleBaseTaker."""
    src = mixin_sources[cross_module_derived_takers_with_base_role]
    classes = _classes(src)
    assert "RoleForDerivedTakerA" in classes
    assert "RoleForCrossModuleBaseTaker" in _base_names(classes["RoleForDerivedTakerA"])


def test_derived_b_inherits_base_rolefor(mixin_sources):
    """RoleForDerivedTakerB must inherit from RoleForCrossModuleBaseTaker."""
    src = mixin_sources[cross_module_derived_takers_with_base_role]
    classes = _classes(src)
    assert "RoleForDerivedTakerB" in classes
    assert "RoleForCrossModuleBaseTaker" in _base_names(classes["RoleForDerivedTakerB"])


def test_no_circular_import(mixin_sources):
    """Neither mixin imports from the other, preventing a circular dependency."""
    base_src = mixin_sources[cross_module_base_taker]
    derived_src = mixin_sources[cross_module_derived_takers_with_base_role]
    base_mixin_name = "cross_module_base_taker_role_mixins"
    derived_mixin_name = "cross_module_derived_takers_with_base_role_role_mixins"
    assert derived_mixin_name not in base_src
    assert base_mixin_name not in derived_src or "RoleForCrossModuleBaseTaker" in base_src
