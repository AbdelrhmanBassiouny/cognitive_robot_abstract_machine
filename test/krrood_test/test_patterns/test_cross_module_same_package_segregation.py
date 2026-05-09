import pytest
import libcst as cst

from krrood.patterns.role.role_transformer import RoleTransformer, TransformationMode

TRANSFORMED = TransformationMode.TRANSFORMED.value
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
    """A DelegatorForCrossModuleBase class must be emitted for the cross-module ancestor."""
    assert "class DelegatorForCrossModuleBase" in mixin_source


def test_shared_method_not_duplicated(mixin_source):
    """cross_method appears exactly once (in DelegatorForCrossModuleBase)."""
    assert mixin_source.count("def cross_method") == 1


def test_shared_field_in_base_mixin_only(mixin_source):
    """cross_field property is in DelegatorForCrossModuleBase and not in taker-specific DelegatorFors."""
    classes = _classes(mixin_source)
    assert "cross_field" in _method_names(classes["DelegatorForCrossModuleBase"])
    assert "cross_field" not in _method_names(classes["DelegatorForTakerX"])
    assert "cross_field" not in _method_names(classes["DelegatorForTakerY"])


def test_single_base_mixin_per_base(mixin_source):
    """DelegatorForCrossModuleBase is defined exactly once."""
    assert mixin_source.count("class DelegatorForCrossModuleBase") == 1


def test_taker_rolefors_inherit_base_mixin(mixin_source):
    """Both DelegatorForTakerX and DelegatorForTakerY inherit from DelegatorForCrossModuleBase."""
    classes = _classes(mixin_source)
    for name in ("DelegatorForTakerX", "DelegatorForTakerY"):
        bases = _base_names(classes[name])
        assert "DelegatorForCrossModuleBase" in bases, (
            f"{name} does not inherit DelegatorForCrossModuleBase; got bases: {bases}"
        )


def test_taker_only_methods_stay_in_taker(mixin_source):
    """taker_x_only_method stays in DelegatorForTakerX; taker_y_only_method stays in DelegatorForTakerY."""
    classes = _classes(mixin_source)
    assert "taker_x_only_method" in _method_names(classes["DelegatorForTakerX"])
    assert "taker_y_only_method" in _method_names(classes["DelegatorForTakerY"])
    shared_methods = _method_names(classes["DelegatorForCrossModuleBase"])
    assert "taker_x_only_method" not in shared_methods
    assert "taker_y_only_method" not in shared_methods


def test_base_mixin_has_abstract_role_taker(mixin_source):
    """DelegatorForCrossModuleBase declares an abstract role_taker property."""
    classes = _classes(mixin_source)
    assert "delegatee" in _method_names(classes["DelegatorForCrossModuleBase"])


def test_base_mixin_emitted_before_taker_rolefors(mixin_source):
    """DelegatorForCrossModuleBase appears before DelegatorForTakerX in the source."""
    assert mixin_source.index("class DelegatorForCrossModuleBase") < mixin_source.index(
        "class DelegatorForTakerX"
    )


def test_cross_module_base_import_present(mixin_source):
    """The generated mixin imports CrossModuleBase from its original module."""
    assert "CrossModuleBase" in mixin_source
    assert "cross_module_shared_base" in mixin_source
