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
    AddBaseClass,
    AddImport,
    CreateClass,
)
from krrood.patterns.code_generation.planners.base import (
    ActionPlanner,
    PlanningContext,
)
from krrood.patterns.code_generation.planners.role_planner import (
    RoleTransformationPlanner,
)
from krrood.patterns.code_generation.specs import (
    BaseClassSpec,
    DelegationSpec,
    ImportSpec,
    MemberKind,
    MemberSpec,
    ModuleTransformationSpec,
    RoleClassTransformationSpec,
)


# ── fixtures ──────────────────────────────────────────────────────────


@pytest.fixture
def planning_context():
    mod = types.ModuleType("test_mod")
    diagram = ClassDiagram([])
    resolver = ImportNameResolver(
        source_module=mod, companion_modules=[], class_diagram=diagram
    )
    normaliser = TypeNormaliser(resolver=resolver, class_diagram=diagram)
    factory = LibCSTNodeFactory()
    return PlanningContext(
        factory=factory,
        normaliser=normaliser,
        resolver=resolver,
        module=mod,
    )


@pytest.fixture
def planner():
    return RoleTransformationPlanner()


@pytest.fixture
def executor():
    return ActionExecutor()


def _make_spec(classes=None, imports=None):
    mod = types.ModuleType("test_mod")
    return ModuleTransformationSpec(
        module_name="test_mod",
        source_module=mod,
        classes=classes or [],
        imports=imports or [],
    )


# ── ActionPlanner ABC ─────────────────────────────────────────────────


class TestActionPlannerABC:
    def test_cannot_instantiate_abstract(self):
        with pytest.raises(TypeError):
            ActionPlanner()


# ── PlanningContext ───────────────────────────────────────────────────


class TestPlanningContext:
    def test_construction(self, planning_context):
        assert planning_context.delegatee_attr == "delegatee"
        assert planning_context.file_name_prefix == ""
        assert isinstance(planning_context.factory, LibCSTNodeFactory)

    def test_custom_delegatee_attr(self, planning_context):
        ctx = PlanningContext(
            factory=planning_context.factory,
            normaliser=planning_context.normaliser,
            resolver=planning_context.resolver,
            delegatee_attr="role_taker",
        )
        assert ctx.delegatee_attr == "role_taker"


# ── RoleTransformationPlanner ─────────────────────────────────────────


