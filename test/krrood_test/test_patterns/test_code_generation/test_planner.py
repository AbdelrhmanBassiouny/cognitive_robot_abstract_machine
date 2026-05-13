"""Tests for the planner layer: RoleTransformationPlanner, PlanningContext."""

from __future__ import annotations

import libcst
import pytest
import types

from krrood.class_diagrams import ClassDiagram
from krrood.patterns.code_generation import (
    LibCSTNodeFactory,
    TypeNormaliser,
    ImportNameResolver,
)
from krrood.patterns.code_generation.actions import (
    ActionExecutor,
    ActionPlan,
)
from krrood.patterns.code_generation.planners.base import (
    ActionPlanner,
    PlanningContext,
)
from krrood.patterns.code_generation.planners.role_planner import (
    RoleTransformationPlanner,
)
from krrood.patterns.code_generation.planners.role_planners import (
    DelegatorForPlanner,
    HasRolesPlanner,
    RoleForPlanner,
)
from krrood.patterns.code_generation.specs import (
    BaseClassSpec,
    DelegationSpec,
    FieldSpec,
    ImportSpec,
    MethodSpec,
    ModuleTransformationSpec,
    PropertySpec,
    RoleClassTransformationSpec,
)
from krrood.patterns.role.meta_data import RoleType


@pytest.fixture
def planning_context():
    mod = types.ModuleType("test_mod")
    diagram = ClassDiagram([])
    resolver = ImportNameResolver(source_module=mod, companion_modules=[], class_diagram=diagram)
    normaliser = TypeNormaliser(resolver=resolver, class_diagram=diagram)
    factory = LibCSTNodeFactory()
    return PlanningContext(factory=factory, normaliser=normaliser, resolver=resolver, module=mod)


@pytest.fixture
def planner():
    return RoleTransformationPlanner()


@pytest.fixture
def executor():
    return ActionExecutor()


def _make_spec(classes=None, imports=None):
    mod = types.ModuleType("test_mod")
    return ModuleTransformationSpec(module_name="test_mod", source_module=mod, classes=classes or [], imports=imports or [])


class TestActionPlannerABC:
    def test_cannot_instantiate_abstract(self):
        with pytest.raises(TypeError):
            ActionPlanner()


class TestSubPlannerPreconditions:
    def test_has_roles_precondition_true(self):
        spec = RoleClassTransformationSpec(class_name="X", qualified_name="p.X", bases_to_add=[BaseClassSpec(name="HasRoles")])
        assert HasRolesPlanner().precondition(spec) is True

    def test_has_roles_precondition_false(self):
        spec = RoleClassTransformationSpec(class_name="X", qualified_name="p.X")
        assert HasRolesPlanner().precondition(spec) is False

    def test_delegator_for_precondition_true(self):
        spec = RoleClassTransformationSpec(class_name="X", qualified_name="p.X", is_role_taker=True, delegation=DelegationSpec(delegatee_attribute="d", members=[FieldSpec(name="f", return_type="str")]))
        assert DelegatorForPlanner().precondition(spec) is True

    def test_delegator_for_precondition_false_no_taker(self):
        spec = RoleClassTransformationSpec(class_name="X", qualified_name="p.X", delegation=DelegationSpec(delegatee_attribute="d", members=[FieldSpec(name="f", return_type="str")]))
        assert DelegatorForPlanner().precondition(spec) is False

    def test_delegator_for_precondition_false_no_delegation(self):
        spec = RoleClassTransformationSpec(class_name="X", qualified_name="p.X", is_role_taker=True)
        assert DelegatorForPlanner().precondition(spec) is False

    def test_role_for_precondition_true(self):
        spec = RoleClassTransformationSpec(class_name="X", qualified_name="p.X", is_role_taker=True, role_type=RoleType.PRIMARY)
        assert RoleForPlanner().precondition(spec) is True

    def test_role_for_precondition_false_delegator(self):
        spec = RoleClassTransformationSpec(class_name="X", qualified_name="p.X", is_role_taker=True, role_type=RoleType.DELEGATOR)
        assert RoleForPlanner().precondition(spec) is False


