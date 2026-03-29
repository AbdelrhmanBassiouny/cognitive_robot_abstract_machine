from __future__ import annotations

import dataclasses
import sys
from copy import copy
from pathlib import Path
from types import ModuleType
from typing import (
    List,
    Optional,
    Type,
)

import libcst
import rustworkx as rx
from black.handle_ipynb_magics import lru_cache
from libcst.codemod import ContextAwareTransformer, CodemodContext
from libcst.codemod.visitors import AddImportsVisitor
from typing_extensions import Dict, Tuple, Callable

from krrood.class_diagrams import ClassDiagram
from krrood.class_diagrams.class_diagram import WrappedClass
from krrood.class_diagrams.exceptions import ClassIsUnMappedInClassDiagram
from krrood.class_diagrams.utils import classes_of_module
from krrood.class_diagrams.wrapped_field import WrappedField
from krrood.patterns.role.meta_data import RoleType
from krrood.patterns.role.role import Role
from krrood.utils import (
    run_black_on_file,
    run_ruff_on_file,
)


@dataclasses.dataclass
class RoleTransformer:
    """
    Transform classes related to roles to inherit from the generated mixins that add the gained attributes and to adjust
     their fields. Also generates these mixin classes for role takers.
    """

    module: ModuleType
    taker_modules: List[ModuleType] = dataclasses.field(default_factory=list)
    class_diagram: ClassDiagram = dataclasses.field(init=False)
    path: Optional[Path] = None

    def __post_init__(self):
        if self.path is None:
            self.path = self.get_generated_file_path(self.module)
        self._build_diagram()

    def _build_diagram(self):
        classes = classes_of_module(self.module)
        role_classes = [clazz for clazz in classes if issubclass(clazz, Role)]
        for clazz in role_classes:
            role_taker_type = clazz.get_role_taker_type()
            if role_taker_type not in classes:
                classes.append(role_taker_type)
                role_taker_module = sys.modules[role_taker_type.__module__]
                if role_taker_module not in self.taker_modules:
                    self.taker_modules.append(role_taker_module)
        self.class_diagram = ClassDiagram(classes)

    def transform(self, write: bool = False) -> Dict[ModuleType, str]:
        """
        Transforms the module and its taker modules, generating mixins for each role taker. If write is True,
         writes the generated edits to the file system and runs ruff and black on the generated files.

        :return: A dictionary mapping each transformed module to its mixin module content.
        """
        all_modules = list(self.taker_modules)
        if self.module not in all_modules:
            all_modules.append(self.module)
        all_stub_contents = {}
        for module in all_modules:
            with open(self.get_module_file_path(module), "r") as f:
                source = f.read()

            context = CodemodContext()

            transformer = RoleModuleTransformer(
                context=context,
                class_diagram=self.class_diagram,
                module=module,
                taker_modules=self.taker_modules,
            )
            tree = libcst.parse_module(source)

            result = transformer.transform_module(tree)
            # Run AddImportsVisitor as a second pass
            result = AddImportsVisitor(context).transform_module(result)

            stub_content = result.code

            all_stub_contents[module] = stub_content

            if write:
                path = self.get_generated_file_path(module)
                with open(path, "w") as f:
                    f.write(stub_content)
                try:
                    run_ruff_on_file(str(path))
                    run_black_on_file(str(path))
                except RuntimeError as e:
                    print(f"Error generating stub for {module}: {e}")
                    raise

        return all_stub_contents

    @staticmethod
    @lru_cache
    def get_module_file_path(module: ModuleType) -> Path:
        """
        :return: Path to the module file.
        """
        return Path(sys.modules[module.__name__].__file__)

    @staticmethod
    @lru_cache
    def get_generated_file_path(module: ModuleType) -> Path:
        """
        :return: Path to the generated stub file.
        """
        # add role mixins folder if it does not exist, and add a __init__.py file to it
        parent_directory = Path(RoleTransformer.get_module_file_path(module)).parent
        postfix = "role_mixins"
        role_mixins_folder = parent_directory / postfix
        role_mixins_folder.mkdir(exist_ok=True)
        init_file_path = role_mixins_folder / "__init__.py"
        if not init_file_path.exists():
            init_file_path.touch()
        # Generate a new file containing the mixin classes in the role_mixins folder
        mixin_file_path = (
            role_mixins_folder / f"{module.__name__.split('.')[-1]}_{postfix}.py"
        )
        return mixin_file_path


