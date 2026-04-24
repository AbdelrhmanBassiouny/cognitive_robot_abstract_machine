from __future__ import annotations

import dataclasses
import inspect
import sys
from copy import copy
from pathlib import Path
from textwrap import dedent
from types import ModuleType
from typing import (
    List,
    Optional,
    Type,
)

import libcst
import rustworkx as rx
from functools import lru_cache
from libcst.codemod import ContextAwareTransformer, CodemodContext
from libcst.codemod.visitors import AddImportsVisitor
from typing_extensions import Dict, Tuple, Callable

from krrood.class_diagrams import ClassDiagram
from krrood.class_diagrams.class_diagram import WrappedClass
from krrood.class_diagrams.exceptions import ClassIsUnMappedInClassDiagram
from krrood.class_diagrams.utils import classes_of_module
from krrood.class_diagrams.wrapped_field import WrappedField, FieldRepresentation
from krrood.exceptions import SubprocessExecutionError
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
    file_name_prefix: str = ""

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

    def transform(self, write: bool = False) -> Dict[ModuleType, Tuple[str, str]]:
        """
        Transforms the module and its taker modules, generating mixins for each role taker. If write is True,
         writes the generated edits to the file system and runs ruff and black on the generated files.

        :return: A dictionary mapping each transformed module to a tuple of its transformed module content and its mixin module content.
        """
        import importlib

        all_modules = list(self.taker_modules)
        if self.module not in all_modules:
            all_modules.append(self.module)

        for m in all_modules:
            importlib.reload(m)
        self._build_diagram()

        all_modules_sources = {}
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

            mixin_result = transformer.transform_module(tree)
            # Run AddImportsVisitor on the mixin module
            mixin_result = AddImportsVisitor(context).transform_module(mixin_result)

            # Run AddImportsVisitor on the transformed original module
            transformed_original = transformer.transformed_module
            transformed_original = AddImportsVisitor(
                transformer.original_context
            ).transform_module(transformed_original)

            module_source = transformed_original.code
            mixin_source = mixin_result.code

            all_modules_sources[module] = (module_source, mixin_source)

            if write:
                original_path = self.get_generated_file_path(module, is_mixin=False)
                mixin_path = self.get_generated_file_path(module, is_mixin=True)
                for path, content in [
                    (original_path, module_source),
                    (mixin_path, mixin_source),
                ]:
                    with open(path, "w") as f:
                        f.write(content)
                    try:
                        run_ruff_on_file(str(path))
                        run_black_on_file(str(path))
                    except (RuntimeError, SubprocessExecutionError) as e:
                        print(f"Error formatting generated file {path}: {e}")

        return all_modules_sources

    def __hash__(self):
        return hash((self.__class__, self.module))

    def __eq__(self, other):
        return hash(self) == hash(other)

    @staticmethod
    @lru_cache
    def get_module_file_path(module: ModuleType) -> Path:
        """
        :return: Path to the module file.
        """
        return Path(sys.modules[module.__name__].__file__)

    @lru_cache
    def get_generated_file_path(self, module: ModuleType, is_mixin: bool = False) -> Path:
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
        module_name = module.__name__.split(".")[-1]
        if is_mixin:
            filename = f"{module_name}_role_mixins.py"
        else:
            prefix = copy(self.file_name_prefix)
            if prefix and not prefix.endswith("_"):
                prefix = f"{prefix}_"
            filename = f"{prefix}{module_name}.py"

        return role_mixins_folder / filename


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
        self.role_attributes: Dict[WrappedClass, libcst.ClassDef] = {}
        self.role_for: Dict[WrappedClass, libcst.ClassDef] = {}
        self.transformed_module: Optional[libcst.Module] = None
        self.original_context = CodemodContext()

    def require_original_import(
        self, module: str, obj: str | List[str] | None = None
    ) -> None:
        """
        Requires an import in the original (transformed) module.
        """
        if obj is None:
            AddImportsVisitor.add_needed_import(self.original_context, module)
        elif isinstance(obj, str):
            AddImportsVisitor.add_needed_import(self.original_context, module, obj)
        else:
            for o in obj:
                AddImportsVisitor.add_needed_import(self.original_context, module, o)

    def leave_ClassDef(
        self, original_node: libcst.ClassDef, updated_node: libcst.ClassDef
    ) -> libcst.ClassDef | libcst.FlattenSentinel[libcst.BaseCompoundStatement]:
        """
        Transforms class definitions: prunes methods, renames takers, and adjusts roles.
        """
        print(f"DEBUG: Visiting class {updated_node.name.value}")
        wrapped_class = None
        for wc in self.class_diagram.wrapped_classes:
            if wc.clazz.__name__ == updated_node.name.value:
                wrapped_class = wc
                break

        if wrapped_class is None:
            print(f"DEBUG:   Class {updated_node.name.value} not found in ClassDiagram")
            return updated_node

        is_taker = wrapped_class.clazz in self.class_diagram.role_takers

        result_nodes = [updated_node]
        if is_taker:
            # transform_role_taker returns [original_class]
            result_nodes = self._transform_role_taker(updated_node, wrapped_class)
            updated_node = result_nodes[0]

        role_type = RoleType.get_role_type(wrapped_class)
        print(f"DEBUG:   role_type for {updated_node.name.value}: {role_type}")

        if role_type != RoleType.NOT_A_ROLE:
            updated_node = self._transform_role(updated_node, wrapped_class)
            result_nodes[0] = updated_node

        if len(result_nodes) > 1:
            return libcst.FlattenSentinel(result_nodes)
        return result_nodes[0]

    def leave_Module(
        self, original_node: libcst.Module, updated_node: libcst.Module
    ) -> libcst.Module:
        self.transformed_module = updated_node
        self._add_required_mixin_imports()

        mixin_body = []
        all_mixin_classes = list(self.role_attributes.values()) + list(
            self.role_for.values()
        )

        used_names = self._collect_used_names_in_mixins(all_mixin_classes)
        self._add_typing_imports(used_names)

        type_checking_block = self._create_type_checking_block(used_names, all_mixin_classes)
        if type_checking_block:
            mixin_body.append(type_checking_block)

        mixin_body.extend(all_mixin_classes)

        return libcst.Module(
            body=mixin_body, header=updated_node.header, footer=updated_node.footer
        )

    def _add_required_mixin_imports(self) -> None:
        self.require_import("dataclasses", ["dataclass", "field"])
        self.require_import("abc", ["ABC", "abstractmethod"])
        self.require_import("typing_extensions", ["TYPE_CHECKING"])

    def _collect_used_names_in_mixins(self, mixin_classes: List[libcst.ClassDef]) -> set[str]:
        used_names = set()

        class NameCollector(libcst.CSTVisitor):
            def __init__(self):
                self.names = set()

            def visit_Name(self, node: libcst.Name) -> None:
                self.names.add(node.value)

        for class_def in mixin_classes:
            collector = NameCollector()
            class_def.visit(collector)
            used_names.update(collector.names)
        return used_names

    def _add_typing_imports(self, used_names: set[str]) -> None:
        typing_names = {
            "List", "Set", "Optional", "Union", "Tuple", "Type", "TypeVar", "Any", "Callable"
        }
        for name in used_names:
            if name in typing_names:
                self.require_import("typing", name)

    def _create_type_checking_block(
        self, used_names: set[str], mixin_classes: List[libcst.ClassDef]
    ) -> Optional[libcst.If]:
        import_map = self._build_mixin_import_map(used_names, mixin_classes)
        if not import_map:
            return None

        type_checking_body = []
        for module_name, names in sorted(import_map.items()):
            type_checking_body.append(self._create_import_from_node(module_name, names))

        return libcst.If(
            test=libcst.Name("TYPE_CHECKING"),
            body=libcst.IndentedBlock(body=type_checking_body),
        )

    def _build_mixin_import_map(
        self, used_names: set[str], mixin_classes: List[libcst.ClassDef]
    ) -> Dict[str, set[str]]:
        typing_names = {"List", "Set", "Optional", "Union", "Tuple", "Type", "TypeVar", "Any", "Callable"}
        common_names = {"dataclass", "field", "ABC", "abstractmethod", "TYPE_CHECKING", "Role", "Symbol"}
        common_names.update(typing_names)
        mixin_defined_names = {cd.name.value for cd in mixin_classes}

        import_map = {}
        for name in used_names:
            if name in common_names or name in mixin_defined_names:
                continue

            module_name = self._resolve_name_to_module(name)
            if module_name:
                import_map.setdefault(module_name, set()).add(name)
        return import_map

    def _resolve_name_to_module(self, name: str) -> Optional[str]:
        # 1. Check if it's in original module globals
        if name in self.module_.__dict__:
            obj = self.module_.__dict__[name]
            if hasattr(obj, "__module__"):
                return obj.__module__
            return self.module_.__name__

        # 2. Check ClassDiagram
        for wrapped in self.class_diagram.wrapped_classes:
            if wrapped.clazz.__name__ == name:
                return wrapped.clazz.__module__

        # 3. Heuristic for TypeVars
        if name.startswith("T"):
            return self.module_.__name__
        return None

    def _create_import_from_node(self, module_name: str, names: set[str]) -> libcst.SimpleStatementLine:
        curr_pkg = ".".join(self.module_.__name__.split(".")[:-1])
        target_pkg = ".".join(module_name.split(".")[:-1])

        if curr_pkg == target_pkg:
            rel_module = module_name.split(".")[-1]
            dots = 2
        else:
            rel_module = module_name
            dots = 0

        return libcst.SimpleStatementLine(
            body=[
                libcst.ImportFrom(
                    module=libcst.Name(rel_module) if rel_module else None,
                    names=[libcst.ImportAlias(name=libcst.Name(n)) for n in sorted(names)],
                    relative=[libcst.Dot()] * dots if dots else [],
                )
            ]
        )

    def _transform_role_taker(
        self, role_taker_node: libcst.ClassDef, wrapped_class: WrappedClass
    ) -> List[libcst.ClassDef]:
        """
        Transforms a role taker class into a Mixin and a re-entry class.
        """

        self.make_role_for_node(role_taker_node, wrapped_class)

        if self.should_make_role_attributes_for_node(role_taker_node, wrapped_class):
            self.make_role_attributes_node(wrapped_class)
            role_attributes_name = self.get_role_attributes_name(wrapped_class)
            role_taker_class_bases = list(role_taker_node.bases)
            role_taker_class_bases.insert(0, self.make_argument(role_attributes_name))
            role_taker_node = role_taker_node.with_changes(bases=role_taker_class_bases)

            mixin_module_name = f".{self.module_.__name__.split('.')[-1]}_role_mixins"
            self.require_original_import(mixin_module_name, [role_attributes_name])

        return [role_taker_node]

    @lru_cache
    def should_make_role_attributes_for_node(
        self, node: libcst.ClassDef, wrapped_class: WrappedClass
    ) -> bool:
        """
        Whether to make role attributes class for the given class node.

        :param node: The role taker class node to check.
        :param wrapped_class: The wrapped class of the role taker.
        """
        return not (
            any(self._is_role_base(base.value) for base in node.bases)
            or self.bases_of_class_that_are_role_takers(wrapped_class)
        )

    @lru_cache
    def bases_of_class_that_are_role_takers(
        self, wrapped_class: WrappedClass
    ) -> Dict[str, Type]:
        """
        :param wrapped_class: Wrapped class of the role taker.
        :return: Dictionary of base class names to base class types for role takers.
        """
        return {
            b.__name__: b
            for b in wrapped_class.clazz.__bases__
            if b in self.class_diagram.role_takers
        }

    def transform_original_role_taker_node(
        self,
        node: libcst.ClassDef,
        wrapped_class: WrappedClass,
    ) -> libcst.ClassDef:
        """
        Transforms the original role taker class node by adding role attributes if necessary.

        :param node: The role taker class node to transform.
        :param wrapped_class: The wrapped class of the role taker.
        :return: The transformed role taker class node.
        """
        reentry_class_bases = list(node.bases)
        if self.should_make_role_attributes_for_node(node, wrapped_class):
            reentry_class_bases.insert(
                0, self.make_argument(self.get_role_attributes_name(wrapped_class))
            )
        return node.with_changes(bases=reentry_class_bases)

    def make_role_attributes_node(self, wrapped_class: WrappedClass) -> None:
        propagated_fields = self._get_propagated_fields(wrapped_class)
        role_attributes_node = self.make_dataclass(
            self.get_role_attributes_name(wrapped_class), body=propagated_fields
        )
        self.role_attributes[wrapped_class] = role_attributes_node

    @classmethod
    @lru_cache
    def get_role_attributes_name(cls, wrapped_class: WrappedClass) -> str:
        """
        :param wrapped_class: Wrapped class of the role taker.
        :return: Name of the role attributes dataclass.
        """
        return f"{wrapped_class.clazz.__name__}RoleAttributes"

    def make_role_for_node(
        self,
        node: libcst.ClassDef,
        wrapped_class: WrappedClass,
    ) -> None:
        """
        Create a RoleFor<RoleTaker> class for the given role taker class node. Roles of this role taker will inherit
        from this class.

        :param node: The role taker class node to transform.
        :param wrapped_class: The wrapped class of the role taker.
        """

        # create role for node from role taker
        role_for_name = self.get_role_for_name(wrapped_class.clazz)
        role_for_node = self.get_renamed_node(node, role_for_name)

        # update bases
        role_for_bases = self.make_role_for_bases(
            role_for_node,
            wrapped_class,
            self.get_role_attributes_name(wrapped_class),
        )
        role_for_node = role_for_node.with_changes(bases=role_for_bases)

        # create role for body from fields and methods of role taker and its bases
        all_taker_fields = []
        for base_name, taker_type in self.bases_of_class_that_are_role_takers(
            wrapped_class
        ).items():
            wrapped_taker = self.class_diagram.get_wrapped_class(taker_type)
            all_taker_fields.extend([f.name for f in wrapped_taker.fields])
        role_for_body = self.make_role_for_properties(wrapped_class, all_taker_fields)
        role_for_body.update(self.make_role_for_methods(wrapped_class))

        # update body
        flattened_role_for_body = [
            method_node
            for method_nodes in role_for_body.values()
            for method_node in method_nodes
        ]
        self.role_for[wrapped_class] = self.get_node_with_new_body(
            role_for_node, flattened_role_for_body
        )

    @classmethod
    def make_role_for_methods(
        cls, wrapped_class: WrappedClass
    ) -> Dict[str, List[libcst.FunctionDef]]:
        """
        Add methods to the role for class. Each method should have the same signature as the method in the role taker,
         and its body should call the method on the role taker.

        :param wrapped_class: Wrapped class of the role taker.
        :return: Dictionary mapping method names to their corresponding FunctionDef nodes.
        """
        role_for_body = {}
        for method_name, method_object in inspect.getmembers(
            wrapped_class.clazz, predicate=inspect.isfunction
        ):
            method_node = cls.make_method_node(method_name, method_object)
            if method_node is not None:
                role_for_body[method_name] = [method_node]
        return role_for_body

    @classmethod
    def make_method_node(
        cls, name: str, method: Callable
    ) -> Optional[libcst.FunctionDef]:
        """
        Creates a FunctionDef node for a given method, with the same signature and a body that calls the method on the role taker.

        :param name: The name of the method.
        :param method: The method to create the node for.
        :return: A libcst FunctionDef node representing the method.
        """
        try:
            method_source = inspect.getsource(method)
        except OSError as e:
            return None
        method_node = libcst.parse_module(dedent(method_source)).body[0]
        assert isinstance(method_node, libcst.FunctionDef)
        parameters = inspect.signature(method).parameters
        method_node = method_node.with_changes(
            body=libcst.IndentedBlock(
                [
                    libcst.parse_statement(
                        f"return self.role_taker.{name}({', '.join(parameters.keys())})"
                    )
                ]
            )
        )

        return method_node

    def make_role_for_bases(
        self,
        node: libcst.ClassDef,
        wrapped_class: WrappedClass,
        role_attributes_name: str,
    ) -> List[libcst.Arg]:
        """
        Generate arguments for the base classes of a role class, considering role takers and role attributes.

        :param node: The original taker class node.
        :param wrapped_class: The taker wrapped class.
        :param role_attributes_name: Name for the role attributes dataclass.
        """
        role_for_bases = []
        bases_that_are_takers = self.bases_of_class_that_are_role_takers(wrapped_class)
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

        if self.should_make_role_attributes_for_node(node, wrapped_class):
            role_for_bases.insert(0, self.make_argument(role_attributes_name))

        role_for_bases.append(self.make_argument("ABC"))

        return role_for_bases

    def make_role_for_properties(
        self, taker_wrapped_class: WrappedClass, all_taker_fields: List[str]
    ) -> Dict[str, List[libcst.FunctionDef]]:
        """
        Generate property getter and setter methods for role attributes based on role taker wrapped class fields.

        :param taker_wrapped_class: Wrapped class of the role taker.
        :param all_taker_fields: List of all fields of the role taker.
        :return: Dictionary mapping field names to lists of FunctionDef nodes representing property getter and setter methods.
        """
        role_for_properties: Dict[str, List[libcst.FunctionDef]] = {
            "role_taker": [
                self.make_property_getter_node(
                    "role_taker", taker_wrapped_class.clazz.__name__, "..."
                )
            ]
        }
        for field_ in taker_wrapped_class.fields:
            if field_.name in all_taker_fields:
                continue
            if field_.field.kw_only or field_.field.init:
                role_for_properties[field_.name] = (
                    self.make_property_getter_and_setter_nodes(
                        field_.name,
                        str(field_.field.type),
                        f"self.role_taker.{field_.name}",
                        f"self.role_taker.{field_.name} = value",
                    )
                )
        for property_name, property_value in inspect.getmembers(
            taker_wrapped_class.clazz, inspect.isdatadescriptor
        ):
            if not isinstance(property_value, property):
                continue
            return_annotation = (
                str(property_value.fget.__annotations__["return"])
                if "return" in property_value.fget.__annotations__
                else None
            )
            if property_value.fset is not None:
                role_for_properties[property_name] = (
                    self.make_property_getter_and_setter_nodes(
                        property_name,
                        return_annotation,
                        f"self.role_taker.{property_name}",
                        f"self.role_taker.{property_name} = value",
                    )
                )
            else:
                role_for_properties[property_name] = [
                    self.make_property_getter_node(
                        property_name,
                        return_annotation,
                        f"self.role_taker.{property_name}",
                    )
                ]
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
        decorators = [cls.make_decorator("property")]
        if return_statement == "...":
            decorators.insert(0, cls.make_decorator("abstractmethod"))
            body = [libcst.SimpleStatementLine([libcst.Expr(libcst.Ellipsis())])]
        else:
            body = [libcst.parse_statement(f"return {return_statement}")]

        return libcst.FunctionDef(
            decorators=decorators,
            name=libcst.Name(name),
            params=cls.make_function_parameters({"self": None}),
            returns=cls.make_annotation(type_) if type_ else None,
            body=libcst.IndentedBlock(body),
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
        return libcst.Decorator(decorator=libcst.parse_expression(decorator_name))

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
        print(f"DEBUG: Transforming role {wrapped_class.clazz.__name__}, type: {role_type}")
        if role_type == RoleType.NOT_A_ROLE:
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
        print(f"DEBUG:   role_bases keys: {list(role_bases.keys())}")
        for base in node.bases:
            new_bases.append(base)
            base_name = self.get_name_from_base_node(base.value)
            print(f"DEBUG:   Checking base {base_name}")

            # Check if this base is a Role class in our diagram
            is_role_base = False
            if base_name == "Role":
                is_role_base = True
            else:
                for wrapped in self.class_diagram.wrapped_classes:
                    if (
                        wrapped.clazz.__name__ == base_name
                        and issubclass(wrapped.clazz, Role)
                    ):
                        is_role_base = True
                        break

            if is_role_base:
                role_for_name = self.get_role_for_name(taker_type)
                print(f"DEBUG:   Adding {role_for_name}")
                new_bases.append(self.make_argument(role_for_name))

                taker_module = sys.modules[taker_type.__module__]
                mixin_module_name = (
                    f".{taker_module.__name__.split('.')[-1]}_role_mixins"
                )
                self.require_original_import(mixin_module_name, [role_for_name])

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

    def _create_field_node(
        self,
        wrapped_field: WrappedField,
        init: bool = True,
        kw_only: Optional[bool] = None,
    ) -> libcst.SimpleStatementLine:
        """
        Creates a libcst SimpleStatementLine node for a field.
        """
        self.require_import(
            wrapped_field.type_endpoint.__module__,
            [wrapped_field.type_endpoint.__name__],
        )
        if wrapped_field.is_container:
            self.require_import(
                wrapped_field.container_type.__module__,
                [wrapped_field.container_type.__name__],
            )

        f_copy = copy(wrapped_field.field)
        if not init:
            f_copy.init = False
            # Clear defaults to match GT for init=False
            f_copy.default = dataclasses.MISSING
            f_copy.default_factory = dataclasses.MISSING
            f_copy.kw_only = False
        else:
            # Match FieldRepresentation logic for role-related classes
            f_copy.kw_only = f_copy.kw_only or (
                not wrapped_field.is_required and f_copy.init
            )

        if kw_only is not None:
            f_copy.kw_only = kw_only

        rep_obj = FieldRepresentation(f_copy)
        rep_str = rep_obj.representation.strip()

        if rep_str.startswith("="):
            val_str = rep_str[1:].strip()
            try:
                value_cst = libcst.parse_expression(val_str)
            except Exception:
                value_cst = libcst.Name("None")
        else:
            value_cst = None

        type_str = wrapped_field.type_name

        type_str = type_str.replace("typing.", "").replace("typing_extensions.", "")

        return libcst.SimpleStatementLine(
            body=[
                libcst.AnnAssign(
                    target=libcst.Name(wrapped_field.name),
                    annotation=libcst.Annotation(
                        annotation=self.to_cst_expression(type_str)
                    ),
                    value=value_cst,
                )
            ]
        )

    def require_import(self, module: str, names: List[str]):
        """
        Add an import statement to the module context.
        """
        if module in ["builtins", self.module_.__name__]:
            return
        for name in names:
            AddImportsVisitor.add_needed_import(
                self.context,
                module=module,
                obj=name,
            )

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
