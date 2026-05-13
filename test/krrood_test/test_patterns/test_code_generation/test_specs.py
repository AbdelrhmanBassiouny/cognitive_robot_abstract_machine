"""Tests for spec dataclasses in krrood.patterns.code_generation.specs."""

from __future__ import annotations

import pytest

from krrood.patterns.role.meta_data import RoleType
from krrood.patterns.code_generation.specs import (
    BaseClassSpec,
    ClassMethodSpec,
    ClassTransformationSpec,
    DelegationSpec,
    FactoryMethodSpec,
    FieldSpec,
    ImportSpec,
    MemberSpec,
    MethodSpec,
    ModuleTransformationSpec,
    ParameterSpec,
    PropertySpec,
    RoleClassTransformationSpec,
    StaticMethodSpec,
)


class TestMemberSpecHierarchy:
    def test_field_spec_is_member_spec(self):
        spec = FieldSpec(name="age", return_type="int")
        assert isinstance(spec, MemberSpec)
        assert spec.name == "age"

    def test_property_spec_is_member_spec(self):
        spec = PropertySpec(name="full_name", return_type="str")
        assert isinstance(spec, MemberSpec)

    def test_method_spec_is_member_spec(self):
        spec = MethodSpec(name="get_title", return_type="str")
        assert isinstance(spec, MemberSpec)
        assert spec.parameters == []
        assert spec.decorators == []

    def test_method_spec_with_parameters(self):
        params = [ParameterSpec(name="x", type_annotation="int")]
        spec = MethodSpec(name="add", return_type="int", parameters=params)
        assert len(spec.parameters) == 1

    def test_static_method_spec_is_method_spec(self):
        spec = StaticMethodSpec(name="factory", return_type="int")
        assert isinstance(spec, MethodSpec)
        assert isinstance(spec, MemberSpec)

    def test_class_method_spec_is_method_spec(self):
        spec = ClassMethodSpec(name="from_str", return_type="Self")
        assert isinstance(spec, MethodSpec)

    def test_factory_method_spec_is_class_method_spec(self):
        spec = FactoryMethodSpec(name="create", return_type="Self")
        assert isinstance(spec, ClassMethodSpec)
        assert isinstance(spec, MethodSpec)

    def test_field_spec_frozen(self):
        spec = FieldSpec(name="x")
        with pytest.raises(Exception):
            spec.name = "y"

    def test_method_spec_equality(self):
        a = MethodSpec(name="f", return_type="str")
        b = MethodSpec(name="f", return_type="str")
        assert a == b

    def test_different_types_not_equal(self):
        a = FieldSpec(name="f", return_type="str")
        b = MethodSpec(name="f", return_type="str")
        assert a != b


class TestParameterSpec:
    def test_minimal_construction(self):
        spec = ParameterSpec(name="self")
        assert spec.name == "self"
        assert spec.type_annotation is None
        assert spec.has_default is False

    def test_full_construction(self):
        spec = ParameterSpec(name="x", type_annotation="int", has_default=True)
        assert spec.name == "x"
        assert spec.type_annotation == "int"
        assert spec.has_default is True

    def test_equality(self):
        a = ParameterSpec(name="x", type_annotation="int")
        b = ParameterSpec(name="x", type_annotation="int")
        assert a == b

    def test_inequality(self):
        a = ParameterSpec(name="x")
        b = ParameterSpec(name="y")
        assert a != b

    def test_frozen(self):
        spec = ParameterSpec(name="x")
        with pytest.raises(Exception):
            spec.name = "y"

    def test_hashable(self):
        spec = ParameterSpec(name="x")
        assert hash(spec) is not None


class TestMemberSpec:
    def test_minimal_construction(self):
        spec = MethodSpec(name="get_name")
        assert spec.name == "get_name"
        assert spec.return_type is None
        assert spec.parameters == []
        assert spec.defining_class is None
        assert spec.decorators == []

    def test_with_return_type(self):
        spec = MethodSpec(name="get_name", return_type="str")
        assert spec.return_type == "str"

    def test_with_parameters(self):
        params = [ParameterSpec(name="x", type_annotation="int")]
        spec = MethodSpec(name="add", parameters=params)
        assert len(spec.parameters) == 1
        assert spec.parameters[0].name == "x"

    def test_with_defining_class(self):
        spec = MethodSpec(name="method", defining_class=str)
        assert spec.defining_class is str

    def test_with_decorators(self):
        spec = MethodSpec(name="attr", decorators=["abstractmethod"])
        assert "abstractmethod" in spec.decorators

    def test_frozen(self):
        spec = FieldSpec(name="x")
        with pytest.raises(Exception):
            spec.name = "y"

    def test_equality(self):
        a = MethodSpec(name="f", return_type="str")
        b = MethodSpec(name="f", return_type="str")
        assert a == b

    def test_inequality(self):
        a = FieldSpec(name="f")
        b = MethodSpec(name="f")
        assert a != b


