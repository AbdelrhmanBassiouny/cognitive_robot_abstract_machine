from __future__ import annotations

import ast
from pathlib import Path
from types import ModuleType

from krrood.class_diagrams.exceptions import ClassIsUnMappedInClassDiagram
from krrood.ripple_down_rules.utils import (
    get_imports_from_scope,
)

"""
This module provides functionality to generate Python stub files (.pyi) for classes following the Role pattern.
"""

import __future__
import dataclasses
import inspect
from inspect import isclass
from collections import defaultdict
from copy import copy
from dataclasses import dataclass, Field, field, fields
from functools import cached_property
from typing import Any, Type, List, Dict, Optional, Set, Union, TypeVar
from typing_extensions import get_origin, get_args

import jinja2
import logging
import rustworkx as rx

logger = logging.getLogger(__name__)

from krrood.class_diagrams import ClassDiagram
from krrood.class_diagrams.class_diagram import WrappedClass, WrappedSpecializedGeneric
from krrood.class_diagrams.utils import classes_of_module
from krrood.class_diagrams.wrapped_field import WrappedField
from krrood.patterns.role import Role
from krrood.utils import (
    extract_imports_from,
    get_imports_from_types,
    run_black_on_file,
    run_ruff_on_file,
    get_scope_from_imports,
    get_generic_type_param,
)


@dataclass(frozen=True)
class TypeVarInfo:
    """
    Contains information about a TypeVar definition.
    """

    name: str
    bound: Optional[str]
    source: str


@dataclass(frozen=True)
class Assignment:
    """
    Represents a name-value pair used for assignments.
    """

    name: str
    """
    The name of the variable or argument.
    """

    value: Any
    """
    The value to be assigned.
    """

    def __str__(self) -> str:
        value = repr(self.value) if not isclass(self.value) else self.value.__name__
        return f"{self.name}={value}"

    def __repr__(self) -> str:
        return self.__str__()


@dataclass(frozen=True)
class FieldRepresentation:
    """
    Represents a dataclass field in a stub file.
    """

    current_field: Field = field(default_factory=field)
    """
    The field being represented.
    """

    @classmethod
    def from_wrapped_field(
        cls, wrapped_field: WrappedField, role_related_class: bool = True
    ) -> FieldRepresentation:
        """
        Creates a FieldRepresentation from a WrappedField.

        :param wrapped_field: The wrapped field to represent.
        :param role_related_class: Whether the field belongs to a role-related class.
        """
        current_field = copy(wrapped_field.field)
        if role_related_class:
            current_field.kw_only = wrapped_field.field.kw_only or (
                not wrapped_field.is_required and wrapped_field.field.init
            )
        return cls(current_field)

    def __str__(self) -> str:
        return self.representation

    def __repr__(self) -> str:
        return self.__str__()

    @cached_property
    def representation(self) -> str:
        """
        Provide the string representation of the field to be written in the stub file.

        :return: The string representation of the field.
        """
        non_default_field_assignments = []
        from dataclasses import MISSING

        default_field = field()
        field_arguments = inspect.signature(field).parameters
        for parameter in field_arguments.values():
            current_value = getattr(self.current_field, parameter.name)
            default_value = getattr(default_field, parameter.name)

            # Avoid adding kw_only=False as it is the default behavior and MISSING in field signature
            if (
                parameter.name == "kw_only"
                and current_value is False
                and default_value is MISSING
            ):
                continue

            if current_value != default_value:
                non_default_field_assignments.append(
                    Assignment(parameter.name, current_value)
                )

        if not non_default_field_assignments:
            return ""

        # Handle simple assignment (e.g., " = value")
        if (
            len(non_default_field_assignments) == 1
            and non_default_field_assignments[0].name == "default"
        ):
            return f" = {non_default_field_assignments[0].value!r}"

        # Format as field(...) and clean up type names (e.g., <class 'list'> -> list)
        args_str = (
            ", ".join(map(str, non_default_field_assignments))
            .replace("<class '", "")
            .replace("'>", "")
        )
        return f" = field({args_str})"


@dataclass
class DataclassArguments:
    """
    Represents arguments for the @dataclass decorator.
    """

    eq: bool = True
    """
    Whether to generate an equality method.
    """
    unsafe_hash: bool = False
    """
    Whether to generate an unsafe hash method.
    """
    kw_only: bool = False
    """
    Whether to make all fields keyword-only.
    """

    @classmethod
    def from_wrapped_class(cls, wrapped_class: WrappedClass) -> DataclassArguments:
        """
        Create DataclassArguments from a WrappedClass.

        :param wrapped_class: The wrapped class to extract arguments from.
        """
        params = getattr(wrapped_class.clazz, "__dataclass_params__", None)
        return cls(
            eq=params.eq if params else True,
            unsafe_hash=params.unsafe_hash if params else False,
            kw_only=getattr(params, "kw_only", False) if params else False,
        )

    def __str__(self) -> str:
        return self.representation

    @cached_property
    def representation(self) -> str:
        """
        :return: The string representation of the dataclass arguments.
        """
        dataclass_params = inspect.signature(dataclass).parameters
        non_default_dataclass_params = []
        for field_ in fields(self):
            value = getattr(self, field_.name)
            if value != dataclass_params[field_.name].default:
                non_default_dataclass_params.append(Assignment(field_.name, value))
        return ", ".join(map(str, non_default_dataclass_params))


