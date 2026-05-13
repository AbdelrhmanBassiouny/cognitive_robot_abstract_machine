"""
Role transformation planner: orchestrates sub-planners for role-pattern
module transformation.

The heavy lifting has moved to :mod:`role_planners`:

* :class:`~krrood.patterns.code_generation.planners.role_planners.HasRolesPlanner`
* :class:`~krrood.patterns.code_generation.planners.role_planners.DelegatorForPlanner`
* :class:`~krrood.patterns.code_generation.planners.role_planners.RoleForPlanner`

This module's :class:`RoleTransformationPlanner` iterates over classes and
imports, delegating to the sub-planners whose :meth:`precondition` is met.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from krrood.patterns.code_generation.actions.base import Action
from krrood.patterns.code_generation.actions.plan import ActionPlan
from krrood.patterns.code_generation.actions.transform import AddImport
from krrood.patterns.code_generation.planners.base import (
    ActionPlanner,
    PlanningContext,
)
from krrood.patterns.code_generation.planners.role_planners import (
    DelegatorForPlanner,
    HasRolesPlanner,
    RoleForPlanner,
)
from krrood.patterns.code_generation.specs.specs import (
    ModuleTransformationSpec,
    RoleClassTransformationSpec,
)


@dataclass
class RoleTransformationPlanner(ActionPlanner):
    """Orchestrates sub-planners to transform role-pattern modules.

    For each class in the module spec, runs every sub-planner whose
    :meth:`precondition` is satisfied.  Adding a new transformation step
    means adding a new planner to :attr:`_sub_planners` — no conditional
    logic to modify.
    """

    delegatee_attr: str = "delegatee"

    def __post_init__(self):
        self._sub_planners: list[ActionPlanner] = [
            HasRolesPlanner(),
            DelegatorForPlanner(delegatee_attr=self.delegatee_attr),
            RoleForPlanner(delegatee_attr=self.delegatee_attr),
        ]

    def plan(
        self, spec: ModuleTransformationSpec, context: PlanningContext
    ) -> ActionPlan:
        """Convert *spec* into an :class:`ActionPlan`.

        :param spec: The module transformation spec from the analysis layer.
        :param context: Shared planning context.
        """
        actions: list[Action] = []

        for class_spec in spec.classes:
            if isinstance(class_spec, RoleClassTransformationSpec):
                for planner in self._sub_planners:
                    if planner.precondition(class_spec):
                        actions.append(planner.plan(class_spec, context))

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