class TestDelegationSpec:
    def test_minimal_construction(self):
        spec = DelegationSpec(delegatee_attribute="delegatee")
        assert spec.delegatee_attribute == "delegatee"
        assert spec.members == []
        assert spec.excluded_names == frozenset()

    def test_with_members(self):
        members = [
            MethodSpec(name="get_name", return_type="str"),
            FieldSpec(name="age", return_type="int"),
        ]
        spec = DelegationSpec(delegatee_attribute="role_taker", members=members)
        assert len(spec.members) == 2
        assert spec.members[0].name == "get_name"
        assert spec.members[1].name == "age"

    def test_with_excluded_names(self):
        spec = DelegationSpec(
            delegatee_attribute="delegatee",
            excluded_names=frozenset({"__init__", "__post_init__"}),
        )
        assert "__init__" in spec.excluded_names
        assert "__post_init__" in spec.excluded_names


class TestBaseClassSpec:
    def test_same_module_default(self):
        spec = BaseClassSpec(name="HasRoles")
        assert spec.name == "HasRoles"
        assert spec.module is None

    def test_cross_module(self):
        spec = BaseClassSpec(name="HasRoles", module="krrood.patterns.role")
        assert spec.module == "krrood.patterns.role"

    def test_equality(self):
        a = BaseClassSpec(name="ABC", module="abc")
        b = BaseClassSpec(name="ABC", module="abc")
        assert a == b


class TestClassTransformationSpec:
    def test_minimal_construction(self):
        spec = ClassTransformationSpec(
            class_name="Professor",
            qualified_name="uni.Professor",
        )
        assert spec.class_name == "Professor"
        assert spec.bases_to_add == []
        assert spec.delegation is None

    def test_with_delegation(self):
        delegation = DelegationSpec(
            delegatee_attribute="delegatee",
            members=[FieldSpec(name="name", return_type="str")],
        )
        spec = ClassTransformationSpec(
            class_name="Person",
            qualified_name="uni.Person",
            bases_to_add=[BaseClassSpec(name="HasRoles")],
            delegation=delegation,
        )
        assert len(spec.bases_to_add) == 1
        assert spec.delegation.delegatee_attribute == "delegatee"

    def test_is_frozen(self):
        spec = ClassTransformationSpec(class_name="X", qualified_name="p.X")
        with pytest.raises(Exception):
            spec.class_name = "Y"


class TestRoleClassTransformationSpec:
    def test_minimal_construction(self):
        spec = RoleClassTransformationSpec(
            class_name="Professor",
            qualified_name="uni.Professor",
        )
        from krrood.patterns.role.meta_data import RoleType
        assert spec.role_type == RoleType.NOT_A_ROLE
        assert spec.is_role_taker is False
        assert spec.is_role is False

    def test_role_taker_with_delegation(self):
        delegation = DelegationSpec(
            delegatee_attribute="delegatee",
            members=[FieldSpec(name="name", return_type="str")],
        )
        spec = RoleClassTransformationSpec(
            class_name="Person",
            qualified_name="uni.Person",
            role_type=RoleType.DELEGATOR,
            bases_to_add=[BaseClassSpec(name="HasRoles")],
            delegation=delegation,
            is_role_taker=True,
            needs_has_roles_init=True,
        )
        assert spec.is_role_taker is True
        assert spec.needs_has_roles_init is True
        assert len(spec.bases_to_add) == 1
        assert spec.delegation.delegatee_attribute == "delegatee"

    def test_is_subclass_of_base(self):
        spec = RoleClassTransformationSpec(class_name="X", qualified_name="p.X")
        assert isinstance(spec, ClassTransformationSpec)


class TestImportSpec:
    def test_minimal_construction(self):
        spec = ImportSpec(module="typing")
        assert spec.module == "typing"
        assert spec.names == frozenset()

    def test_with_names(self):
        spec = ImportSpec(
            module="typing", names=frozenset({"List", "Optional"})
        )
        assert "List" in spec.names
        assert "Optional" in spec.names

    def test_type_checking(self):
        spec = ImportSpec(
            module="krrood.patterns.role",
            names=frozenset({"Role"}),
            is_type_checking=True,
        )
        assert spec.is_type_checking is True

    def test_equality(self):
        a = ImportSpec(module="typing", names=frozenset({"List"}))
        b = ImportSpec(module="typing", names=frozenset({"List"}))
        assert a == b


class TestModuleTransformationSpec:
    def test_minimal_construction(self):
        import types

        mod = types.ModuleType("test_module")
        spec = ModuleTransformationSpec(
            module_name="test_module",
            source_module=mod,
        )
        assert spec.module_name == "test_module"
        assert spec.classes == []
        assert spec.imports == []
        assert spec.cross_module_references == {}

    def test_with_classes_and_imports(self):
        import types

        mod = types.ModuleType("test_module")
        cls_spec = RoleClassTransformationSpec(
            class_name="Person",
            qualified_name="test_module.Person",
            is_role_taker=True,
        )
        imp_spec = ImportSpec(
            module="typing", names=frozenset({"List"})
        )
        spec = ModuleTransformationSpec(
            module_name="test_module",
            source_module=mod,
            classes=[cls_spec],
            imports=[imp_spec],
            cross_module_references={"Person": "other.module"},
        )
        assert len(spec.classes) == 1
        assert len(spec.imports) == 1
        assert spec.cross_module_references["Person"] == "other.module"
