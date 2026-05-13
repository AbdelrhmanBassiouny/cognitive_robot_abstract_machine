"""
Role-specific action planners.

Each planner is an :class:`ActionPlanner` subclass with a :meth:`precondition`
and a :meth:`plan`.  :class:`RoleTransformationPlanner` orchestrates them.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import libcst

from krrood.patterns.code_generation.actions import (
    Action,
    ActionPlan,
    AddBaseClass,
    CreateClass,
    DelegateField,
    DelegateMethod,
    DelegateProperty,
)
from krrood.patterns.code_generation.actions.transform import (
    AddImport,
    EnsureSuperInitCall,
)
from krrood.patterns.code_generation.planners.base import (
    ActionPlanner,
    PlanningContext,
)
from krrood.patterns.code_generation.specs.specs import (
    BaseClassSpec,
    MemberKind,
    MemberSpec,
    RoleClassTransformationSpec,
)


def _make_arg(name: str) -> libcst.Arg:
    return libcst.Arg(value=libcst.Name(name))


def _make_delegator_name(class_name: str) -> str:
    return f"DelegatorFor{class_name}"


def _make_role_for_name(class_name: str) -> str:
    return f"RoleFor{class_name}"


def _make_dataclass_decorator() -> libcst.Decorator:
    return libcst.Decorator(
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


def _make_delegatee_property(
    class_name: str, delegatee_attr: str, context: PlanningContext
) -> list[libcst.BaseStatement]:
    return [
        context.factory.make_property_getter_node(delegatee_attr, class_name, "...")
    ]


def _action_for_member(
    member: MemberSpec, target_class: str, delegatee_attr: str
) -> Action | None:
    """Return the appropriate delegation action for a member spec."""
    if member.kind == MemberKind.FIELD:
        return DelegateField(
            member=member, target_class=target_class, delegatee_attr=delegatee_attr
        )
    elif member.kind == MemberKind.PROPERTY:
        return DelegateProperty(
            member=member, target_class=target_class, delegatee_attr=delegatee_attr
        )
    elif member.kind == MemberKind.METHOD:
        return DelegateMethod(
            member=member, target_class=target_class, delegatee_attr=delegatee_attr
        )
    return None


# ── HasRolesPlanner ──────────────────────────────────────────────────


@dataclass
class HasRolesPlanner(ActionPlanner):
    """Plans HasRoles injection and ``__init__`` call for a role taker."""

    def precondition(self, spec: RoleClassTransformationSpec) -> bool:
        return bool(spec.bases_to_add) or spec.needs_has_roles_init

    def plan(
        self, spec: RoleClassTransformationSpec, context: PlanningContext
    ) -> ActionPlan:
        actions: list[Action] = []
        for base in spec.bases_to_add:
            actions.append(AddBaseClass(spec.class_name, base))
            # Add the import for the base class to the transformed original
            if base.module:
                actions.append(AddImport(base.module, [base.name]))
        if spec.needs_has_roles_init:
            actions.append(EnsureSuperInitCall(spec.class_name, "HasRoles"))
        return ActionPlan(
            actions=actions,
            description=f"Add HasRoles to {spec.class_name}",
        )


# ── DelegatorForPlanner ──────────────────────────────────────────────


@dataclass
class DelegatorForPlanner(ActionPlanner):
    """Plans ``DelegatorFor<Taker>`` mixin creation with base segregation."""

    delegatee_attr: str = "delegatee"

    def precondition(self, spec: RoleClassTransformationSpec) -> bool:
        return spec.is_role_taker and spec.delegation is not None

    def plan(
        self, spec: RoleClassTransformationSpec, context: PlanningContext
    ) -> ActionPlan:
        actions: list[Action] = []
        delegation = spec.delegation
        current_module = context.module.__name__ if context.module else ""

        # Separate own members from inherited members, split by module
        own_members: list[MemberSpec] = []
        by_definer: dict[str, list[MemberSpec]] = {}
        cross_module_definers: dict[str, str] = {}  # definer_name → module
        for member in delegation.members:
            if member.defining_class is None:
                own_members.append(member)
            else:
                definer_name = member.defining_class.__name__
                definer_module = member.defining_class.__module__
                if definer_module != current_module:
                    # Cross-module: import, don't create locally
                    cross_module_definers[definer_name] = definer_module
                else:
                    by_definer.setdefault(definer_name, []).append(member)

        # Phase A — local base mixin classes
        base_mixin_names: list[str] = []
        for definer_name, definer_members in by_definer.items():
            base_name = _make_delegator_name(definer_name)
            base_mixin_names.append(base_name)
            base_body = _make_delegatee_property(
                definer_name, self.delegatee_attr, context
            )
            for m in definer_members:
                base_body.extend(
                    _build_delegation_nodes(m, self.delegatee_attr, context)
                )
            actions.append(
                CreateClass(
                    class_name=base_name,
                    bases=[BaseClassSpec(name="ABC")],
                    body=base_body,
                    decorators=[_make_dataclass_decorator()],
                )
            )

        # Phase A2 — cross-module imports for defining ancestors
        for definer_name, definer_module in cross_module_definers.items():
            cross_name = _make_delegator_name(definer_name)
            base_mixin_names.append(cross_name)
            # Generate the import for this cross-module mixin
            from krrood.class_diagrams.utils import mixin_module_dotted_name
            mixin_mod = mixin_module_dotted_name(
                definer_module, "role_mixins", "_role_mixins"
            )
            actions.append(AddImport(mixin_mod, [cross_name]))

        # Phase B — taker's own DelegatorFor, inheriting from base mixins
        delegator_name = _make_delegator_name(spec.class_name)
        delegator_bases = [BaseClassSpec(name=bn) for bn in base_mixin_names] + [
            BaseClassSpec(name="ABC")
        ]
        body_nodes = _make_delegatee_property(
            spec.class_name, self.delegatee_attr, context
        )
        for m in own_members:
            body_nodes.extend(_build_delegation_nodes(m, self.delegatee_attr, context))

        actions.append(
            CreateClass(
                class_name=delegator_name,
                bases=delegator_bases,
                body=body_nodes,
                decorators=[_make_dataclass_decorator()],
            )
        )

        return ActionPlan(
            actions=actions,
            description=f"Create {delegator_name} mixin",
        )


def _build_delegation_nodes(
    member: MemberSpec, delegatee_attr: str, context: PlanningContext
) -> list[libcst.BaseStatement]:
    """Build CST nodes for a delegation member. Returns list (1-2 nodes)."""
    from krrood.patterns.code_generation.actions.generate import (
        _build_field_getter_node,
        _build_field_setter_node,
        _build_delegation_method_node,
    )

    if member.kind == MemberKind.FIELD:
        getter = _build_field_getter_node(member, delegatee_attr)
        setter = _build_field_setter_node(member, delegatee_attr)
        if setter:
            return [getter, setter]
        return [getter]
    elif member.kind == MemberKind.PROPERTY:
        return [_build_field_getter_node(member, delegatee_attr)]
    elif member.kind == MemberKind.METHOD:
        return [_build_delegation_method_node(member, delegatee_attr)]
    raise NotImplementedError(f"No node builder for {member.kind}")


# ── RoleForPlanner ───────────────────────────────────────────────────


@dataclass
class RoleForPlanner(ActionPlanner):
    """Plans ``RoleFor<Taker>`` mixin creation."""

    delegatee_attr: str = "delegatee"

    def precondition(self, spec: RoleClassTransformationSpec) -> bool:
        return spec.is_role_taker and spec.role_type != "DELEGATOR"

    def plan(
        self, spec: RoleClassTransformationSpec, context: PlanningContext
    ) -> ActionPlan:
        role_for_name = _make_role_for_name(spec.class_name)
        delegator_name = _make_delegator_name(spec.class_name)
        body_nodes = _make_delegatee_property(
            spec.class_name, self.delegatee_attr, context
        )

        return ActionPlan(
            actions=[
                CreateClass(
                    class_name=role_for_name,
                    bases=[
                        BaseClassSpec(name=delegator_name),
                        BaseClassSpec(name="ABC"),
                    ],
                    body=body_nodes,
                    decorators=[_make_dataclass_decorator()],
                )
            ],
            description=f"Create {role_for_name} mixin",
        )
