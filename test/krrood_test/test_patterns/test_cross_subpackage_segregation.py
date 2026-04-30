import pytest
import libcst as cst

from krrood.patterns.role.role_transformer import RoleTransformer, TransformationMode

TRANSFORMED = TransformationMode.TRANSFORMED.value
from test.krrood_test.dataset.role_and_ontology import cross_subpackage_takers


@pytest.fixture
def mixin_source():
    transformer = RoleTransformer(cross_subpackage_takers, file_name_prefix=TRANSFORMED)
    _, src = transformer.transform()[cross_subpackage_takers]
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
    """A RoleForCrossSubpackageBase class must be emitted for the sibling-subpackage ancestor."""
    assert "class RoleForCrossSubpackageBase" in mixin_source


def test_shared_method_not_duplicated(mixin_source):
    """sub_method appears exactly once (in RoleForCrossSubpackageBase, not in each taker RoleFor)."""
    assert mixin_source.count("def sub_method") == 1


def test_shared_field_in_base_mixin_only(mixin_source):
    """sub_field property is in RoleForCrossSubpackageBase and not in taker-specific RoleFors."""
    classes = _classes(mixin_source)
    assert "sub_field" in _method_names(classes["RoleForCrossSubpackageBase"])
    assert "sub_field" not in _method_names(classes["RoleForTakerP"])
    assert "sub_field" not in _method_names(classes["RoleForTakerQ"])


def test_single_base_mixin_per_base(mixin_source):
    """RoleForCrossSubpackageBase is defined exactly once."""
    assert mixin_source.count("class RoleForCrossSubpackageBase") == 1


def test_taker_rolefors_inherit_base_mixin(mixin_source):
    """Both RoleForTakerP and RoleForTakerQ inherit from RoleForCrossSubpackageBase."""
    classes = _classes(mixin_source)
    for name in ("RoleForTakerP", "RoleForTakerQ"):
        bases = _base_names(classes[name])
        assert "RoleForCrossSubpackageBase" in bases, (
            f"{name} does not inherit RoleForCrossSubpackageBase; got bases: {bases}"
        )


def test_taker_only_methods_stay_in_taker(mixin_source):
    """taker_p_only_method stays in RoleForTakerP; taker_q_only_method stays in RoleForTakerQ."""
    classes = _classes(mixin_source)
    assert "taker_p_only_method" in _method_names(classes["RoleForTakerP"])
    assert "taker_q_only_method" in _method_names(classes["RoleForTakerQ"])
    shared_methods = _method_names(classes["RoleForCrossSubpackageBase"])
    assert "taker_p_only_method" not in shared_methods
    assert "taker_q_only_method" not in shared_methods


def test_base_mixin_has_abstract_role_taker(mixin_source):
    """RoleForCrossSubpackageBase declares an abstract role_taker property."""
    classes = _classes(mixin_source)
    assert "role_taker" in _method_names(classes["RoleForCrossSubpackageBase"])


def test_base_mixin_emitted_before_taker_rolefors(mixin_source):
    """RoleForCrossSubpackageBase appears before RoleForTakerP in the source."""
    assert mixin_source.index("class RoleForCrossSubpackageBase") < mixin_source.index(
        "class RoleForTakerP"
    )


def test_cross_subpackage_base_import_present(mixin_source):
    """The generated mixin imports CrossSubpackageBase from its sibling-subpackage module."""
    assert "CrossSubpackageBase" in mixin_source
    assert "cross_subpackage_base" in mixin_source
