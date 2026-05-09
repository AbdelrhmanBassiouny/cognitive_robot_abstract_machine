import pytest
import libcst as cst

from krrood.patterns.role.role_transformer import RoleTransformer, TransformationMode

TRANSFORMED = TransformationMode.TRANSFORMED.value
from test.krrood_test.dataset.role_and_ontology import shared_base_takers


@pytest.fixture
def mixin_source():
    transformer = RoleTransformer(shared_base_takers, file_name_prefix=TRANSFORMED)
    _, src = transformer.transform()[shared_base_takers]
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


def test_base_class_mixin_is_generated(mixin_source):
    """A DelegatorForSharedBase class must be emitted for the shared ancestor."""
    assert "class DelegatorForSharedBase" in mixin_source


def test_shared_methods_not_duplicated(mixin_source):
    """Methods from SharedBase appear exactly once (in DelegatorForSharedBase)."""
    assert mixin_source.count("def shared_method") == 1
    assert mixin_source.count("def another_shared_method") == 1


def test_shared_field_property_in_base_mixin_only(mixin_source):
    """shared_field property is in DelegatorForSharedBase and not in the taker-specific DelegatorFors."""
    classes = _classes(mixin_source)
    assert "shared_field" in _method_names(classes["DelegatorForSharedBase"])
    assert "shared_field" not in _method_names(classes["DelegatorForExclusiveTakerA"])
    assert "shared_field" not in _method_names(classes["DelegatorForExclusiveTakerB"])


def test_single_base_mixin_per_base(mixin_source):
    """DelegatorForSharedBase is defined exactly once."""
    assert mixin_source.count("class DelegatorForSharedBase") == 1


def test_taker_rolefor_inherits_base_mixin(mixin_source):
    """Both DelegatorForExclusiveTakerA and DelegatorForExclusiveTakerB inherit from DelegatorForSharedBase."""
    classes = _classes(mixin_source)
    for name in ("DelegatorForExclusiveTakerA", "DelegatorForExclusiveTakerB"):
        bases = _base_names(classes[name])
        assert "DelegatorForSharedBase" in bases, (
            f"{name} does not inherit DelegatorForSharedBase; got bases: {bases}"
        )


def test_taker_direct_methods_stay_in_taker_rolefor(mixin_source):
    """taker_a_only_method is in DelegatorForExclusiveTakerA, not in DelegatorForSharedBase."""
    classes = _classes(mixin_source)
    assert "taker_a_only_method" in _method_names(classes["DelegatorForExclusiveTakerA"])
    assert "taker_b_only_method" in _method_names(classes["DelegatorForExclusiveTakerB"])
    shared_methods = _method_names(classes["DelegatorForSharedBase"])
    assert "taker_a_only_method" not in shared_methods
    assert "taker_b_only_method" not in shared_methods


def test_shared_methods_in_base_mixin(mixin_source):
    """shared_method and another_shared_method are in DelegatorForSharedBase."""
    classes = _classes(mixin_source)
    shared_methods = _method_names(classes["DelegatorForSharedBase"])
    assert "shared_method" in shared_methods
    assert "another_shared_method" in shared_methods


def test_base_mixin_has_abstract_role_taker(mixin_source):
    """DelegatorForSharedBase declares an abstract role_taker property."""
    classes = _classes(mixin_source)
    assert "delegatee" in _method_names(classes["DelegatorForSharedBase"])


def test_base_mixin_emitted_before_taker_rolefors(mixin_source):
    """DelegatorForSharedBase appears before DelegatorForExclusiveTakerA in the source."""
    assert mixin_source.index("class DelegatorForSharedBase") < mixin_source.index(
        "class DelegatorForExclusiveTakerA"
    )
