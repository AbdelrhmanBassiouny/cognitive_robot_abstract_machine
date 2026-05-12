"""
Role transformation planner: converts :class:`ModuleTransformationSpec` into
an :class:`ActionPlan` for role-pattern module transformation.

This planner knows how to generate CST nodes for:
- Delegated property getters and setters
- Delegated method bodies
- ``DelegatorFor`` and ``RoleFor`` mixin class definitions
- Imports needed by generated code
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import libcst

from krrood.class_diagrams.utils import topological_sort_by_inheritance
from krrood.patterns.code_generation.actions.base import Action
from krrood.patterns.code_generation.actions.generate import CreateClass
from krrood.patterns.code_generation.actions.plan import ActionPlan
from krrood.patterns.code_generation.actions.transform import (
    AddBaseClass,
    AddImport,
    AddMethod,
    AddProperty,
    EnsureSuperInitCall,
)
from krrood.patterns.code_generation.libcst_node_factory import LibCSTNodeFactory
from krrood.patterns.code_generation.planners.base import (
    ActionPlanner,
    PlanningContext,
)
from krrood.patterns.code_generation.specs.specs import (
    BaseClassSpec,
    ClassTransformationSpec,
    DelegationSpec,
    ImportSpec,
    MemberKind,
    MemberSpec,
    ModuleTransformationSpec,
)


def _make_arg(name: str) -> libcst.Arg:
    return libcst.Arg(value=libcst.Name(name))


def _parse_type_annotation(type_str: str) -> libcst.BaseExpression:
    """Parse a type string into a libcst expression node.

    Handles both simple names (``"int"``) and complex generics
    (``"Optional[List[str]]"``).
    """
    try:
        return libcst.parse_expression(type_str)
    except Exception:
        # Fallback: if the type string is not a valid expression,
        # use it as a plain name (may still fail for truly invalid types).
        return libcst.Name(type_str)


def _make_delegator_name(class_name: str) -> str:
    return f"DelegatorFor{class_name}"


def _make_role_for_name(class_name: str) -> str:
    return f"RoleFor{class_name}"


@dataclass
class RoleTransformationPlanner(ActionPlanner):
    """Converts a :class:`ModuleTransformationSpec` into an :class:`ActionPlan`.

    This is the planner for the role-pattern transformation pipeline.  It
    produces atomic actions that, when executed, generate:
    - Transformed role-taker classes with ``HasRoles`` base
    - ``DelegatorFor<Taker>`` and ``RoleFor<Taker>`` mixin classes
    - Required imports
    """

    delegatee_attr: str = "delegatee"
    """Attribute name on the delegating class that holds the delegatee."""

    def plan(
        self, spec: ModuleTransformationSpec, context: PlanningContext
    ) -> ActionPlan:
        """Convert *spec* into an :class:`ActionPlan`.

        :param spec: The module transformation spec from the analysis layer.
        :param context: Shared planning context.
        """
        actions: list[Action] = []

        for class_spec in spec.classes:
            if class_spec.is_role_taker or class_spec.role_type != "NOT_A_ROLE":
                actions.append(
                    self._plan_class_transformation(class_spec, context)
                )

        for import_spec in spec.imports:
            if import_spec.names:
                actions.append(
                    AddImport(
                        module_name=import_spec.module,
                        names=list(import_spec.names),
                        is_type_checking=import_spec.is_type_checking,
                    )
                )

        return ActionPlan(
            actions=actions,
            description=f"Transform module {spec.module_name}",
        )

    def _plan_class_transformation(
        self, spec: ClassTransformationSpec, context: PlanningContext
    ) -> ActionPlan:
        """Plan the transformation of a single class."""
        sub_actions: list[Action] = []

        # 1. Add base classes (e.g., HasRoles)
        for base in spec.bases_to_add:
            sub_actions.append(
                AddBaseClass(spec.class_name, base)
            )

        # 2. Ensure HasRoles.__init__ is called
        if spec.needs_has_roles_init:
            sub_actions.append(
                EnsureSuperInitCall(spec.class_name, "HasRoles")
            )

        # 3. Generate DelegatorFor mixin with delegation members
        if spec.is_role_taker and spec.delegation:
            sub_actions.append(
                self._plan_delegator_for(spec, context)
            )

        # 4. Generate RoleFor mixin (only for non-pd_only takers)
        if spec.is_role_taker and spec.role_type != "DELEGATOR":
            sub_actions.append(
                self._plan_role_for(spec, context)
            )

        return ActionPlan(
            actions=sub_actions,
            description=f"Transform class {spec.class_name}",
        )

    def _plan_delegator_for(
        self, spec: ClassTransformationSpec, context: PlanningContext
    ) -> ActionPlan:
        """Plan the creation of a ``DelegatorFor<Taker>`` class.

        Groups members by their defining class and creates a base mixin
        class for each non-None definer, plus the main ``DelegatorFor``
        for the taker itself.
        """
        actions: list[Action] = []
        delegation = spec.delegation
        if delegation is None:
            return ActionPlan(actions=actions, description="No delegation needed")

        # Separate taker-own members from inherited members
        own_members: list[MemberSpec] = []
        by_definer: dict[str, list[MemberSpec]] = {}

        for member in delegation.members:
            if member.defining_class is None:
                own_members.append(member)
            else:
                definer_name = member.defining_class.__name__
                by_definer.setdefault(definer_name, []).append(member)

        # Create body for the main DelegatorFor class
        body_nodes = self._make_delegatee_property(spec.class_name, context)
        body_nodes += self._members_to_body(own_members, context)

        delegator_name = _make_delegator_name(spec.class_name)
        actions.append(
            CreateClass(
                class_name=delegator_name,
                bases=[BaseClassSpec(name="ABC")],
                body=body_nodes,
                decorators=[
                    libcst.Decorator(
                        decorator=libcst.Call(
                            func=libcst.Name("dataclass"),
                            args=[
                                libcst.Arg(
                                    keyword=libcst.Name("eq"),
                                    value=libcst.Name("False"),
                                )
                            ],
                        )
                    )
                ],
            )
        )

        return ActionPlan(
            actions=actions,
            description=f"Create {delegator_name} mixin",
        )

    def _plan_role_for(
        self, spec: ClassTransformationSpec, context: PlanningContext
    ) -> ActionPlan:
        """Plan the creation of a ``RoleFor<Taker>`` class."""
        role_for_name = _make_role_for_name(spec.class_name)
        delegator_name = _make_delegator_name(spec.class_name)

        body_nodes = self._make_delegatee_property(spec.class_name, context)

        actions = [
            CreateClass(
                class_name=role_for_name,
                bases=[
                    BaseClassSpec(name=delegator_name),
                    BaseClassSpec(name="ABC"),
                ],
                body=body_nodes,
                decorators=[
                    libcst.Decorator(
                        decorator=libcst.Call(
                            func=libcst.Name("dataclass"),
                            args=[
                                libcst.Arg(
                                    keyword=libcst.Name("eq"),
                                    value=libcst.Name("False"),
                                )
                            ],
                        )
                    )
                ],
            )
        ]

        return ActionPlan(
            actions=actions,
            description=f"Create {role_for_name} mixin",
        )

    def _make_delegatee_property(
        self, class_name: str, context: PlanningContext
    ) -> list[libcst.BaseStatement]:
        """Create the abstract ``delegatee`` property getter."""
        return [
            context.factory.make_property_getter_node(
                self.delegatee_attr, class_name, "..."
            )
        ]

    def _members_to_body(
        self, members: list[MemberSpec], context: PlanningContext
    ) -> list[libcst.BaseStatement]:
        """Convert a list of :class:`MemberSpec` objects to CST body statements."""
        nodes: list[libcst.BaseStatement] = []
        for member in members:
            if member.kind == MemberKind.FIELD:
                nodes.extend(
                    self._make_field_delegation(member, context)
                )
            elif member.kind == MemberKind.PROPERTY:
                nodes.append(
                    self._make_property_delegation(member, context)
                )
            elif member.kind == MemberKind.METHOD:
                node = self._make_method_delegation(member, context)
                if node is not None:
                    nodes.append(node)
        return nodes

    def _make_field_delegation(
        self, member: MemberSpec, context: PlanningContext
    ) -> list[libcst.FunctionDef]:
        """Create getter and setter nodes for a dataclass field."""
        type_name = member.return_type
        delegatee_path = f"self.{self.delegatee_attr}.{member.name}"
        return context.factory.make_property_getter_and_setter_nodes(
            member.name,
            type_name,
            delegatee_path,
            f"{delegatee_path} = value",
        )

    def _make_property_delegation(
        self, member: MemberSpec, context: PlanningContext
    ) -> libcst.FunctionDef:
        """Create a getter node for a property."""
        delegatee_path = f"self.{self.delegatee_attr}.{member.name}"
        return context.factory.make_property_getter_node(
            member.name,
            member.return_type,
            delegatee_path,
        )

    def _make_method_delegation(
        self, member: MemberSpec, context: PlanningContext
    ) -> libcst.BaseStatement | None:
        """Create a delegation method node."""
        param_names = [
            p.name
            for p in member.parameters
            if p.name not in ("self", "cls")
        ]
        call_args = ", ".join(param_names)
        delegatee_path = f"self.{self.delegatee_attr}.{member.name}"
        body = libcst.IndentedBlock(
            [
                libcst.parse_statement(
                    f"return {delegatee_path}({call_args})"
                )
            ]
        )

        params = [
            libcst.Param(name=libcst.Name("self")),
        ]
        for p in member.parameters:
            if p.name in ("self", "cls"):
                continue
            ann = (
                libcst.Annotation(annotation=_parse_type_annotation(p.type_annotation))
                if p.type_annotation
                else None
            )
            default = None
            if p.has_default:
                default = libcst.Name("None")
            params.append(
                libcst.Param(
                    name=libcst.Name(p.name),
                    annotation=ann,
                    default=default,
                )
            )

        returns = None
        if member.return_type:
            returns = libcst.Annotation(
                annotation=_parse_type_annotation(member.return_type)
            )

        return libcst.FunctionDef(
            name=libcst.Name(member.name),
            params=libcst.Parameters(params=tuple(params)),
            body=body,
            returns=returns,
        )
