import pytest
import libcst as cst

from krrood.patterns.role.role_transformer import RoleTransformer, TRANSFORMED
from test.krrood_test.dataset.role_and_ontology import cross_module_takers


@pytest.fixture
def mixin_source():
    transformer = RoleTransformer(cross_module_takers, file_name_prefix=TRANSFORMED)
    _, src = transformer.transform()[cross_module_takers]
    return src


def _classes(source: str) -> dict[str, cst.ClassDef]:
    tree = cst.parse_module(source)
    return {stmt.name.value: stmt for stmt in tree.body if isinstance(stmt, cst.ClassDef)}


def _method_names(cls_def: cst.ClassDef) -> set[str]:
    return {stmt.name.value for stmt in cls_def.body.body if isinstance(stmt, cst.FunctionDef)}


def _base_names(cls_def: cst.ClassDef) -> list[str]:
    return [cst.parse_module("").code_for_node(b.value).strip() for b in cls_def.bases]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_base_mixin_generated(mixin_source):
    """A RoleForCrossModuleBase class must be emitted for the cross-module ancestor."""
    assert "class RoleForCrossModuleBase" in mixin_source


def test_shared_method_not_duplicated(mixin_source):
    """cross_method appears exactly once (in RoleForCrossModuleBase)."""
    assert mixin_source.count("def cross_method") == 1


def test_shared_field_in_base_mixin_only(mixin_source):
    """cross_field property is in RoleForCrossModuleBase and not in taker-specific RoleFors."""
    classes = _classes(mixin_source)
    assert "cross_field" in _method_names(classes["RoleForCrossModuleBase"])
    assert "cross_field" not in _method_names(classes["RoleForTakerX"])
    assert "cross_field" not in _method_names(classes["RoleForTakerY"])


def test_single_base_mixin_per_base(mixin_source):
    """RoleForCrossModuleBase is defined exactly once."""
    assert mixin_source.count("class RoleForCrossModuleBase") == 1


def test_taker_rolefors_inherit_base_mixin(mixin_source):
    """Both RoleForTakerX and RoleForTakerY inherit from RoleForCrossModuleBase."""
    classes = _classes(mixin_source)
    for name in ("RoleForTakerX", "RoleForTakerY"):
        bases = _base_names(classes[name])
        assert "RoleForCrossModuleBase" in bases, (
            f"{name} does not inherit RoleForCrossModuleBase; got bases: {bases}"
        )


def test_taker_only_methods_stay_in_taker(mixin_source):
    """taker_x_only_method stays in RoleForTakerX; taker_y_only_method stays in RoleForTakerY."""
    classes = _classes(mixin_source)
    assert "taker_x_only_method" in _method_names(classes["RoleForTakerX"])
    assert "taker_y_only_method" in _method_names(classes["RoleForTakerY"])
    shared_methods = _method_names(classes["RoleForCrossModuleBase"])
    assert "taker_x_only_method" not in shared_methods
    assert "taker_y_only_method" not in shared_methods


def test_base_mixin_has_abstract_role_taker(mixin_source):
    """RoleForCrossModuleBase declares an abstract role_taker property."""
    classes = _classes(mixin_source)
    assert "role_taker" in _method_names(classes["RoleForCrossModuleBase"])


def test_base_mixin_emitted_before_taker_rolefors(mixin_source):
    """RoleForCrossModuleBase appears before RoleForTakerX in the source."""
    assert mixin_source.index("class RoleForCrossModuleBase") < mixin_source.index(
        "class RoleForTakerX"
    )


def test_cross_module_base_import_present(mixin_source):
    """The generated mixin imports CrossModuleBase from its original module."""
    assert "CrossModuleBase" in mixin_source
    assert "cross_module_shared_base" in mixin_source
