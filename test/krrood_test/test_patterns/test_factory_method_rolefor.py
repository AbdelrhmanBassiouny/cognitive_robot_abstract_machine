import pytest
import libcst as cst

from krrood.patterns.role.role_transformer import RoleTransformer
from test.krrood_test.dataset.role_and_ontology import factory_method_takers


@pytest.fixture(scope="module")
def mixin_source():
    transformer = RoleTransformer(factory_method_takers)
    _, src = transformer.transform()[factory_method_takers]
    return src


# ── CST helpers ──────────────────────────────────────────────────────


def _classes(source: str) -> dict[str, cst.ClassDef]:
    tree = cst.parse_module(source)
    return {
        stmt.name.value: stmt
        for stmt in tree.body
        if isinstance(stmt, cst.ClassDef)
    }


def _method_names(cls_def: cst.ClassDef) -> set[str]:
    return {
        stmt.name.value
        for stmt in cls_def.body.body
        if isinstance(stmt, cst.FunctionDef)
    }


def _methods(cls_def: cst.ClassDef) -> dict[str, cst.FunctionDef]:
    return {
        stmt.name.value: stmt
        for stmt in cls_def.body.body
        if isinstance(stmt, cst.FunctionDef)
    }


def _base_names(cls_def: cst.ClassDef) -> list[str]:
    return [
        cst.parse_module("").code_for_node(b.value).strip()
        for b in cls_def.bases
    ]


def _decorator_names(func_def: cst.FunctionDef) -> set[str]:
    return {
        d.decorator.value
        for d in func_def.decorators
        if isinstance(d.decorator, cst.Name)
    }


# ── Group 1: simple factory wrapping ─────────────────────────────────


def test_rolefor_has_factory_wrapper(mixin_source):
    """RoleFor<Person> has a create_adult method because Person defines it."""
    classes = _classes(mixin_source)
    assert "create_adult" in _method_names(classes["RoleForPerson"])


def test_rolefor_without_factory_has_no_wrappers(mixin_source):
    """RoleFor<PlainEntity> body is just the delegatee property."""
    classes = _classes(mixin_source)
    assert _method_names(classes["RoleForPlainEntity"]) == {"delegatee"}


def test_delegator_for_does_not_have_factory_method(mixin_source):
    """DelegatorFor<Person> does NOT contain create_adult — factory methods are
    skipped during delegation generation."""
    classes = _classes(mixin_source)
    assert "create_adult" not in _method_names(classes["DelegatorForPerson"])


# ── Group 2: factory wrapper structure ───────────────────────────────


def test_factory_wrapper_has_classmethod_decorator(mixin_source):
    """The wrapper method keeps the @classmethod decorator."""
    classes = _classes(mixin_source)
    create_adult = _methods(classes["RoleForPerson"])["create_adult"]
    assert "classmethod" in _decorator_names(create_adult)


def test_factory_wrapper_preserves_parameters(mixin_source):
    """Parameters (except cls) are preserved from the original factory method."""
    classes = _classes(mixin_source)
    create_adult = _methods(classes["RoleForPerson"])["create_adult"]
    param_names = [p.name.value for p in create_adult.params.params]
    assert param_names == ["cls", "name"]


def test_factory_wrapper_returns_self(mixin_source):
    """The return type is Self, preserved from the original."""
    classes = _classes(mixin_source)
    create_adult = _methods(classes["RoleForPerson"])["create_adult"]
    assert create_adult.returns is not None
    ret_annotation = create_adult.returns.annotation
    assert isinstance(ret_annotation, cst.Name) and ret_annotation.value == "Self"


def test_factory_wrapper_body_pattern(mixin_source):
    """The wrapper body follows the expected 4-statement pattern."""
    classes = _classes(mixin_source)
    create_adult = _methods(classes["RoleForPerson"])["create_adult"]
    body_text = cst.parse_module("").code_for_node(create_adult.body)
    assert "delegatee_type = cls.get_delegatee_type()" in body_text
    assert "role_taker = delegatee_type.create_adult(name)" in body_text
    assert "delegatee_attr = cls.delegatee_attribute_name()" in body_text
    assert "return cls(**{delegatee_attr: role_taker})" in body_text


# ── Group 3: inheritance chain ───────────────────────────────────────


def test_derived_rolefor_inherits_base_rolefor(mixin_source):
    """RoleFor<DerivedWorker> has RoleFor<BaseWorker> in its bases."""
    classes = _classes(mixin_source)
    assert "RoleForBaseWorker" in _base_names(classes["RoleForDerivedWorker"])


def test_base_rolefor_has_base_factory(mixin_source):
    """RoleFor<BaseWorker> contains create_intern."""
    classes = _classes(mixin_source)
    assert "create_intern" in _method_names(classes["RoleForBaseWorker"])


def test_derived_rolefor_has_own_factory(mixin_source):
    """RoleFor<DerivedWorker> contains create_manager."""
    classes = _classes(mixin_source)
    assert "create_manager" in _method_names(classes["RoleForDerivedWorker"])


def test_derived_rolefor_does_not_duplicate_base_factory(mixin_source):
    """RoleFor<DerivedWorker> does NOT define create_intern — it inherits it
    from RoleFor<BaseWorker>."""
    classes = _classes(mixin_source)
    assert "create_intern" not in _method_names(classes["RoleForDerivedWorker"])


def test_base_rolefor_does_not_have_derived_factory(mixin_source):
    """RoleFor<BaseWorker> does NOT contain create_manager."""
    classes = _classes(mixin_source)
    assert "create_manager" not in _method_names(classes["RoleForBaseWorker"])