class RoleModuleTransformer(ContextAwareTransformer):
    """
    Transforms a Python module AST into a mixin classes file AST by pruning methods
    and applying the Role pattern transformations.
    """

    def __init__(
        self,
        context: CodemodContext,
        class_diagram: ClassDiagram,
        module: ModuleType,
        taker_modules: List[ModuleType],
    ):
        super().__init__(context)
        self.class_diagram = class_diagram
        self.module_ = module
        self.taker_modules = taker_modules

    @lru_cache
    def _has_primary_role(self, taker_type: Type) -> bool:
        """
        Checks if there is at least one primary role targeting this taker
        that does not update its taker type.
        """
        roles = self.class_diagram.get_roles_of_class(taker_type)
        return any(
            RoleType.get_role_type(role_wrapped) == RoleType.PRIMARY
            for role_wrapped in roles
        )

    @classmethod
    def unparse_type_value(cls, value: libcst.BaseExpression) -> Optional[str]:
        """
        Unparses a libcst expression to get the type name as a string.
        """
        if isinstance(value, libcst.Name):
            return value.value
        elif isinstance(value, libcst.SimpleString):
            return value.evaluated_value
        else:
            raise ValueError(f"Unsupported type value: {value}")

    @classmethod
    def get_keyword_value_from_call(
        cls, call: libcst.Call, keyword: str
    ) -> Optional[libcst.BaseExpression]:
        for kw in call.args:
            if kw.keyword and kw.keyword.value == keyword:
                return kw.value
        return None

    def leave_ClassDef(
        self, original_node: libcst.ClassDef, updated_node: libcst.ClassDef
    ) -> libcst.ClassDef | libcst.FlattenSentinel[libcst.BaseCompoundStatement]:
        """
        Transforms class definitions: prunes methods, renames takers, and adjusts roles.
        """
        if updated_node.name.value not in self.module_.__dict__:
            return updated_node
        clazz = self.module_.__dict__[updated_node.name.value]
        try:
            wrapped_class = self.class_diagram.get_wrapped_class(clazz)
        except ClassIsUnMappedInClassDiagram:
            return updated_node

        # Prune methods and non-essential nodes
        new_body_list = [item.visit(self) for item in updated_node.body.body]
        updated_node = updated_node.with_changes(
            body=updated_node.body.with_changes(body=new_body_list)
        )

        is_taker = wrapped_class.clazz in self.class_diagram.role_takers

        if is_taker:
            # transform_role_taker returns [Mixin, original_class]
            result_nodes = self._transform_role_taker(updated_node, wrapped_class)
            return libcst.FlattenSentinel(result_nodes)
        else:
            result_nodes = [updated_node]

        role_type = RoleType.get_role_type(wrapped_class)

        match role_type:
            case RoleType.NOT_A_ROLE:
                ...
            case _:
                updated_node = self._transform_role(updated_node, wrapped_class)
                old_node = next(
                    (rn for rn in result_nodes if rn.name == updated_node.name), None
                )
                if old_node is not None:
                    result_nodes.remove(old_node)
                result_nodes.append(updated_node)

        if len(result_nodes) > 1:
            return libcst.FlattenSentinel(result_nodes)
        return result_nodes[0]

    def leave_Module(self, original_node, updated_node):
        self.require_import("dataclasses", ["dataclass", "field"])
        return updated_node

    def _has_type_var_for_taker(self, taker_type: Type) -> bool:
        """
        Checks if a TypeVar bound to this taker exists in the module.
        """
        return self._get_type_var_name(taker_type) is not None

    def _transform_specialized_role(
        self, node: libcst.ClassDef, wrapped_class: WrappedClass[Role]
    ) -> List[libcst.ClassDef]:
        """
        Handles a role that updates its taker type by synthesizing a specialized (due to role taker type update)
         RoleFor base.

        :param node: The original class node.
        :param wrapped_class: The wrapped class for the role.
        """
        taker_type = wrapped_class.clazz.get_role_taker_type()
        base_role = next(
            clazz for clazz in wrapped_class.clazz.__bases__ if issubclass(clazz, Role)
        )
        specialized_name = f"{base_role.__name__}AsRoleFor{taker_type.__name__}"

        # TSubclassOfARoleTaker
        type_var_name = self._get_type_var_name(taker_type) or f"T{taker_type.__name__}"
        available_type_vars = {type_var_name}

        # Specialized base: CEOAsFirstRoleAsRoleForSubclassOfARoleTaker(CEOAsFirstRole[TSubclassOfARoleTaker], SubclassOfARoleTakerMixin)
        specialized_bases = [
            f"{taker_type.__name__}Mixin",
            f"{base_role.__name__}[{type_var_name}]",
        ]

        # Add fields from taker as init=False
        wrapped_taker = self.class_diagram.get_wrapped_class(taker_type)
        body = [
            self._create_field_node(
                field_, init=False, available_type_vars=available_type_vars
            )
            for field_ in wrapped_taker.fields
            if field_.field.init or field_.field.kw_only
        ]

        specialized_class = self.make_dataclass(
            name=specialized_name,
            bases=specialized_bases,
            body=body,
        )

        # Current class inherits from specialized base
        node = node.with_changes(
            bases=[self.make_argument(specialized_name)],
            body=self.make_ellipsis_body(),
        )

        return [specialized_class, node]

    def _transform_role_taker(
        self, node: libcst.ClassDef, wrapped_class: WrappedClass
    ) -> List[libcst.ClassDef]:
        """
        Transforms a role taker class into a Mixin and a re-entry class.
        """
        original_name = node.name.value
        role_for_name = self.get_role_for_name(wrapped_class.clazz)
        role_attributes_name = f"{original_name}RoleAttributes"
        bases_that_are_takers = {
            b.__name__: b
            for b in wrapped_class.clazz.__bases__
            if b in self.class_diagram.role_takers
        }
        make_role_attributes = not (
            any(self._is_role_base(base.value) for base in node.bases)
            or bases_that_are_takers
        )
        role_for_node = self.get_renamed_node(node, role_for_name)

        all_taker_fields = []
        for base_name, taker_type in bases_that_are_takers.items():
            wrapped_taker = self.class_diagram.get_wrapped_class(taker_type)
            all_taker_fields.extend([f.name for f in wrapped_taker.fields])

        role_for_body = self.make_role_for_properties(wrapped_class, all_taker_fields)

        role_for_node = self.get_node_with_new_body(role_for_node, role_for_body)
        role_for_bases = self.make_role_for_bases(
            node,
            wrapped_class,
            bases_that_are_takers,
            make_role_attributes,
            role_attributes_name,
        )
        role_for_node = role_for_node.with_changes(bases=role_for_bases)

        reentry_node_bases = list(node.bases)
        if make_role_attributes:
            reentry_node_bases.insert(0, self.make_argument(role_attributes_name))
        reentry_class = node.with_changes(bases=reentry_node_bases)

        if make_role_attributes:
            propagated_fields = self._get_propagated_fields(wrapped_class)
            role_attributes_node = self.make_dataclass(
                role_attributes_name, body=propagated_fields
            )
            return [role_attributes_node, role_for_node, reentry_class]
        else:
            return [role_for_node, reentry_class]

    def make_role_for_bases(
        self,
        node: libcst.ClassDef,
        wrapped_class: WrappedClass,
        bases_that_are_takers: Dict[str, Type],
        make_role_attributes: bool,
        role_attributes_name: str,
    ) -> List[libcst.Arg]:
        """
        Generate arguments for the base classes of a role class, considering role takers and role attributes.

        :param node: The original taker class node.
        :param wrapped_class: The taker wrapped class.
        :param bases_that_are_takers: Dictionary mapping base class names to their corresponding role taker types.
        :param make_role_attributes: Flag indicating whether to include role attributes in the generated arguments.
        :param role_attributes_name: Name for the role attributes dataclass.
        """
        role_for_bases = []
        for base in node.bases:
            base_name = self.get_name_from_base_node(base.value)
            if base_name in bases_that_are_takers:
                taker_role_for = self.make_argument(
                    self.get_role_for_name(bases_that_are_takers[base_name])
                )
                role_for_bases.append(taker_role_for)
            elif self._is_role_base(base.value) and issubclass(
                wrapped_class.clazz, Role
            ):
                taker_type = wrapped_class.clazz.get_role_taker_type()
                taker_role_for = self.make_argument(self.get_role_for_name(taker_type))
                role_for_bases.append(taker_role_for)

        if make_role_attributes:
            role_for_bases.insert(0, self.make_argument(role_attributes_name))

        return role_for_bases

    def make_role_for_properties(
        self, taker_wrapped_class: WrappedClass, all_taker_fields: List[str]
    ) -> List[libcst.FunctionDef]:
        """
        Generate property getter and setter methods for role attributes based on role taker wrapped class fields.

        :param taker_wrapped_class: Wrapped class of the role taker.
        :param all_taker_fields: List of all fields of the role taker.
        :return: List of FunctionDef nodes representing property getter and setter methods.
        """
        role_for_properties = [
            self.make_property_getter_node(
                "role_taker", taker_wrapped_class.clazz.__name__, "..."
            )
        ]
        for field_ in taker_wrapped_class.fields:
            if field_.name in all_taker_fields:
                continue
            if field_.field.kw_only or field_.field.init:
                role_for_properties.extend(
                    self.make_property_getter_and_setter_nodes(
                        field_.name,
                        str(field_.field.type),
                        f"self.role_taker.{field_.name}",
                        f"self.role_taker.{field_.name} = value",
                    )
                )
        return role_for_properties

    @classmethod
    def make_dataclass(
        cls,
        name: str,
        bases: Optional[List[Type | str]] = None,
        body: Optional[List[libcst.BaseStatement]] = None,
    ) -> libcst.ClassDef:
        """
        :param name: Name of the dataclass.
        :param bases: Base classes of the dataclass.
        :param body: Body of the dataclass.
        :return: libcst ClassDef object for the given dataclass.
        """
        return libcst.ClassDef(
            name=libcst.Name(name),
            bases=[libcst.Arg(value=cls.to_cst_expression(b)) for b in (bases or [])],
            body=libcst.IndentedBlock(
                body=body if body else [libcst.parse_statement("...")]
            ),
            decorators=[cls.make_dataclass_decorator()],
        )

    @classmethod
    def to_cst_expression(
        cls, has_name: Type | Callable | str
    ) -> libcst.BaseExpression:
        """
        :param has_name: An object that has a `__name__` attribute, one of class, method, or function.
        :return: libcst Expression object for the given name.
        """
        if isinstance(has_name, str):
            try:
                return libcst.parse_expression(has_name)
            except Exception:
                name = has_name
        elif hasattr(has_name, "__name__"):
            name = has_name.__name__
        else:
            name = str(has_name)
        name.replace("typing.", "").replace("typing_extensions.", "")
        return libcst.Name(name)

    @classmethod
    def make_dataclass_decorator(cls) -> libcst.Decorator:
        return libcst.Decorator(
            decorator=libcst.parse_expression("dataclass(eq=False)")
        )

    def make_property_getter_and_setter_nodes(
        self, name: str, type_: str, getter_return_statement: str, setter_statement: str
    ) -> List[libcst.FunctionDef]:
        """
        :param name: The name of the field for which to create getter and setter nodes.
        :param type_: The type annotation for the field.
        :param getter_return_statement: The value to be returned by the getter.
        :param setter_statement: The statement to be executed in the setter body.
        :return: A list containing the getter and setter FunctionDef nodes for the property.
         The getter returns the value of the field from the role taker, and the setter sets the value of the field on
          the role taker.
        """
        getter_node = self.make_property_getter_node(
            name, type_, getter_return_statement
        )
        setter_node = self.make_property_setter_node(name, type_, setter_statement)
        return [getter_node, setter_node]

    @classmethod
    def make_property_getter_node(
        cls, name: str, type_: str, return_statement: str
    ) -> libcst.FunctionDef:
        """
        :param name: The name of the field for which to create a getter node.
        :param type_: The type annotation for the field.
        :param return_statement: The value to be returned by the getter.
        :return: A libcst FunctionDef node representing the property getter.
        """
        return libcst.FunctionDef(
            decorators=[cls.make_decorator("property")],
            name=libcst.Name(name),
            params=cls.make_function_parameters({"self": None}),
            returns=cls.make_annotation(type_),
            body=libcst.IndentedBlock(
                [libcst.parse_statement(f"return {return_statement}")]
            ),
        )

    @classmethod
    def make_property_setter_node(
        cls, name: str, type_: str, statement: str
    ) -> libcst.FunctionDef:
        """
        :param name: The name of the field for which to create a setter node.
        :param type_: The type of the field.
        :param statement: The statement to be executed in the setter body.
        :return: A libcst FunctionDef node representing the property setter.
        """
        return libcst.FunctionDef(
            decorators=[cls.make_decorator(f"{name}.setter")],
            name=libcst.Name(name),
            params=cls.make_function_parameters({"self": None, "value": type_}),
            body=libcst.IndentedBlock(
                [libcst.parse_statement(f"self.role_taker.{name} = value")]
            ),
        )

    @classmethod
    def make_decorator(cls, decorator_name: str) -> libcst.Decorator:
        """
        Creates a libcst Decorator node with the given decorator name.

        :param decorator_name: The name of the decorator.
        :return: A libcst Decorator node.
        """
        return libcst.Decorator(decorator=libcst.Name(decorator_name))

    @classmethod
    def make_function_parameters(
        cls, parameters: Dict[str, Optional[str]]
    ) -> libcst.Parameters:
        """
        Creates a libcst Parameters object from a dictionary of parameter names and type annotations.

        :param parameters: A dictionary mapping parameter names to their type annotations.
        :return: A libcst Parameters object containing the parameters with annotations.
        """
        parameters = parameters or {}
        return libcst.Parameters(
            params=[
                libcst.Param(
                    name=libcst.Name(param),
                    annotation=(
                        cls.make_annotation(annotation)
                        if annotation is not None
                        else None
                    ),
                )
                for param, annotation in parameters.items()
            ]
        )

    @classmethod
    def make_annotation(cls, value: str) -> libcst.Annotation:
        """
        :param value: The type annotation as a string.
        :return: A libcst Annotation node representing the given type annotation.
        """
        return libcst.Annotation(libcst.parse_expression(value))

    @classmethod
    def make_return_statement_body(cls, statement: str) -> libcst.IndentedBlock:
        """
        Creates an IndentedBlock with a return statement that returns the parsed expression.
        """
        return libcst.IndentedBlock(
            body=[
                libcst.SimpleStatementLine(
                    body=[libcst.Return(value=libcst.parse_expression(statement))]
                )
            ]
        )

    @classmethod
    def get_node_with_new_body(
        cls, node: libcst.ClassDef, new_body: List[libcst.BaseStatement]
    ) -> libcst.ClassDef:
        """
        :param node: The node to update.
        :param new_body: The new body for the node.
        :return: A new node that is a copy of the original node but with the new body.
        """
        return node.with_changes(body=node.body.with_changes(body=new_body))

    @classmethod
    def get_renamed_node(cls, node, new_name):
        """
        :param node: The node to rename.
        :param new_name: The new name for the node.
        :return: A new node that is a copy of the original node but with the new name.
        """
        return node.with_changes(name=libcst.Name(new_name))

    @classmethod
    def make_argument(cls, value: str) -> libcst.Arg:
        """
        :param value: The value of the argument.
        :return: libcst Arg object with the given value.
        """
        return libcst.Arg(value=libcst.parse_expression(value))

    @classmethod
    def _is_role_base(cls, base_node: libcst.BaseExpression) -> bool:
        """
        Checks if a base node is the 'Role' class or 'Role[T]'.

        :param base_node: The base node to check.
        :return: True if the base node is 'Role' or 'Role[T]', False otherwise.
        """
        name = cls.get_name_from_base_node(base_node)
        return name == "Role"

    @classmethod
    def get_name_from_base_node(cls, base_node: libcst.BaseExpression) -> str:
        """
        Extracts the class name from a base node, handling both simple names and sub-scripted types.

        :param base_node: The base node to extract the class name from.
        :return: The class name as a string.
        """
        if isinstance(base_node, libcst.Name):
            return base_node.value
        if isinstance(base_node, libcst.Subscript):
            if isinstance(base_node.value, libcst.Name):
                return base_node.value.value
        raise ValueError(f"Unexpected base node type: {base_node}")

    @classmethod
    def _get_field_name_if_statement_is_field_definition(
        cls, item: libcst.BaseStatement
    ) -> Optional[str]:
        """
        :param item: The statement to check.
        :return: The field name if the statement is a field definition, otherwise None.
        """
        if (
            isinstance(item, libcst.SimpleStatementLine)
            and len(item.body) == 1
            and isinstance(ann_assign := item.body[0], libcst.AnnAssign)
            and isinstance(field_name := ann_assign.target, libcst.Name)
        ):
            return field_name.value
        return None

    def _transform_role(
        self, node: libcst.ClassDef, wrapped_class: WrappedClass
    ) -> libcst.ClassDef:
        """
        Transforms a primary role class by adjusting its bases and filtering fields.

        :param node: The original class node.
        :param wrapped_class: The wrapped class information.
        """
        role_type = RoleType.get_role_type(wrapped_class)
        if role_type not in [RoleType.PRIMARY, RoleType.SPECIALIZED_ROLE_FOR]:
            return node
        taker_type = wrapped_class.clazz.get_role_taker_type()

        # Filter out original Role bases and redundant bases
        new_bases = []

        role_bases = {
            base.__name__: base
            for base in wrapped_class.clazz.__bases__
            if base is Role
            or (issubclass(base, Role) and base.updates_role_taker_type())
        }
        for base in node.bases:
            if self.get_name_from_base_node(base.value) in role_bases:
                new_bases.append(self.make_argument(self.get_role_for_name(taker_type)))
            new_bases.append(base)

        return node.with_changes(bases=new_bases)

    @classmethod
    def get_role_for_name(cls, taker_class: Type) -> str:
        return f"RoleFor{taker_class.__name__}"

    def _get_propagated_fields(
        self, wrapped_class: WrappedClass
    ) -> List[libcst.BaseStatement]:
        """
        Get libcst nodes for fields propagated from roles to the root role taker.

        :param wrapped_class: The wrapped class for the role.
        :return: A list of libcst nodes representing the fields to be propagated.
        """
        # Only propagate to root takers
        root_taker = wrapped_class.clazz
        if issubclass(root_taker, Role):
            root_taker = root_taker.get_root_role_taker_type()

        if wrapped_class.clazz != root_taker:
            return []

        # Find all roles (recursive) for this taker
        roles = self._get_all_roles_for_taker(root_taker)

        # Exclude taker fields from roles
        possible_fields_to_propagate = []
        for role_wrapped in roles:
            taker_attr_name = role_wrapped.clazz.role_taker_attribute_name()
            possible_fields_to_propagate.extend(
                [
                    role_field
                    for role_field in role_wrapped.fields
                    if role_field.name != taker_attr_name
                ]
            )

        # Add unseen fields from roles to the root taker
        fields_to_propagate = []
        seen_field_names = {f.name for f in wrapped_class.fields}
        for role_field in possible_fields_to_propagate:
            if role_field.name not in seen_field_names:
                fields_to_propagate.append(
                    self._create_field_node(role_field, init=False)
                )
                seen_field_names.add(role_field.name)

        return fields_to_propagate

    def _get_all_roles_for_taker(self, taker_type: Type) -> List[WrappedClass]:
        """
        Recursively finds all roles for a taker.
        """
        roles = []
        direct_roles = self.class_diagram.get_roles_of_class(taker_type)
        for role_wrapped in direct_roles:
            roles.append(role_wrapped)
            subclasses_of_role = rx.descendants(
                self.class_diagram.inheritance_subgraph, role_wrapped.index
            )
            roles.extend(
                [
                    self.class_diagram.inheritance_subgraph[idx]
                    for idx in subclasses_of_role
                ]
            )
            # A role can also be a taker
            roles.extend(self._get_all_roles_for_taker(role_wrapped.clazz))
        return roles

    def __hash__(self):
        return hash((self.__class__, self.module_))