class TestRoleTransformationPlanner:
    def test_empty_spec_produces_empty_plan(self, planner, planning_context):
        spec = _make_spec()
        plan = planner.plan(spec, planning_context)
        assert len(plan.actions) == 0
        assert plan.description == "Transform module test_mod"

    def test_class_without_delegation(self, planner, planning_context):
        """A role-taker class with no bases or delegation gets no sub-plans."""
        spec = _make_spec(
            classes=[
                RoleClassTransformationSpec(
                    class_name="Simple",
                    qualified_name="test_mod.Simple",
                    role_type="DELEGATOR",
                    is_role_taker=True,
                )
            ]
        )
        plan = planner.plan(spec, planning_context)
        # No sub-planner precondition matches (no bases, no delegation)
        assert len(plan.actions) == 0

    def test_class_with_delegation_creates_delegator_for(self, planner, planning_context, executor):
        spec = _make_spec(
            classes=[
                RoleClassTransformationSpec(
                    class_name="Person",
                    qualified_name="test_mod.Person",
                    role_type="DELEGATOR",
                    is_role_taker=True,
                    delegation=DelegationSpec(
                        delegatee_attribute="delegatee",
                        members=[
                            MemberSpec(
                                name="name",
                                kind=MemberKind.FIELD,
                                return_type="str",
                            ),
                            MemberSpec(
                                name="get_title",
                                kind=MemberKind.METHOD,
                                return_type="str",
                            ),
                        ],
                    ),
                )
            ]
        )
        plan = planner.plan(spec, planning_context)
        result = executor.execute(
            plan,
            libcst.parse_module("class Person:\n    name: str\n"),
        )
        assert result.success
        code = result.module.code
        assert "class DelegatorForPerson" in code
        assert "def name" in code
        assert "def get_title" in code

    def test_class_with_has_roles_base(self, planner, planning_context, executor):
        spec = _make_spec(
            classes=[
                RoleClassTransformationSpec(
                    class_name="Person",
                    qualified_name="test_mod.Person",
                    role_type="DELEGATOR",
                    is_role_taker=True,
                    bases_to_add=[BaseClassSpec(name="HasRoles")],
                    delegation=DelegationSpec(
                        delegatee_attribute="delegatee",
                        members=[
                            MemberSpec(
                                name="name",
                                kind=MemberKind.FIELD,
                                return_type="str",
                            ),
                        ],
                    ),
                )
            ]
        )
        plan = planner.plan(spec, planning_context)
        result = executor.execute(
            plan,
            libcst.parse_module("class Person:\n    name: str\n"),
        )
        assert result.success
        code = result.module.code
        assert "class Person(HasRoles)" in code
        assert "class DelegatorForPerson" in code

    def test_role_taker_with_role_for(self, planner, planning_context, executor):
        """Non-DELEGATOR role type also generates a RoleFor mixin."""
        spec = _make_spec(
            classes=[
                RoleClassTransformationSpec(
                    class_name="Person",
                    qualified_name="test_mod.Person",
                    role_type="PRIMARY",
                    is_role_taker=True,
                    delegation=DelegationSpec(
                        delegatee_attribute="delegatee",
                        members=[
                            MemberSpec(
                                name="age",
                                kind=MemberKind.FIELD,
                                return_type="int",
                            ),
                        ],
                    ),
                )
            ]
        )
        plan = planner.plan(spec, planning_context)
        result = executor.execute(
            plan,
            libcst.parse_module("class Person:\n    age: int = 0\n"),
        )
        assert result.success
        code = result.module.code
        assert "class DelegatorForPerson" in code
        assert "class RoleForPerson" in code

    def test_imports_appended_to_module(self, planner, planning_context, executor):
        spec = _make_spec(
            imports=[
                ImportSpec(module="typing", names=frozenset({"List", "Optional"})),
            ]
        )
        plan = planner.plan(spec, planning_context)
        result = executor.execute(plan, libcst.parse_module("x = 1\n"))
        assert result.success
        code = result.module.code
        assert "from typing import List, Optional" in code

    def test_empty_imports_skipped(self, planner, planning_context, executor):
        spec = _make_spec(
            imports=[ImportSpec(module="typing", names=frozenset())]
        )
        plan = planner.plan(spec, planning_context)
        result = executor.execute(plan, libcst.parse_module("x = 1\n"))
        assert result.success
        # Module should be unchanged (no empty import added)
        assert "from typing import" not in result.module.code

    def test_field_delegation_creates_getter_and_setter(self, planner, planning_context, executor):
        spec = _make_spec(
            classes=[
                RoleClassTransformationSpec(
                    class_name="Person",
                    qualified_name="test_mod.Person",
                    role_type="DELEGATOR",
                    is_role_taker=True,
                    delegation=DelegationSpec(
                        delegatee_attribute="delegatee",
                        members=[
                            MemberSpec(
                                name="name",
                                kind=MemberKind.FIELD,
                                return_type="str",
                            ),
                        ],
                    ),
                )
            ]
        )
        plan = planner.plan(spec, planning_context)
        result = executor.execute(
            plan,
            libcst.parse_module("class Person:\n    name: str\n"),
        )
        assert result.success
        code = result.module.code
        assert "@property" in code
        assert "def name" in code
        assert "name.setter" in code
        assert "self.delegatee.name" in code

    def test_method_delegation_creates_delegating_call(self, planner, planning_context, executor):
        spec = _make_spec(
            classes=[
                RoleClassTransformationSpec(
                    class_name="Person",
                    qualified_name="test_mod.Person",
                    role_type="DELEGATOR",
                    is_role_taker=True,
                    delegation=DelegationSpec(
                        delegatee_attribute="delegatee",
                        members=[
                            MemberSpec(
                                name="get_title",
                                kind=MemberKind.METHOD,
                                return_type="str",
                            ),
                        ],
                    ),
                )
            ]
        )
        plan = planner.plan(spec, planning_context)
        result = executor.execute(
            plan,
            libcst.parse_module("class Person:\n    name: str\n"),
        )
        assert result.success
        code = result.module.code
        assert "def get_title" in code
        assert "self.delegatee.get_title()" in code

    def test_property_delegation_creates_getter_only(self, planner, planning_context, executor):
        spec = _make_spec(
            classes=[
                RoleClassTransformationSpec(
                    class_name="Person",
                    qualified_name="test_mod.Person",
                    role_type="DELEGATOR",
                    is_role_taker=True,
                    delegation=DelegationSpec(
                        delegatee_attribute="delegatee",
                        members=[
                            MemberSpec(
                                name="full_name",
                                kind=MemberKind.PROPERTY,
                                return_type="str",
                            ),
                        ],
                    ),
                )
            ]
        )
        plan = planner.plan(spec, planning_context)
        result = executor.execute(
            plan,
            libcst.parse_module("class Person:\n    name: str\n"),
        )
        assert result.success
        code = result.module.code
        assert "def full_name" in code
        assert "self.delegatee.full_name" in code
        # Property getter should NOT have a setter
        assert "full_name.setter" not in code

    def test_defining_class_separates_members(self, planner, planning_context, executor):
        """Members with a defining_class get their own base DelegatorFor class."""
        # Create a same-module base so it gets a local DelegatorFor
        same_module_base = type("Base", (), {})
        same_module_base.__module__ = "test_mod"
        spec = _make_spec(
            classes=[
                RoleClassTransformationSpec(
                    class_name="Professor",
                    qualified_name="test_mod.Professor",
                    role_type="DELEGATOR",
                    is_role_taker=True,
                    delegation=DelegationSpec(
                        delegatee_attribute="delegatee",
                        members=[
                            MemberSpec(
                                name="own_field",
                                kind=MemberKind.FIELD,
                                return_type="str",
                                defining_class=None,
                            ),
                            MemberSpec(
                                name="inherited_method",
                                kind=MemberKind.METHOD,
                                return_type="int",
                                defining_class=same_module_base,
                            ),
                        ],
                    ),
                )
            ]
        )
        plan = planner.plan(spec, planning_context)
        result = executor.execute(
            plan,
            libcst.parse_module("class Professor:\n    own_field: str\n"),
        )
        assert result.success
        code = result.module.code
        # Both DelegatorFor classes should be created (same-module base)
        assert "class DelegatorForProfessor" in code
        assert "class DelegatorForBase" in code
        # Base mixin gets inherited members
        assert "inherited_method" in code
        # Taker's own DelegatorFor gets own members
        assert "own_field" in code

    def test_cross_module_definer_generates_import(self, planner, planning_context, executor):
        """A defining_class from another module generates an import, not a local class."""
        cross_module_base = type("OtherBase", (), {})
        cross_module_base.__module__ = "some.other.module"
        spec = _make_spec(
            classes=[
                RoleClassTransformationSpec(
                    class_name="Professor",
                    qualified_name="test_mod.Professor",
                    role_type="DELEGATOR",
                    is_role_taker=True,
                    delegation=DelegationSpec(
                        delegatee_attribute="delegatee",
                        members=[
                            MemberSpec(
                                name="inherited_method",
                                kind=MemberKind.METHOD,
                                return_type="int",
                                defining_class=cross_module_base,
                            ),
                        ],
                    ),
                )
            ]
        )
        plan = planner.plan(spec, planning_context)
        result = executor.execute(
            plan,
            libcst.parse_module("class Professor:\n    name: str\n"),
        )
        assert result.success
        code = result.module.code
        # Should import the cross-module DelegatorFor instead of creating it
        assert "import DelegatorForOtherBase" in code
        # Should NOT create a local DelegatorForOtherBase
        assert "class DelegatorForOtherBase" not in code
        # But the local DelegatorFor inherits from it
        assert "DelegatorForOtherBase" in code

    def test_delegatee_property_is_present(self, planner, planning_context, executor):
        spec = _make_spec(
            classes=[
                RoleClassTransformationSpec(
                    class_name="Person",
                    qualified_name="test_mod.Person",
                    role_type="DELEGATOR",
                    is_role_taker=True,
                    delegation=DelegationSpec(
                        delegatee_attribute="delegatee",
                        members=[],
                    ),
                )
            ]
        )
        plan = planner.plan(spec, planning_context)
        result = executor.execute(
            plan,
            libcst.parse_module("class Person:\n    name: str\n"),
        )
        assert result.success
        code = result.module.code
        assert "@property" in code
        assert "def delegatee" in code

    def test_plan_is_executable_multiple_classes(self, planner, planning_context, executor):
        spec = _make_spec(
            classes=[
                RoleClassTransformationSpec(
                    class_name="Person",
                    qualified_name="test_mod.Person",
                    role_type="DELEGATOR",
                    is_role_taker=True,
                    bases_to_add=[BaseClassSpec(name="HasRoles")],
                    delegation=DelegationSpec(
                        delegatee_attribute="delegatee",
                        members=[
                            MemberSpec(
                                name="name",
                                kind=MemberKind.FIELD,
                                return_type="str",
                            ),
                        ],
                    ),
                ),
                RoleClassTransformationSpec(
                    class_name="Company",
                    qualified_name="test_mod.Company",
                    role_type="DELEGATOR",
                    is_role_taker=True,
                    delegation=DelegationSpec(
                        delegatee_attribute="delegatee",
                        members=[
                            MemberSpec(
                                name="revenue",
                                kind=MemberKind.FIELD,
                                return_type="float",
                            ),
                        ],
                    ),
                ),
            ]
        )
        plan = planner.plan(spec, planning_context)
        module = libcst.parse_module(
            "class Person:\n    name: str\n\nclass Company:\n    revenue: float = 0.0\n"
        )
        result = executor.execute(plan, module)
        assert result.success
        code = result.module.code
        assert "class Person(HasRoles)" in code
        assert "class DelegatorForPerson" in code
        assert "class DelegatorForCompany" in code

    def test_needs_has_roles_init_creates_ensure_call(self, planner, planning_context, executor):
        spec = _make_spec(
            classes=[
                RoleClassTransformationSpec(
                    class_name="Person",
                    qualified_name="test_mod.Person",
                    role_type="DELEGATOR",
                    is_role_taker=True,
                    bases_to_add=[BaseClassSpec(name="HasRoles")],
                    needs_has_roles_init=True,
                    delegation=None,
                )
            ]
        )
        plan = planner.plan(spec, planning_context)
        src = """\
@dataclass(eq=False, init=False)
class Person:
    name: str

    def __init__(self, name: str):
        self.name = name
"""
        module = libcst.parse_module(src)
        result = executor.execute(plan, module)
        assert result.success
        assert "HasRoles.__init__(self)" in result.module.code

    def test_plan_actions_are_correct_types(self, planner, planning_context):
        spec = _make_spec(
            classes=[
                RoleClassTransformationSpec(
                    class_name="Person",
                    qualified_name="test_mod.Person",
                    role_type="DELEGATOR",
                    is_role_taker=True,
                    bases_to_add=[BaseClassSpec(name="HasRoles")],
                    delegation=DelegationSpec(
                        delegatee_attribute="delegatee",
                        members=[
                            MemberSpec(
                                name="name",
                                kind=MemberKind.FIELD,
                                return_type="str",
                            ),
                        ],
                    ),
                )
            ],
            imports=[ImportSpec(module="typing", names=frozenset({"List"}))],
        )
        plan = planner.plan(spec, planning_context)
        # Sub-planners contributed directly: HasRoles, DelegatorFor, + import
        assert len(plan.actions) == 3

        # Verify the AddImport is present
        imports = [a for a in plan.actions if isinstance(a, AddImport)]
        assert len(imports) == 1
        assert imports[0].module_name == "typing"
        assert "List" in imports[0].names

        # Verify sub-plans exist
        sub_plans = [a for a in plan.actions if isinstance(a, ActionPlan)]
        assert len(sub_plans) == 2
