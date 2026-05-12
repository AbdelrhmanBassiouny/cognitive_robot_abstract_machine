"""
Role pattern analyzer: classifies classes within the role/delegation hierarchy
and produces :class:`ClassTransformationSpec` values.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from krrood.class_diagrams.class_diagram import WrappedClass
from krrood.patterns.code_generation.analysis.base import (
    AnalysisContext,
    CodeAnalyzer,
)
from krrood.patterns.code_generation.specs.specs import (
    BaseClassSpec,
    ClassTransformationSpec,
)
from krrood.patterns.role.meta_data import RoleType
from krrood.patterns.role.role import HasRoles, Role


@dataclass
class RolePatternAnalyzer(CodeAnalyzer):
    """Analyzes a :class:`WrappedClass` and produces a :class:`ClassTransformationSpec`.

    Determines:
    - Whether the class is a role taker, a role, or neither
    - What base classes need to be added (e.g. ``HasRoles``)
    - Whether ``HasRoles.__init__`` must be called explicitly
    """

    def analyze(
        self, target: WrappedClass, context: AnalysisContext
    ) -> ClassTransformationSpec:
        """Produce a :class:`ClassTransformationSpec` for *target*.

        :param target: The wrapped class to analyze.
        :param context: Shared analysis context.
        """
        clazz = target.clazz
        role_type = RoleType.get_role_type(target)
        is_role_taker = clazz in context.already_covered_bases
        is_role = issubclass(clazz, Role) if not isinstance(target, type) else False

        # More specific check for role taker detection
        # A class is a role taker if it is an already_covered_bases member AND
        # not excluded by pd_only_delegatees
        if clazz in context.pd_only_delegatees:
            is_role_taker = True
            is_role = False
        elif is_role_taker:
            is_role = is_role and clazz not in context.pd_only_delegatees

        bases_to_add: list[BaseClassSpec] = []
        needs_has_roles_init = False

        if is_role_taker and clazz not in context.pd_only_delegatees:
            # Only add HasRoles to root Role-pattern takers
            if clazz in context.class_diagram.role_takers:
                if not self._already_has_has_roles(target):
                    bases_to_add.append(BaseClassSpec(
                        name=HasRoles.__name__,
                        module="krrood.patterns.role",
                    ))
                    needs_has_roles_init = True

        return ClassTransformationSpec(
            class_name=clazz.__name__,
            qualified_name=f"{clazz.__module__}.{clazz.__qualname__}",
            role_type=role_type,
            bases_to_add=bases_to_add,
            delegation=None,  # filled in by planner combining with DelegationAnalyzer
            is_role_taker=is_role_taker,
            is_role=is_role,
            needs_has_roles_init=needs_has_roles_init,
        )

    @staticmethod
    def _already_has_has_roles(target: WrappedClass) -> bool:
        """Check whether *target* already inherits from ``HasRoles``."""
        for base in target.clazz.__mro__:
            if base is HasRoles:
                return True
        return False
