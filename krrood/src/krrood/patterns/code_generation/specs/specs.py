"""
Pure-data specification dataclasses for code generation.

These dataclasses describe *what* transformations are needed without any
knowledge of *how* they are implemented.  Analyzers produce specs; planners
consume specs to produce :class:`Action` objects.

All classes in this module are frozen dataclasses so they are hashable,
comparable, and safe to cache or serialise.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from types import ModuleType

from krrood.patterns.role.meta_data import RoleType


@dataclass(frozen=True)
class ParameterSpec:
    """Describes one parameter of a method.

    Attributes:
        name: The parameter name (without annotations or defaults).
        type_annotation: The string form of the type annotation, or ``None``
            if the parameter is unannotated.
        has_default: ``True`` if the parameter has a default value.
    """

    name: str
    type_annotation: str | None = None
    has_default: bool = False


# ── MemberSpec hierarchy ─────────────────────────────────────────────
#
# The previous ``MemberKind`` enum + ``kind`` field has been replaced by
# polymorphic subclasses.  Each subclass carries only the fields relevant
# to that member type.  Dispatch is done via ``isinstance`` checks rather
# than comparing an enum value.


@dataclass(frozen=True)
class MemberSpec:
    """Base for all member specifications.

    Attributes:
        name: The member name (e.g. ``"get_name"``, ``"age"``).
        return_type: The string form of the return type, or ``None``.
        defining_class: The class that originally defines this member.
    """

    name: str
    return_type: str | None = None
    defining_class: type | None = None


@dataclass(frozen=True)
class FieldSpec(MemberSpec):
    """A dataclass field exposed via getter + setter delegation."""


@dataclass(frozen=True)
class PropertySpec(MemberSpec):
    """A Python property exposed via getter-only delegation."""


@dataclass(frozen=True)
class MethodSpec(MemberSpec):
    """A concrete instance method that delegates to the delegatee.

    Attributes:
        parameters: The method parameters (excluding ``self``).
        decorators: Decorator names to apply (e.g. ``["abstractmethod"]``).
    """

    parameters: list[ParameterSpec] = field(default_factory=list)
    decorators: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class StaticMethodSpec(MethodSpec):
    """A ``@staticmethod`` that delegates."""


@dataclass(frozen=True)
class ClassMethodSpec(MethodSpec):
    """A ``@classmethod`` that delegates."""


@dataclass(frozen=True)
class FactoryMethodSpec(ClassMethodSpec):
    """A ``@classmethod`` that returns an instance (not delegated)."""


@dataclass(frozen=True)
class DelegationSpec:
    """Describes what members a class should delegate via a named attribute.

    Produced by :class:`DelegationAnalyzer` after walking the MRO of a
    role-taker or property-delegator class.

    Attributes:
        delegatee_attribute: The attribute name on the delegating class that
            holds the delegatee instance (e.g. ``"delegatee"``).
        members: The members that need delegation nodes.
        excluded_names: Member names that are deliberately excluded from
            delegation (e.g. ``__init__``, ``__post_init__``).
    """

    delegatee_attribute: str
    members: list[MemberSpec] = field(default_factory=list)
    excluded_names: frozenset[str] = field(default_factory=frozenset)


@dataclass(frozen=True)
class BaseClassSpec:
    """Describes a base class that should be added to or referenced by a class.

    Attributes:
        name: The class name (e.g. ``"HasRoles"``).
        module: The dotted module name where the class is defined, or
            ``None`` if the class lives in the same module as its target.
    """

    name: str
    module: str | None = None


@dataclass(frozen=True)
class ClassTransformationSpec:
    """Generic specification for transforming one class in a module.

    Describes *what* a class needs: base classes, delegation members, and
    factory methods.  Role-specific concerns live in the subclass
    :class:`RoleClassTransformationSpec`.

    Attributes:
        class_name: The short name of the class.
        qualified_name: The fully-qualified dotted name.
        bases_to_add: Base classes that should be injected into the class.
        delegation: Delegation members, or ``None`` if no delegation is needed.
        factory_methods: Factory methods that need wrapper generation.
    """

    class_name: str
    qualified_name: str
    bases_to_add: list[BaseClassSpec] = field(default_factory=list)
    delegation: DelegationSpec | None = None
    factory_methods: list[MemberSpec] = field(default_factory=list)


@dataclass(frozen=True)
class RoleClassTransformationSpec(ClassTransformationSpec):
    """Role-specific transformation spec for one class.

    Extends :class:`ClassTransformationSpec` with fields that describe where
    the class sits in the role/delegation hierarchy.

    Attributes:
        role_type: Classification within the role/delegation hierarchy.
        is_role_taker: ``True`` if this class is a role taker (or delegatee).
        is_role: ``True`` if this class is a :class:`Role` subclass.
        needs_has_roles_init: ``True`` if ``HasRoles.__init__`` must be
            called explicitly in the class's ``__init__``.
    """

    role_type: RoleType = RoleType.NOT_A_ROLE
    is_role_taker: bool = False
    is_role: bool = False
    needs_has_roles_init: bool = False


@dataclass(frozen=True)
class ImportSpec:
    """Describes an import that must appear in a generated or transformed module.

    Attributes:
        module: The dotted module name to import from.
        names: The names to import from that module.
        is_type_checking: ``True`` if the import belongs inside an
            ``if TYPE_CHECKING:`` block.
    """

    module: str
    names: frozenset[str] = field(default_factory=frozenset)
    is_type_checking: bool = False


@dataclass(frozen=True)
class ModuleTransformationSpec:
    """Complete specification for transforming one module.

    This is the top-level spec produced by running all analyzers over a
    single module.  It is consumed by :class:`ActionPlanner` to produce an
    :class:`ActionPlan`.

    Attributes:
        module_name: The dotted name of the module being transformed.
        source_module: The live :class:`ModuleType` object.
        classes: Per-class transformation specs, in definition order.
        imports: All imports required by the generated/transformed code.
        cross_module_references: Mapping of class name to the module that
            *owns* that class's mixin definitions.
    """

    module_name: str
    source_module: ModuleType
    classes: list[ClassTransformationSpec] = field(default_factory=list)
    imports: list[ImportSpec] = field(default_factory=list)
    cross_module_references: dict[str, str] = field(default_factory=dict)