class TestRoleTransformationPlanner:
    def test_empty_spec_produces_empty_plan(self, planner, planning_context):
        plan = planner.plan(_make_spec(), planning_context)
        assert len(plan.actions) == 0

    def test_class_with_delegation_creates_delegator_for(self, planner, planning_context, executor):
        spec = _make_spec(classes=[RoleClassTransformationSpec(
            class_name="Person", qualified_name="test_mod.Person",
            role_type=RoleType.DELEGATOR, is_role_taker=True,
            delegation=DelegationSpec(delegatee_attribute="delegatee", members=[
                FieldSpec(name="name", return_type="str"),
                MethodSpec(name="get_title", return_type="str"),
            ]),
        )])
        plan = planner.plan(spec, planning_context)
        result = executor.execute(plan, libcst.parse_module("class Person:\n    name: str\n"))
        assert result.success
        code = result.module.code
        assert "class DelegatorForPerson" in code
        assert "def name" in code
        assert "def get_title" in code

    def test_class_with_has_roles_base(self, planner, planning_context, executor):
        spec = _make_spec(classes=[RoleClassTransformationSpec(
            class_name="Person", qualified_name="test_mod.Person",
            role_type=RoleType.DELEGATOR, is_role_taker=True,
            bases_to_add=[BaseClassSpec(name="HasRoles")],
            delegation=DelegationSpec(delegatee_attribute="delegatee", members=[
                FieldSpec(name="name", return_type="str"),
            ]),
        )])
        plan = planner.plan(spec, planning_context)
        result = executor.execute(plan, libcst.parse_module("class Person:\n    name: str\n"))
        assert result.success
        code = result.module.code
        assert "class Person(HasRoles)" in code
        assert "class DelegatorForPerson" in code

    def test_role_taker_with_role_for(self, planner, planning_context, executor):
        spec = _make_spec(classes=[RoleClassTransformationSpec(
            class_name="Person", qualified_name="test_mod.Person",
            role_type=RoleType.PRIMARY, is_role_taker=True,
            delegation=DelegationSpec(delegatee_attribute="delegatee", members=[
                FieldSpec(name="age", return_type="int"),
            ]),
        )])
        plan = planner.plan(spec, planning_context)
        result = executor.execute(plan, libcst.parse_module("class Person:\n    age: int = 0\n"))
        assert result.success
        assert "class RoleForPerson" in result.module.code

    def test_imports_appended_to_module(self, planner, planning_context, executor):
        spec = _make_spec(imports=[ImportSpec(module="typing", names=frozenset({"List"}))])
        plan = planner.plan(spec, planning_context)
        result = executor.execute(plan, libcst.parse_module("x = 1\n"))
        assert result.success
        assert "from typing import List" in result.module.code

    def test_field_delegation_creates_getter_and_setter(self, planner, planning_context, executor):
        spec = _make_spec(classes=[RoleClassTransformationSpec(
            class_name="Person", qualified_name="test_mod.Person",
            role_type=RoleType.DELEGATOR, is_role_taker=True,
            delegation=DelegationSpec(delegatee_attribute="delegatee", members=[
                FieldSpec(name="name", return_type="str"),
            ]),
        )])
        plan = planner.plan(spec, planning_context)
        result = executor.execute(plan, libcst.parse_module("class Person:\n    name: str\n"))
        assert result.success
        assert "name.setter" in result.module.code
        assert "self.delegatee.name" in result.module.code

    def test_method_delegation_creates_delegating_call(self, planner, planning_context, executor):
        spec = _make_spec(classes=[RoleClassTransformationSpec(
            class_name="Person", qualified_name="test_mod.Person",
            role_type=RoleType.DELEGATOR, is_role_taker=True,
            delegation=DelegationSpec(delegatee_attribute="delegatee", members=[
                MethodSpec(name="get_title", return_type="str"),
            ]),
        )])
        plan = planner.plan(spec, planning_context)
        result = executor.execute(plan, libcst.parse_module("class Person:\n    name: str\n"))
        assert result.success
        assert "self.delegatee.get_title()" in result.module.code

    def test_delegatee_property_is_present(self, planner, planning_context, executor):
        spec = _make_spec(classes=[RoleClassTransformationSpec(
            class_name="Person", qualified_name="test_mod.Person",
            role_type=RoleType.DELEGATOR, is_role_taker=True,
            delegation=DelegationSpec(delegatee_attribute="delegatee", members=[]),
        )])
        plan = planner.plan(spec, planning_context)
        result = executor.execute(plan, libcst.parse_module("class Person:\n    name: str\n"))
        assert result.success
        assert "def delegatee" in result.module.code

    def test_needs_has_roles_init_creates_ensure_call(self, planner, planning_context, executor):
        spec = _make_spec(classes=[RoleClassTransformationSpec(
            class_name="Person", qualified_name="test_mod.Person",
            role_type=RoleType.DELEGATOR, is_role_taker=True,
            bases_to_add=[BaseClassSpec(name="HasRoles")], needs_has_roles_init=True,
        )])
        plan = planner.plan(spec, planning_context)
        src = "@dataclass(eq=False, init=False)\nclass Person:\n    name: str\n\n    def __init__(self, name: str):\n        self.name = name\n"
        result = executor.execute(plan, libcst.parse_module(src))
        assert result.success
        assert "HasRoles.__init__(self)" in result.module.code
