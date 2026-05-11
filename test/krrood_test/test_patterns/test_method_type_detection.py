from __future__ import annotations
import inspect
from textwrap import dedent
from unittest.mock import MagicMock

import libcst as cst
from typing_extensions import Self, Any

from krrood.patterns.code_generation.delegation_generator import DelegationGenerator
from krrood.patterns.code_generation.libcst_node_factory import LibCSTNodeFactory
from krrood.patterns.role.meta_data import MethodType


class Taker:
    """Delegatee class with normal, static, class, and factory methods."""

    def normal_method(self, x: int) -> str:
        return str(x)

    @staticmethod
    def static_method(data: str) -> int:
        return len(data)

    @classmethod
    def class_method(cls, path: str) -> Any:
        return cls()

    @classmethod
    def factory_method(cls) -> Self:
        return cls()


def test_method_type_detection():
    """_get_method_type correctly classifies NORMAL, CLASS_METHOD, and FACTORY_METHOD."""
    node_factory = LibCSTNodeFactory()
    type_normaliser = MagicMock()
    generator = DelegationGenerator(
        node_factory=node_factory,
        delegatee_attribute_name="delegatee",
        type_normaliser=type_normaliser,
    )

    cases = [
        ("normal_method", MethodType.NORMAL),
        ("static_method", MethodType.STATIC_METHOD),
        ("class_method", MethodType.CLASS_METHOD),
        ("factory_method", MethodType.FACTORY_METHOD),
    ]

    for method_name, expected_type in cases:
        method_obj = getattr(Taker, method_name)
        source = dedent(inspect.getsource(method_obj))
        method_node = cst.parse_module(source).body[0]
        assert isinstance(method_node, cst.FunctionDef)

        detected_type = generator._get_method_type(method_obj, method_node)
        assert (
            detected_type == expected_type
        ), f"Failed for {method_name}: expected {expected_type}, got {detected_type}"


def test_factory_method_skipped():
    """make_delegation_method_node returns None for factory methods."""
    node_factory = LibCSTNodeFactory()
    type_normaliser = MagicMock()
    generator = DelegationGenerator(
        node_factory=node_factory,
        delegatee_attribute_name="delegatee",
        type_normaliser=type_normaliser,
    )

    result = generator.make_delegation_method_node(
        "factory_method", Taker.factory_method, Taker
    )
    assert result is None, "Factory method should return None (be skipped)"


def test_static_method_delegation_body():
    """Static method delegation strips @staticmethod and adds self as first param."""
    node_factory = LibCSTNodeFactory()
    type_normaliser = MagicMock()
    generator = DelegationGenerator(
        node_factory=node_factory,
        delegatee_attribute_name="delegatee",
        type_normaliser=type_normaliser,
    )

    result = generator.make_delegation_method_node(
        "static_method", Taker.static_method, Taker
    )
    assert result is not None, "Static method should produce a delegation node"

    # Should NOT have @staticmethod decorator
    decorator_names = [
        node_factory._get_decorator_name(d.decorator) for d in result.decorators
    ]
    assert "staticmethod" not in decorator_names, (
        "@staticmethod decorator should be stripped"
    )

    # First param should be 'self' (added by the transformer)
    assert result.params.params, "Method should have parameters"
    assert result.params.params[0].name.value == "self", (
        f"First param should be 'self', got '{result.params.params[0].name.value}'"
    )

    # Body should delegate via self.delegatee
    body_code = cst.parse_module("").code_for_node(result.body)
    assert "self.delegatee.static_method" in body_code, (
        f"Body should delegate to self.delegatee.static_method, got: {body_code}"
    )


def test_class_method_delegation_body():
    """Class method delegation uses self.delegatee.method(args) as instance method."""
    node_factory = LibCSTNodeFactory()
    type_normaliser = MagicMock()
    generator = DelegationGenerator(
        node_factory=node_factory,
        delegatee_attribute_name="delegatee",
        type_normaliser=type_normaliser,
    )

    result = generator.make_delegation_method_node(
        "class_method", Taker.class_method, Taker
    )
    assert result is not None, "Class method should produce a delegation node"

    # Should NOT have @classmethod decorator
    decorator_names = [
        node_factory._get_decorator_name(d.decorator) for d in result.decorators
    ]
    assert "classmethod" not in decorator_names, (
        "@classmethod decorator should be stripped"
    )

    # First param should be 'self', not 'cls'
    assert result.params.params, "Method should have parameters"
    assert result.params.params[0].name.value == "self", (
        f"First param should be 'self', got '{result.params.params[0].name.value}'"
    )

    # Body should delegate via self.delegatee
    body_code = cst.parse_module("").code_for_node(result.body)
    assert "self.delegatee.class_method" in body_code, (
        f"Body should delegate to self.delegatee.class_method, got: {body_code}"
    )
    assert "cls.get_delegatee_type" not in body_code, (
        "Should not use cls.get_delegatee_type()"
    )


def test_normal_method_delegation_body():
    """Normal method delegation is unchanged."""
    node_factory = LibCSTNodeFactory()
    type_normaliser = MagicMock()
    generator = DelegationGenerator(
        node_factory=node_factory,
        delegatee_attribute_name="delegatee",
        type_normaliser=type_normaliser,
    )

    result = generator.make_delegation_method_node(
        "normal_method", Taker.normal_method, Taker
    )
    assert result is not None, "Normal method should produce a delegation node"

    body_code = cst.parse_module("").code_for_node(result.body)
    assert "self.delegatee.normal_method" in body_code, (
        f"Body should delegate to self.delegatee.normal_method, got: {body_code}"
    )

    # Should still have 'self' as first param
    assert result.params.params[0].name.value == "self", (
        "First param should remain 'self'"
    )


if __name__ == "__main__":
    test_method_type_detection()
    test_factory_method_skipped()
    test_static_method_delegation_body()
    test_class_method_delegation_body()
    test_normal_method_delegation_body()
    print("All tests passed!")