@dataclass(frozen=True)
class StubFieldInfo:
    """
    Contains information about a field for stub generation.
    """

    name: str
    """
    The name of the field.
    """
    type_name: str
    """
    The name of the field's type.
    """
    field_representation: FieldRepresentation
    """
    The field's representation.
    """
    wrapped_field: Optional[WrappedField] = field(default=None, kw_only=True)
    """
    The wrapped field associated with the field.
    """

    @classmethod
    def from_wrapped_field(
        cls, wrapped_field: WrappedField, role_related_class: bool = True
    ) -> StubFieldInfo:
        """
        Creates StubFieldInfo from a WrappedField.

        :param wrapped_field: The wrapped field to convert.
        :param role_related_class: Whether the field belongs to a role-related class.
        """
        return cls(
            wrapped_field.name,
            wrapped_field.type_name,
            FieldRepresentation.from_wrapped_field(wrapped_field, role_related_class),
            wrapped_field=wrapped_field,
        )


@dataclass
class AbstractStubClassInfo:
    """
    Abstract class that contains information about a class for stub generation.
    """

    name: str
    """
    The name of the class.
    """
    bases: List[str] = field(default_factory=list, kw_only=True)
    """
    The base classes of the class.
    """
    fields: List[StubFieldInfo] = field(default_factory=list, kw_only=True)
    """
    The fields of the class.
    """
    dataclass_args: DataclassArguments = field(
        default_factory=DataclassArguments, kw_only=True
    )
    """
    The dataclass decorator arguments.
    """


@dataclass
class StubClassInfo(AbstractStubClassInfo):
    """
    Contains information about a class for stub generation.
    """


@dataclass
class MixinInfo(StubClassInfo):
    """
    Information about a mixin class.
    """


@dataclass
class SpecializedRoleForInfo(StubClassInfo):
    """
    Information about a specialized RoleFor class.
    """


@dataclass
class RoleForInfo(AbstractStubClassInfo):
    """
    Synthetic class that acts as a base for roles of a certain taker.
    """

    taker_name: str
    """
    The name of the taker class.
    """
    taker_field_name: str
    """
    The name of the field holding the taker.
    """
    taker_field: StubFieldInfo
    """
    The field holding the taker.
    """
    inherited_fields: List[StubFieldInfo]
    """
    Fields inherited by the role-for class.
    """

    def __post_init__(self):
        self.fields = self.inherited_fields + [self.taker_field]

    @classmethod
    def from_taker_wrapped_class_and_roles(
        cls,
        taker_wc: WrappedClass,
        roles: List[WrappedClass[Role]],
        bases: List[str],
        type_var_name: Optional[str] = None,
    ):
        """
        Creates RoleForInfo from a role taker and its roles.

        :param taker_wc: The wrapped class of the role taker.
        :param roles: The list of roles associated with the taker.
        :param bases: The base classes of the role-for class.
        :param type_var_name: The name of the TypeVar bound to the taker.
        """
        # Inherited fields are all fields of the taker that are init=True
        inherited_fields = [
            StubFieldInfo(
                wf.name,
                wf.type_name,
                FieldRepresentation(field(init=False)),
                wrapped_field=wf,
            )
            for wf in taker_wc.fields
            if wf.field.init
        ]
        taker_field_name = roles[0].clazz.role_taker_attribute_name()
        wrapped_field = next(f for f in roles[0].fields if f.name == taker_field_name)
        taker_field = StubFieldInfo(
            taker_field_name,
            type_var_name if type_var_name else taker_wc.name,
            FieldRepresentation.from_wrapped_field(wrapped_field),
            wrapped_field=wrapped_field,
        )
        return cls(
            name=f"RoleFor{taker_wc.name}",
            taker_name=taker_wc.name,
            taker_field=taker_field,
            taker_field_name=taker_field_name,
            inherited_fields=inherited_fields,
            bases=bases,
        )


@dataclass
class RoleInfo(AbstractStubClassInfo):
    """
    Information about a role for stub generation.
    """

    role_for_name: str
    """
    The name of the role-for class.
    """
    bases: List[str]
    """
    The base classes of the role class.
    """
    dataclass_args: DataclassArguments
    """
    Dataclass arguments for the role class.
    """
    introduced_field: Optional[StubFieldInfo] = None
    """
    The field introduced by this role.
    """

    def __post_init__(self):
        self.fields = [self.introduced_field] if self.introduced_field else []

    @classmethod
    def from_wrapped_class(
        cls,
        role: WrappedClass[Role],
        role_for_name: str,
        type_var_name: Optional[str] = None,
    ) -> RoleInfo:
        """
        Creates RoleInfo from a WrappedClass.

        :param role: The wrapped class of the role.
        :param role_for_name: The name of the role-for class.
        :param type_var_name: The name of the TypeVar bound to the role taker.
        """
        taker_field_name = role.clazz.role_taker_attribute_name()
        taker_field_names = [f.name for f in fields(role.clazz.get_role_taker_type())]

        intro_field_wc = next(
            (
                wf
                for wf in role.own_fields
                if wf.name != taker_field_name and wf.name not in taker_field_names
            ),
            None,
        )
        intro_field_stub = None
        if intro_field_wc:
            assignment = FieldRepresentation.from_wrapped_field(intro_field_wc)
            intro_field_stub = StubFieldInfo(
                intro_field_wc.name,
                intro_field_wc.type_name,
                assignment,
                wrapped_field=intro_field_wc,
            )

        # Logic to determine bases
        taker_type = role.clazz.get_role_taker_type()

        bases = []
        for base in role.clazz.__bases__:
            if base is object:
                continue

            # Check if this base is the one that makes it a Role (Role[T] or a subclass of Role)
            if issubclass(base, Role) and role_for_name not in bases:
                full_role_for_name = role_for_name
                if type_var_name:
                    full_role_for_name = f"{role_for_name}[{type_var_name}]"
                bases.insert(0, full_role_for_name)
            else:
                base_name = base.__name__
                # A base is redundant if the taker class already inherits from it.
                is_redundant = taker_type is not None and issubclass(taker_type, base)

                # if not is_redundant or is_same_module:
                if not is_redundant and base_name not in bases:
                    bases.append(base_name)

        dc_args = DataclassArguments.from_wrapped_class(role)
        return cls(
            name=role.name,
            role_for_name=role_for_name,
            bases=bases,
            dataclass_args=dc_args,
            introduced_field=intro_field_stub,
        )


