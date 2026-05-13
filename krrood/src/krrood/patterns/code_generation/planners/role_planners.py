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
    CreateDerivedClass,
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
    FieldSpec,
    MemberSpec,
    MethodSpec,
    PropertySpec,
    RoleClassTransformationSpec,
)
from krrood.patterns.role.meta_data import RoleType


def _make_delegator_name(class_name: str) -> str:
    return f"DelegatorFor{class_name}"


def _make_role_for_name(class_name: str) -> str:
    return f"RoleFor{class_name}"


def _delegation_action_for(
    member: MemberSpec, target_class: str, delegatee_attr: str
) -> Action | None:
    """Return a :class:`DelegateField`, :class:`DelegateProperty`, or
    :class:`DelegateMethod` for *member*, dispatching by subclass."""
    if isinstance(member, FieldSpec):
        return DelegateField(
            member=member, target_class=target_class, delegatee_attr=delegatee_attr
        )
    elif isinstance(member, PropertySpec):
        return DelegateProperty(
            member=member, target_class=target_class, delegatee_attr=delegatee_attr
        )
    elif isinstance(member, MethodSpec):
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
            actions.append(
                CreateDerivedClass(
                    class_name=base_name,
                    delegatee_type_name=definer_name,
                    delegatee_attr=self.delegatee_attr,
                )
            )
            for m in definer_members:
                a = _delegation_action_for(m, base_name, self.delegatee_attr)
                if a:
                    actions.append(a)

        # Phase A2 — cross-module imports for defining ancestors
        for definer_name, definer_module in cross_module_definers.items():
            cross_name = _make_delegator_name(definer_name)
            base_mixin_names.append(cross_name)
            from krrood.class_diagrams.utils import mixin_module_dotted_name
            mixin_mod = mixin_module_dotted_name(
                definer_module, "role_mixins", "_role_mixins"
            )
            actions.append(AddImport(mixin_mod, [cross_name]))

        # Phase B — taker's own DelegatorFor, inheriting from base mixins
        delegator_name = _make_delegator_name(spec.class_name)
        delegator_bases = [
            BaseClassSpec(name=bn) for bn in base_mixin_names
        ]
        actions.append(
            CreateDerivedClass(
                class_name=delegator_name,
                delegatee_type_name=spec.class_name,
                delegatee_attr=self.delegatee_attr,
                bases=delegator_bases,
            )
        )
        for m in own_members:
            a = _delegation_action_for(m, delegator_name, self.delegatee_attr)
            if a:
                actions.append(a)

        return ActionPlan(
            actions=actions,
            description=f"Create {delegator_name} mixin",
        )


# ── RoleForPlanner ───────────────────────────────────────────────────


@dataclass
class RoleForPlanner(ActionPlanner):
    """Plans ``RoleFor<Taker>`` mixin creation."""

    delegatee_attr: str = "delegatee"

    def precondition(self, spec: RoleClassTransformationSpec) -> bool:
        return spec.is_role_taker and spec.role_type != RoleType.DELEGATOR

    def plan(
        self, spec: RoleClassTransformationSpec, context: PlanningContext
    ) -> ActionPlan:
        role_for_name = _make_role_for_name(spec.class_name)
        delegator_name = _make_delegator_name(spec.class_name)

        return ActionPlan(
            actions=[
                CreateDerivedClass(
                    class_name=role_for_name,
                    delegatee_type_name=spec.class_name,
                    delegatee_attr=self.delegatee_attr,
                    bases=[BaseClassSpec(name=delegator_name)],
                )
            ],
            description=f"Create {role_for_name} mixin",
        )
