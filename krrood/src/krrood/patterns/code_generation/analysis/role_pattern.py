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
    RoleClassTransformationSpec,
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
    ) -> RoleClassTransformationSpec:
        """Produce a :class:`RoleClassTransformationSpec` for *target*.

        :param target: The wrapped class to analyze.
        :param context: Shared analysis context.
        """
        clazz = target.clazz
        role_type = RoleType.get_role_type(target)

        # A class is a role taker if it appears in any delegatee role.
        # The class_diagram.role_takers are the direct delegatees of Role subclasses.
        # already_covered_bases includes transitive same-package ancestors.
        is_direct_role_taker = clazz in context.class_diagram.role_takers
        is_transitive_taker = clazz in context.already_covered_bases
        is_role_taker = is_direct_role_taker or is_transitive_taker
        is_role = role_type not in (RoleType.NOT_A_ROLE, RoleType.DELEGATOR)

        if clazz in context.pd_only_delegatees:
            is_role_taker = True
            is_role = False

        bases_to_add: list[BaseClassSpec] = []
        needs_has_roles_init = False

        # Only add HasRoles to direct role takers that don't already have it
        # and don't inherit from another role taker.
        if (
            is_direct_role_taker
            and clazz not in context.pd_only_delegatees
            and not self._already_has_has_roles(target)
            and not self._inherits_from_role_taker(target, context)
        ):
            bases_to_add.append(BaseClassSpec(
                name=HasRoles.__name__,
                module="krrood.patterns.role",
            ))
            needs_has_roles_init = True

        return RoleClassTransformationSpec(
            class_name=clazz.__name__,
            qualified_name=f"{clazz.__module__}.{clazz.__qualname__}",
            bases_to_add=bases_to_add,
            delegation=None,  # filled in by planner combining with DelegationAnalyzer
            role_type=role_type,
            is_role_taker=is_role_taker,
            is_role=is_role,
            needs_has_roles_init=needs_has_roles_init,
        )

    @staticmethod
    def _inherits_from_role_taker(
        target: WrappedClass, context: AnalysisContext
    ) -> bool:
        """Check whether *target* inherits from a class that is already a role taker."""
        for base in target.clazz.__bases__:
            if base in context.class_diagram.role_takers:
                return True
        return False

    @staticmethod
    def _already_has_has_roles(target: WrappedClass) -> bool:
        """Check whether *target* already inherits from ``HasRoles``."""
        for base in target.clazz.__mro__:
            if base is HasRoles:
                return True
        return False