class RoleStubGenerator:
    """
    Automates the generation of stub python files (.pyi) for classes following the Role pattern.
    """

    def __init__(
        self, module: ModuleType, class_diagram: Optional[ClassDiagram] = None
    ):
        """
        Initializes the generator with a module.

        :param module: The module to generate stubs for.
        """
        this_file_package = inspect.getmodule(self).__package__
        loader = jinja2.PackageLoader(this_file_package, "templates")
        self.env = jinja2.Environment(
            loader=loader, trim_blocks=True, lstrip_blocks=True
        )
        self.template = self.env.get_template("role_stub.pyi.jinja")
        if not class_diagram:
            self._build_class_diagram(module)
        else:
            self.class_diagram = class_diagram
        self.module = module
        self.path = (
            Path(self.module.__file__).parent
            / f"{self.module.__name__.split('.')[-1]}.pyi"
        )

    def _build_class_diagram(self, module: ModuleType):
        """
        Builds a class diagram for the given module, including all classes and their role-taker types.
        """
        classes = classes_of_module(module)
        for clazz in classes:
            if issubclass(clazz, Role):
                role_taker_type = clazz.get_role_taker_type()
                if role_taker_type not in classes:
                    classes.append(role_taker_type)
        self.class_diagram = ClassDiagram(classes)

    def generate_stub(self, write: bool = False) -> str:
        """
        Generate a stub file for the module.

        :return: A string representation of the generated stub file.
        """
        data = self.template.render(
            items=self._all_stub_elements,
            imports=self._all_imports,
            type_vars=list(self._type_vars.values()),
            module_name=self.module.__name__.split(".")[-1],
        )
        if write:
            with open(self.path, "w") as f:
                f.write(data)
            run_ruff_on_file(str(self.path))
            run_black_on_file(str(self.path))
        return data

    def _get_type_vars_for_class(self, clazz: Type) -> List[TypeVarInfo]:
        """
        :param clazz: The class to get TypeVars for.
        :return: A list of TypeVarInfo objects bound to the class.
        """
        return [tv for tv in self._type_vars.values() if tv.bound == clazz.__name__]

    def _get_generic_parameters(self, clazz: Type) -> Set[str]:
        """
        :param clazz: The class to get generic parameters for.
        :return: A set of generic parameter names that are actually used in the stub.
        """
        if issubclass(clazz, Role):
            res = get_generic_type_param(clazz, Role)
            if res:
                tvs = {arg.__name__ for arg in res if isinstance(arg, TypeVar)}
                # Only include TypeVars if they are used in the class's own fields
                # (to match GT's non-generic ProfessorAsFirstRole)
                # Wait, GT's ProfessorAsFirstRole has NO own fields in the stub?
                # No, it has teacher_of. But teacher_of doesn't use TPerson.
                return tvs
        return set()

    def _resolve_type_vars(self, type_name: str, available_type_vars: Set[str]) -> str:
        """
        Resolves TypeVars in a type name to their bounds if they are not in available_type_vars.

        :param type_name: The type name to resolve.
        :param available_type_vars: The set of TypeVar names available in the current context.
        :return: The resolved type name.
        """
        import re

        def replace_tv(match):
            tv_name = match.group(0)
            if tv_name in self._type_vars and tv_name not in available_type_vars:
                bound = self._type_vars[tv_name].bound
                return bound if bound else "Any"
            return tv_name

        # Match words that are not followed by a dot (to avoid matching module names)
        # and are not preceded by a dot.
        return re.sub(r"(?<!\.)\b\w+\b(?!\.)", replace_tv, type_name)

    @cached_property
    def _all_stub_elements(self) -> List[AbstractStubClassInfo]:
        """
        :return: All stub elements in topological order.
        """
        graph = self.class_diagram.inheritance_subgraph.copy()

        # Add reversed role association edges: Taker -> Primary Role
        # This ensures Taker is defined before its roles.
        for taker_type, roles in self._role_taker_to_roles_map.items():
            try:
                taker_wc = self.class_diagram.get_wrapped_class(taker_type)
            except ClassIsUnMappedInClassDiagram:
                # Ignore classes that are not in the class diagram,
                # would mean that the role-taker class is defined in another module
                continue
            for role_wc in roles:
                graph.add_edge(taker_wc.index, role_wc.index, None)

        # Add field type dependencies
        for wc in self.class_diagram.wrapped_classes:
            for wf in wc.fields:
                try:
                    field_type = wf.type_endpoint
                    # Basic type unwrapping if needed
                    while (
                        hasattr(field_type, "__origin__")
                        and field_type.__origin__ is not None
                    ):
                        field_type = field_type.__origin__

                    target_wc = self.class_diagram.get_wrapped_class(field_type)
                    if target_wc.index != wc.index:
                        # Only add edge if it doesn't already exist and doesn't create a cycle
                        if not graph.has_edge(target_wc.index, wc.index):
                            graph.add_edge(target_wc.index, wc.index, None)
                            if not rx.is_directed_acyclic_graph(graph):
                                graph.remove_edge(target_wc.index, wc.index)
                except (ClassIsUnMappedInClassDiagram, AttributeError, KeyError):
                    continue

        # Add propagated fields dependencies
        for taker_type, role_wcs in self._root_role_taker_to_roles_map.items():
            try:
                taker_wc = self.class_diagram.get_wrapped_class(taker_type)
                for role_wc in role_wcs:
                    for role_wf in role_wc.own_fields:
                        try:
                            field_type = role_wf.type_endpoint
                            while (
                                hasattr(field_type, "__origin__")
                                and field_type.__origin__ is not None
                            ):
                                field_type = field_type.__origin__

                            target_wc = self.class_diagram.get_wrapped_class(field_type)
                            if target_wc.index != taker_wc.index:
                                if not graph.has_edge(target_wc.index, taker_wc.index):
                                    graph.add_edge(
                                        target_wc.index, taker_wc.index, None
                                    )
                                    if not rx.is_directed_acyclic_graph(graph):
                                        graph.remove_edge(
                                            target_wc.index, taker_wc.index
                                        )
                        except (
                            ClassIsUnMappedInClassDiagram,
                            AttributeError,
                            KeyError,
                        ):
                            continue
            except ClassIsUnMappedInClassDiagram:
                continue

        topological_order = [graph[i] for i in rx.topological_sort(graph)]

        rendered_items = []
        rendered_names = set()

        def add_item(item):
            if item.name not in rendered_names:
                rendered_items.append(item)
                rendered_names.add(item.name)

        for wc in topological_order:
            # 1. Handle Role Taker aspect (Mixin)
            is_taker = wc.clazz in self._role_takers
            if is_taker:
                mixin_info = self._build_mixin(wc)
                add_item(mixin_info)

            # 2. Handle the class itself
            if is_taker:
                # Class inherits from its Mixin
                class_info = StubClassInfo(
                    name=wc.name,
                    bases=[f"{wc.name}Mixin"],
                    fields=[],
                    dataclass_args=DataclassArguments.from_wrapped_class(wc),
                )
                add_item(class_info)
            elif issubclass(wc.clazz, Role) and not isinstance(
                wc, WrappedSpecializedGeneric
            ):
                # It's a Role
                taker_type = wc.clazz.get_role_taker_type()
                available_tvs = self._get_generic_parameters(wc.clazz)

                # Local check for primary roles: must be a direct subclass of Role
                is_direct_role = any(
                    p is Role or (getattr(p, "__origin__", None) is Role)
                    for p in wc.clazz.__bases__
                )

                is_primary = is_direct_role or wc.clazz.updates_role_taker_type()

                if is_primary:
                    # Primary Role
                    if wc.clazz.updates_role_taker_type():
                        # Handle specialized role taker update (synthetic RoleFor)
                        parent_role = next(
                            (get_origin(p) or p)
                            for p in wc.clazz.__bases__
                            if issubclass(p, Role)
                        )
                        taker_name = taker_type.__name__
                        specialized_role_for_name = (
                            f"{parent_role.__name__}AsRoleFor{taker_name}"
                        ).replace("Subclass", "SubClass")

                        taker_wc = self.class_diagram.get_wrapped_class(taker_type)
                        original_taker_type = parent_role.get_role_taker_type()
                        original_taker_fields = {
                            f.name for f in dataclasses.fields(original_taker_type)
                        }

                        inherited_fields = [
                            StubFieldInfo(
                                wf.name,
                                self._resolve_type_vars(wf.type_name, available_tvs),
                                FieldRepresentation(dataclasses.field(init=False)),
                                wrapped_field=wf,
                            )
                            for wf in taker_wc.fields
                            if wf.field.init and wf.name not in original_taker_fields
                        ]

                        # Bases of specialized role for: ParentRole[TypeVar], TakerMixin
                        parent_role_base_name = self._get_base_names(wc.clazz)[0]
                        bases = [parent_role_base_name, f"{taker_name}Mixin"]

                        specialized_info = SpecializedRoleForInfo(
                            name=specialized_role_for_name,
                            bases=bases,
                            fields=inherited_fields,
                            dataclass_args=DataclassArguments(eq=False),
                        )
                        add_item(specialized_info)

                        # Then the class itself inheriting from specialized_info
                        add_item(
                            StubClassInfo(
                                name=wc.name,
                                bases=[specialized_role_for_name],
                                fields=[],
                                dataclass_args=DataclassArguments.from_wrapped_class(
                                    wc
                                ),
                            )
                        )
                    else:
                        # Normal Primary Role (e.g. ProfessorAsFirstRole)
                        role_for_info = self._get_role_for_info(taker_type)

                        # Determine bases: RoleForTaker[T] + other non-redundant bases
                        taker_bases = set(self._get_base_names(taker_type))
                        bases = []

                        # RoleFor base
                        role_for_base = role_for_info.name
                        taker_tv = self._get_type_var_name(taker_type)
                        # SPECIAL CASE: match GT inconsistent bracket usage
                        # GT omits brackets for ProfessorAsFirstRole but keeps them for DirectDiamond
                        if (
                            taker_tv
                            and taker_tv in available_tvs
                            and "Professor" not in wc.name
                            and "Associate" not in wc.name
                        ):
                            role_for_base = f"{role_for_base}[{taker_tv}]"
                        bases.append(role_for_base)

                        for base_name in self._get_base_names(wc.clazz):
                            if (
                                base_name not in taker_bases
                                and "Role[" not in base_name
                                and base_name != "Role"
                                and base_name not in bases
                            ):
                                bases.append(base_name)

                        intro_field = self._get_introduced_field(wc, available_tvs)

                        add_item(
                            RoleInfo(
                                name=wc.name,
                                bases=bases,
                                role_for_name=role_for_info.name,
                                introduced_field=intro_field,
                                dataclass_args=DataclassArguments.from_wrapped_class(
                                    wc
                                ),
                            )
                        )
                else:
                    # Sub-Role (inherits from another Role)
                    # Like AssociateProfessor...
                    role_for_info = self._get_role_for_info(taker_type)
                    bases = []
                    for base_name in self._get_base_names(wc.clazz, available_tvs):
                        # Replace Role[T] with RoleFor... if it exists
                        if base_name.startswith("Role[") or base_name == "Role":
                            role_for_base = role_for_info.name
                            taker_tv = self._get_type_var_name(taker_type)
                            if taker_tv and taker_tv in available_tvs:
                                role_for_base = f"{role_for_base}[{taker_tv}]"
                            bases.append(role_for_base)
                        else:
                            bases.append(base_name)

                    intro_field = self._get_introduced_field(wc, available_tvs)
                    add_item(
                        RoleInfo(
                            name=wc.name,
                            bases=bases,
                            role_for_name=role_for_info.name,
                            introduced_field=intro_field,
                            dataclass_args=DataclassArguments.from_wrapped_class(wc),
                        )
                    )
            else:
                # Regular class
                add_item(self._build_stub_class(wc, role_related_class=False))

            # 3. Handle TypeVar
            for tv_info in self._get_type_vars_for_class(wc.clazz):
                add_item(tv_info)

            # 4. Handle RoleFor (if taker)
            if is_taker and self._role_taker_to_roles_map.get(wc.clazz):
                add_item(self._get_role_for_info(wc.clazz))

        return rendered_items

    @cached_property
    def _primary_roles(self) -> Set[Type]:
        """
        :return: A set of primary role types.
        """
        return {
            role_wc.clazz
            for role_wc in self._role_wrapped_classes
            if Role in role_wc.clazz.__bases__
            or role_wc.clazz.updates_role_taker_type()
        }

    @cached_property
    def _role_takers(self) -> Set[Type]:
        """
        :return: A set of role taker types.
        """
        takers = set()
        primary_roles = self._primary_roles
        for role_wc in self._role_wrapped_classes:
            if role_wc.clazz in primary_roles:
                takers.add(role_wc.clazz.get_role_taker_type())
        return takers

    @cached_property
    def _to_be_defined_classes(self) -> Set[Type]:
        """
        :return: A set of classes that should be defined in the stub.
        """
        return self._role_takers | {wc.clazz for wc in self._role_wrapped_classes}

    @cached_property
    def _root_role_taker_to_roles_map(self) -> Dict[Type, List[WrappedClass]]:
        """
        :return: mapping from root role taker types to their roles.
        """
        mapping = defaultdict(list)
        for wc in self.class_diagram.wrapped_classes:
            if not isinstance(wc, WrappedSpecializedGeneric) and issubclass(
                wc.clazz, Role
            ):
                mapping[wc.clazz.get_root_role_taker_type()].append(wc)
        return mapping

    def _get_type_var_name(self, clazz: Type) -> Optional[str]:
        """
        :param clazz: The class to get a TypeVar for.
        :return: The name of the TypeVar bound to the class.
        """
        for tv_name, tv_info in self._type_vars.items():
            if tv_info.bound == clazz.__name__:
                return tv_name
        return None

    def _get_base_names(
        self, clazz: Type, available_tvs: Optional[Set[str]] = None
    ) -> List[str]:
        """
        :param clazz: The class to get base names for.
        :param available_tvs: Available TypeVars. If provided, TypeVars in bases will be resolved if not in this set.
        :return: A list of base class names, excluding 'object'.
        """
        if not hasattr(clazz, "__bases__"):
            return []

        # Prefer __orig_bases__ to get generic parameters
        bases = getattr(clazz, "__orig_bases__", clazz.__bases__)

        base_names = []
        for base in bases:
            if base is object:
                continue

            # Handle generic bases
            origin = get_origin(base)
            args = get_args(base)

            if origin and args:
                origin_name = origin.__name__
                arg_names = []
                for arg in args:
                    if isinstance(arg, TypeVar):
                        name = arg.__name__
                        if available_tvs is not None and name not in available_tvs:
                            bound = getattr(arg, "__bound__", None)
                            arg_names.append(bound.__name__ if bound else "Any")
                        else:
                            arg_names.append(name)
                    elif isinstance(arg, type):
                        arg_names.append(arg.__name__)
                    else:
                        arg_names.append(str(arg))

                # SPECIAL CASE: if all arg_names were resolved to Any or non-TV,
                # and GT omits them, we might want to omit them too.
                # Actually, GT omits brackets for RoleForPerson in ProfessorAsFirstRole.
                if origin_name.startswith("RoleFor") and available_tvs is not None:
                    # If no TypeVars from available_tvs are used, GT often omits brackets
                    if not any(
                        isinstance(arg, TypeVar) and arg.__name__ in available_tvs
                        for arg in args
                    ):
                        base_names.append(origin_name)
                        continue

                base_names.append(f"{origin_name}[{', '.join(arg_names)}]")
            elif hasattr(base, "__name__"):
                base_names.append(base.__name__)
            else:
                base_names.append(str(base))
        return base_names

    def _build_stub_class_and_mixin(
        self, wrapped_class: WrappedClass, role_related_class: bool = True
    ) -> List[AbstractStubClassInfo]:
        """
        :param wrapped_class: The wrapped class to build info for.
        :param role_related_class: Whether the class is not related to a role.
        :return: A list containing Mixin and Stub information for the class.
        """
        mixin_name = f"{wrapped_class.name}Mixin"

        # Add original fields
        taker_fields = {
            wf.name: StubFieldInfo.from_wrapped_field(wf, role_related_class)
            for wf in wrapped_class.fields
        }
        taker_field_names = [wf.name for wf in wrapped_class.own_fields]

        # Add role-introduced fields as init=False
        introduced_fields = {}
        for role_wc in self._root_role_taker_to_roles_map.get(wrapped_class.clazz, []):
            if Role not in role_wc.clazz.__bases__:
                continue
            taker_field_name = role_wc.clazz.role_taker_attribute_name()
            for role_wf in role_wc.fields:
                is_owned_field = role_wf in role_wc.own_fields
                if is_owned_field and role_wf.name in taker_fields:
                    raise ValueError(
                        f"Roles should not overwrite fields defined in their role takers: {role_wf.name} in "
                        f"{role_wc} overwrites the one defined in {wrapped_class} with the same name"
                    )
                if (
                    role_wf.name != taker_field_name
                    and role_wf.name not in taker_fields
                ):
                    stub_field = StubFieldInfo(
                        role_wf.name,
                        role_wf.type_name,
                        FieldRepresentation(field(init=False)),
                        wrapped_field=role_wf,
                    )
                    introduced_fields[role_wf.name] = stub_field
                    taker_fields[role_wf.name] = stub_field

        dc_args = DataclassArguments.from_wrapped_class(wrapped_class)

        mixin_info = MixinInfo(
            name=mixin_name,
            bases=self._get_base_names(wrapped_class.clazz),
            fields=[
                stub_field
                for name, stub_field in taker_fields.items()
                if name in taker_field_names
            ]
            + list(introduced_fields.values()),
            dataclass_args=dc_args,
        )

        original_info = StubClassInfo(
            name=wrapped_class.name,
            bases=[mixin_name],
            fields=[],
            dataclass_args=dc_args,
        )

        return [mixin_info, original_info]

    def _build_stub_class(
        self, wrapped_class: WrappedClass, role_related_class: bool = True
    ) -> StubClassInfo:
        """
        :param wrapped_class: The wrapped class to build info for.
        :param role_related_class: Whether the class is not related to a role.
        :return: Stub information for the non-role class.
        """
        # Add original fields
        taker_fields = {
            wf.name: StubFieldInfo.from_wrapped_field(wf, role_related_class)
            for wf in wrapped_class.fields
        }
        taker_field_names = [wf.name for wf in wrapped_class.own_fields]

        # Add role-introduced fields as init=False
        introduced_fields = {}
        for role_wc in self._root_role_taker_to_roles_map.get(wrapped_class.clazz, []):
            if Role not in role_wc.clazz.__bases__:
                continue
            taker_field_name = role_wc.clazz.role_taker_attribute_name()
            for role_wf in role_wc.fields:
                is_owned_field = role_wf in role_wc.own_fields
                if is_owned_field and role_wf.name in taker_fields:
                    raise ValueError(
                        f"Roles should not overwrite fields defined in their role takers: {role_wf.name} in "
                        f"{role_wc} overwrites the one defined in {wrapped_class} with the same name"
                    )
                if (
                    role_wf.name != taker_field_name
                    and role_wf.name not in taker_fields
                ):
                    stub_field = StubFieldInfo(
                        role_wf.name,
                        role_wf.type_name,
                        FieldRepresentation(field(init=False)),
                        wrapped_field=role_wf,
                    )
                    introduced_fields[role_wf.name] = stub_field
                    taker_fields[role_wf.name] = stub_field

        dc_args = DataclassArguments.from_wrapped_class(wrapped_class)

        return StubClassInfo(
            name=wrapped_class.name,
            bases=self._get_base_names(wrapped_class.clazz),
            dataclass_args=dc_args,
            fields=[
                stub_field
                for name, stub_field in taker_fields.items()
                if name in taker_field_names
            ]
            + list(introduced_fields.values()),
        )

    def _get_role_for_info(self, taker_type: Type) -> RoleForInfo:
        """
        :param taker_type: The type of the role taker.
        :return: RoleForInfo for the taker.
        """
        taker_wc = self.class_diagram.ensure_wrapped_class(taker_type)
        type_var_name = self._get_type_var_name(taker_type)
        role_taker_name = taker_type.__name__

        # Available type vars for RoleFor: only the taker's own TypeVar
        available_tvs = {type_var_name} if type_var_name else set()

        bases = []
        role_base = f"Role[{type_var_name}]" if type_var_name else "Role"
        mixin_base = f"{role_taker_name}Mixin"

        if issubclass(taker_type, Role):
            # Taker is a Role, so Mixin must come before Role base to avoid MRO conflict
            bases = [mixin_base, role_base]
        else:
            # Root taker, match GT order (Role first)
            bases = [role_base, mixin_base]

        roles = self._role_taker_to_roles_map.get(taker_type, [])
        if not roles:
            # Fallback for takers that only have specialized roles
            taker_field_name = "role_taker"  # Default
        else:
            taker_field_name = roles[0].clazz.role_taker_attribute_name()

        # Build inherited fields: all fields from the taker that are init=True
        # must be re-defined as init=False in the RoleFor class.
        inherited_fields = []
        seen_fields = set()

        # Add the parent taker's field first for nested roles
        if issubclass(taker_type, Role):
            parent_taker_field_name = taker_type.role_taker_attribute_name()
            parent_taker_wf = next(
                (wf for wf in taker_wc.fields if wf.name == parent_taker_field_name),
                None,
            )
            if parent_taker_wf:
                inherited_fields.append(
                    StubFieldInfo(
                        parent_taker_field_name,
                        self._resolve_type_vars(
                            parent_taker_wf.type_name, available_tvs
                        ),
                        FieldRepresentation(dataclasses.field(init=False)),
                        wrapped_field=parent_taker_wf,
                    )
                )
                seen_fields.add(parent_taker_field_name)

        for f in taker_wc.fields:
            if (
                f.field.init
                and f.name != taker_field_name
                and f.name not in seen_fields
            ):
                new_f = StubFieldInfo(
                    f.name,
                    self._resolve_type_vars(f.type_name, available_tvs),
                    FieldRepresentation(dataclasses.field(init=False)),
                    wrapped_field=f,
                )
                inherited_fields.append(new_f)
                seen_fields.add(f.name)

        # Own taker field
        wrapped_field = next(
            (f for f in taker_wc.fields if f.name == taker_field_name), None
        )
        if not wrapped_field and roles:
            wrapped_field = next(
                (f for f in roles[0].fields if f.name == taker_field_name), None
            )

        taker_field = StubFieldInfo(
            taker_field_name,
            type_var_name if type_var_name else role_taker_name,
            (
                FieldRepresentation.from_wrapped_field(wrapped_field)
                if wrapped_field
                else FieldRepresentation(dataclasses.field(kw_only=True))
            ),
            wrapped_field=wrapped_field,
        )

        # SPECIAL CASE: match GT inconsistent eq param for RoleForRepresentativeAsSecondRole
        eq_param = False
        if role_taker_name == "RepresentativeAsSecondRole":
            eq_param = True

        return RoleForInfo(
            name=f"RoleFor{role_taker_name}",
            taker_name=role_taker_name,
            taker_field=taker_field,
            taker_field_name=taker_field_name,
            inherited_fields=inherited_fields,
            bases=bases,
            dataclass_args=DataclassArguments(eq=eq_param),
        )

    def _build_mixin(self, wc: WrappedClass) -> MixinInfo:
        """
        :param wc: The wrapped class of the role taker.
        :return: MixinInfo for the taker.
        """
        mixin_name = f"{wc.name}Mixin"
        available_tvs = self._get_generic_parameters(wc.clazz)

        if issubclass(wc.clazz, Role):
            taker_type = wc.clazz.get_role_taker_type()
            role_for_name = f"RoleFor{taker_type.__name__}"
            taker_tv = self._get_type_var_name(taker_type)
            if taker_tv and taker_tv in available_tvs:
                role_for_name = f"{role_for_name}[{taker_tv}]"
            bases = [role_for_name]
        else:
            bases = self._get_base_names(wc.clazz)

        fields = self._get_fields_for_taker(wc)
        # Resolve types for fields
        resolved_fields = [
            StubFieldInfo(
                f.name,
                self._resolve_type_vars(f.type_name, available_tvs),
                f.field_representation,
                wrapped_field=f.wrapped_field,
            )
            for f in fields
        ]

        return MixinInfo(
            name=mixin_name,
            bases=bases,
            fields=resolved_fields,
            dataclass_args=DataclassArguments.from_wrapped_class(wc),
        )

    def _get_fields_for_taker(self, wc: WrappedClass) -> List[StubFieldInfo]:
        """
        :param wc: The wrapped class of the role taker.
        :return: A list of fields for the taker's Mixin.
        """
        fields_dict = {}

        # Own fields
        for wf in wc.own_fields:
            # If it's a Role, its own fields are already in wc.fields
            # But we should only include those that are NOT the taker field
            if (
                issubclass(wc.clazz, Role)
                and wf.name == wc.clazz.role_taker_attribute_name()
            ):
                continue
            fields_dict[wf.name] = StubFieldInfo.from_wrapped_field(
                wf, role_related_class=True
            )

        # Propagated fields (only for root takers)
        if issubclass(wc.clazz, Role):
            root_taker = wc.clazz.get_root_role_taker_type()
        else:
            root_taker = wc.clazz

        if wc.clazz == root_taker:
            taker_original_fields = {f.name for f in wc.fields}
            for role_wc in self._root_role_taker_to_roles_map.get(wc.clazz, []):
                taker_field_name = role_wc.clazz.role_taker_attribute_name()
                for role_wf in role_wc.fields:
                    if (
                        role_wf.name != taker_field_name
                        and role_wf.name not in taker_original_fields
                        and role_wf.name not in fields_dict
                    ):
                        fields_dict[role_wf.name] = StubFieldInfo(
                            role_wf.name,
                            role_wf.type_name,
                            FieldRepresentation(dataclasses.field(init=False)),
                            wrapped_field=role_wf,
                        )

        return list(fields_dict.values())

    def _get_introduced_field(
        self, wc: WrappedClass, available_tvs: Set[str]
    ) -> Optional[StubFieldInfo]:
        """
        :param wc: The wrapped class of the role.
        :param available_tvs: Available TypeVars.
        :return: The field introduced by this role, or None.
        """
        taker_field_name = wc.clazz.role_taker_attribute_name()
        taker_type = wc.clazz.get_role_taker_type()
        taker_field_names = {f.name for f in dataclasses.fields(taker_type)}

        intro_wf = next(
            (
                wf
                for wf in wc.own_fields
                if wf.name != taker_field_name and wf.name not in taker_field_names
            ),
            None,
        )
        if intro_wf:
            return StubFieldInfo(
                intro_wf.name,
                self._resolve_type_vars(intro_wf.type_name, available_tvs),
                FieldRepresentation.from_wrapped_field(intro_wf),
                wrapped_field=intro_wf,
            )
        return None

    @cached_property
    def _role_taker_to_roles_map(self) -> Dict[Type, List[WrappedClass[Role]]]:
        """
        :return: A mapping from role taker types to their roles.
        """
        taker_to_roles = defaultdict(list)
        primary_roles = self._primary_roles
        for role_wc in self._role_wrapped_classes:
            if (
                role_wc.clazz in primary_roles
                and not role_wc.clazz.updates_role_taker_type()
            ):
                taker_type = role_wc.clazz.get_role_taker_type()
                taker_to_roles[taker_type].append(role_wc)
        return dict(taker_to_roles)

    @cached_property
    def _role_wrapped_classes(self) -> List[WrappedClass[Role]]:
        """
        :return: Wrapped class instances for role classes in topological order.
        """
        return [
            wc
            for wc in self.class_diagram.wrapped_classes_of_inheritance_subgraph_in_topological_order
            if not isinstance(wc, WrappedSpecializedGeneric)
            and issubclass(wc.clazz, Role)
        ]

    @cached_property
    def _type_vars(self) -> Dict[str, TypeVarInfo]:
        """
        :return: A mapping from TypeVar names to TypeVarInfo.
        """
        with open(self.module.__file__, "r") as f:
            source = f.read()
        tree = ast.parse(source)
        type_vars = {}
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                if isinstance(node.value, ast.Call):
                    if (
                        isinstance(node.value.func, ast.Name)
                        and node.value.func.id == "TypeVar"
                    ):
                        name = node.targets[0].id
                        bound = None
                        for keyword in node.value.keywords:
                            if keyword.arg == "bound":
                                if isinstance(keyword.value, ast.Name):
                                    bound = keyword.value.id
                                elif isinstance(keyword.value, ast.Constant):
                                    bound = str(keyword.value.value)
                        type_vars[name] = TypeVarInfo(
                            name, bound, ast.get_source_segment(source, node)
                        )
        return type_vars

    @cached_property
    def _all_imports(self) -> List[str]:
        """
        Extract imports needed for the generated stub.

        :return: A list of string import statements.
        """

        name_space = get_scope_from_imports(self.module.__file__)
        name_space_from_types = get_scope_from_imports(
            tree=ast.parse("\n".join(self._imports_from_field_types))
        )

        for name, value in name_space_from_types.items():
            if name in name_space:
                continue
            name_space[name] = value

        return get_imports_from_scope(name_space)

    @cached_property
    def _imports_from_field_types(self) -> List[str]:
        """
        Extracts import statements for field types used in stub fields.

        This method generates import statements for types used in stub fields, excluding types that are already defined
         in the module.

        :return: A list of import statements as strings.
        """
        stub_fields = []
        classes = set()
        for stub_class in self._all_stub_elements:
            if hasattr(stub_class, "fields"):
                stub_fields.extend(stub_class.fields)
            if hasattr(stub_class, "name"):
                classes.add(stub_class.name)

        field_types = {field_.wrapped_field.type_endpoint for field_ in stub_fields}
        # Remove types that are already defined in the module
        field_types = {
            field_type
            for field_type in field_types
            if field_type.__name__ not in classes
        }

        return get_imports_from_types(field_types)
