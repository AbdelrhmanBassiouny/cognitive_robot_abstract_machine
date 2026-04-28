"""
Role transformer: converts role-pattern modules into mixin-based equivalents.
"""

from __future__ import annotations

import dataclasses
import enum
import inspect
import sys
from copy import copy
from pathlib import Path
from textwrap import dedent
from types import ModuleType
from typing import (
    Any,
    Callable,
)

import libcst
import rustworkx as rx
from libcst.codemod import ContextAwareTransformer, CodemodContext
from libcst.codemod.visitors import AddImportsVisitor

from krrood import logger
from krrood.class_diagrams import ClassDiagram
from krrood.class_diagrams.class_diagram import WrappedClass
from krrood.class_diagrams.utils import (
    classes_of_module,
    get_type_hints_of_object,
    resolve_name_in_hierarchy,
)
from krrood.class_diagrams.wrapped_field import WrappedField, FieldRepresentation
from krrood.patterns.role.exceptions import RoleTransformerError
from krrood.patterns.role.import_name_resolver import ImportNameResolver
from krrood.patterns.role.meta_data import RoleType
from krrood.patterns.role.mixin_import_orchestrator import MixinImportOrchestrator
from krrood.patterns.role.role import Role
from krrood.patterns.role.role_mixin_file_writer import RoleMixinFileWriter
from krrood.patterns.role.role_node_factory import RoleNodeFactory
from krrood.patterns.role.type_name_normaliser import TypeNameNormaliser

GROUND_TRUTH = "_ground_truth_"
TRANSFORMED = "transformed_"

# Dataclass/object lifecycle hooks that should never be delegated regardless of origin.
# __new__ is defined on Symbol (a Role base) as a staticmethod; inspect.getmembers
# unwraps it to a plain function, so it must be excluded explicitly here.
_ALWAYS_EXCLUDED_METHODS: frozenset[str] = frozenset({"__init__", "__post_init__", "__new__"})


def _is_from_role_class(name: str, clazz: type) -> bool:
    """Return True if *name* is inherited from the Role hierarchy without being overridden.

    Walks the MRO of *clazz* and returns True iff the first class that defines *name*
    is itself a Role subclass, meaning the taker has not provided its own version.
    """
    for klass in clazz.__mro__:
        if name in vars(klass):
            return issubclass(klass, Role)
    return False


def build_role_diagram(
    module: ModuleType,
    taker_modules: list[ModuleType],
) -> tuple[ClassDiagram, list[ModuleType]]:
    """
    Build a ClassDiagram for the given module, auto-discovering role taker modules.

    :param module: The primary module containing role classes.
    :param taker_modules: The initial list of known taker modules.
    :return: A tuple of the constructed ClassDiagram and the updated taker_modules list.
    """
    classes = classes_of_module(module)
    role_classes = [clazz for clazz in classes if issubclass(clazz, Role)]
    updated_taker_modules = list(taker_modules)
    for clazz in role_classes:
        role_taker_type = clazz.get_role_taker_type()
        if role_taker_type not in classes:
            classes.append(role_taker_type)
            role_taker_module = sys.modules[role_taker_type.__module__]
            if role_taker_module not in updated_taker_modules:
                updated_taker_modules.append(role_taker_module)
    return ClassDiagram(classes), updated_taker_modules


class TransformationMode(str, enum.Enum):
    """
    Enumeration of transformation mode identifiers used as file-name prefixes.
    """

    GROUND_TRUTH = "_ground_truth_"
    TRANSFORMED = "transformed_"


@dataclasses.dataclass
class RoleTransformer:
    """
    Transform classes related to roles to inherit from the generated mixins
    that add the gained attributes and to adjust their fields.
    Also generates these mixin classes for role takers.
    """

    module: ModuleType
    taker_modules: list[ModuleType] = dataclasses.field(default_factory=list)
    class_diagram: ClassDiagram = dataclasses.field(init=False)
    path: Path | None = None
    file_name_prefix: str = ""

    def __post_init__(self):
        """
        Initialise the generated file path and build the class diagram.
        """
        if self.path is None:
            self.path = self.get_generated_file_path(self.module)
        self._refresh_diagram()

    def _refresh_diagram(self) -> None:
        """Rebuild the class diagram, updating taker_modules with any newly discovered ones."""
        self.class_diagram, self.taker_modules = build_role_diagram(
            self.module, self.taker_modules
        )

    def transform(self, write: bool = False) -> dict[ModuleType, tuple[str, str]]:
        """
        Transform the module and its taker modules, generating mixins for each role taker.

        :param write: When True, writes the generated edits to the file system and formats them.
        :return: A dictionary mapping each transformed module to a tuple of its transformed
                 module content and its mixin module content.
        """
        import importlib

        all_modules = list(self.taker_modules)
        if self.module not in all_modules:
            all_modules.append(self.module)

        for module in all_modules:
            importlib.reload(module)
        self._refresh_diagram()

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
                file_name_prefix=self.file_name_prefix,
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
            writer = RoleMixinFileWriter(file_name_prefix=self.file_name_prefix)
            writer.write(all_modules_sources, self.get_generated_file_path)

        return all_modules_sources

    def __hash__(self):
        return hash((self.__class__, self.module))

    def __eq__(self, other):
        return hash(self) == hash(other)

    @staticmethod
    def get_module_file_path(module: ModuleType) -> Path:
        """
        Return the file path of the given module.

        :param module: The module whose file path is needed.
        :return: Path to the module file.
        """
        return Path(sys.modules[module.__name__].__file__)

    def get_generated_file_path(
        self, module: ModuleType, is_mixin: bool = False
    ) -> Path:
        """
        Return the path where the generated file for the module should be written.

        :param module: The module for which to compute the generated path.
        :param is_mixin: Whether the path is for the mixin file rather than the transformed original.
        :return: Path to the generated file.
        """
        parent_directory = Path(RoleTransformer.get_module_file_path(module)).parent
        module_name = module.__name__.split(".")[-1]
        if is_mixin:
            # add role mixins folder if it does not exist, and add a __init__.py file to it
            postfix = "role_mixins"
            role_mixins_folder = parent_directory / postfix
            role_mixins_folder.mkdir(exist_ok=True)
            init_file_path = role_mixins_folder / "__init__.py"
            if not init_file_path.exists():
                init_file_path.touch()
            filename = f"{module_name}_role_mixins.py"
            return role_mixins_folder / filename
        else:
            prefix = copy(self.file_name_prefix)
            if prefix and not prefix.endswith("_"):
                prefix = f"{prefix}_"
            filename = f"{prefix}{module_name}.py"
            return parent_directory / filename


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
        taker_modules: list[ModuleType],
        file_name_prefix: str = "",
    ):
        """
        Initialise the transformer with the class diagram and module context.

        :param context: The codemod context for import tracking.
        :param class_diagram: The class diagram describing all relevant classes.
        :param module: The module being transformed.
        :param taker_modules: All modules that contain role taker classes.
        :param file_name_prefix: Prefix applied to generated file names.
        """
        super().__init__(context)
        self.class_diagram = class_diagram
        self.source_module = module
        self.taker_modules = taker_modules
        self.file_name_prefix = file_name_prefix
        self.role_attributes: dict[WrappedClass, libcst.ClassDef] = {}
        self.role_for: dict[WrappedClass, libcst.ClassDef] = {}
        self.transformed_module: libcst.Module | None = None
        self.original_context = CodemodContext()
        self.current_class: type | None = None
        self._factory = RoleNodeFactory()
        self._resolver = ImportNameResolver(
            source_module=module,
            taker_modules=list(taker_modules),
            class_diagram=class_diagram,
        )
        self._normaliser = TypeNameNormaliser(
            resolver=self._resolver,
            class_diagram=class_diagram,
        )
        self._import_orchestrator = MixinImportOrchestrator(
            mixin_context=context,
            original_context=self.original_context,
            resolver=self._resolver,
            source_module=module,
        )

    @property
    def name_to_module_map(self) -> dict[str, str]:
        """Expose the resolver's name-to-module map for backward compatibility."""
        return self._resolver.name_to_module_map

    def require_original_import(
        self, module: str, obj: str | list[str] | None = None
    ) -> None:
        """
        Record an import that must appear in the transformed original module.

        :param module: The module to import from.
        :param obj: The name or names to import from the module.
        """
        self._import_orchestrator.require_original_import(module, obj)

    def leave_ClassDef(
        self, original_node: libcst.ClassDef, updated_node: libcst.ClassDef
    ) -> libcst.ClassDef | libcst.FlattenSentinel[libcst.BaseCompoundStatement]:
        """
        Transform class definitions by pruning methods, renaming takers, and adjusting roles.

        :param original_node: The original class node before any transformations.
        :param updated_node: The class node after child transformations.
        :return: The transformed class node or a flattened sentinel with multiple nodes.
        """
        wrapped_class = self._find_wrapped_class(updated_node.name.value)
        if wrapped_class is None:
            return updated_node

        result_nodes = [updated_node]
        if wrapped_class.clazz in self.class_diagram.role_takers:
            result_nodes = self._handle_taker_transformation(
                updated_node, wrapped_class
            )
            updated_node = result_nodes[0]

        role_type = RoleType.get_role_type(wrapped_class)
        if role_type != RoleType.NOT_A_ROLE:
            updated_node = self._handle_role_transformation(updated_node, wrapped_class)
            result_nodes[0] = updated_node

        if len(result_nodes) > 1:
            return libcst.FlattenSentinel(result_nodes)
        return result_nodes[0]

    def _find_wrapped_class(self, class_name: str) -> WrappedClass | None:
        """Return the WrappedClass with the given name, or None if not found."""
        for wrapped_class in self.class_diagram.wrapped_classes:
            if wrapped_class.clazz.__name__ == class_name:
                return wrapped_class
        return None

    def _handle_taker_transformation(
        self, node: libcst.ClassDef, wrapped_class: WrappedClass
    ) -> list[libcst.ClassDef]:
        """Apply role-taker transformation, tracking current_class for import resolution."""
        self.current_class = wrapped_class.clazz
        result = self._transform_role_taker(node, wrapped_class)
        self.current_class = None
        return result

    def _handle_role_transformation(
        self, node: libcst.ClassDef, wrapped_class: WrappedClass
    ) -> libcst.ClassDef:
        """Apply role transformation, tracking current_class for import resolution."""
        self.current_class = wrapped_class.clazz
        result = self._transform_role(node, wrapped_class)
        self.current_class = None
        return result

    def leave_ImportFrom(
        self, original_node: libcst.ImportFrom, updated_node: libcst.ImportFrom
    ) -> libcst.ImportFrom:
        """
        Rewrite import statements: resolve relative imports and prefix transformed module names.

        :param original_node: The original import node.
        :param updated_node: The import node after child transformations.
        :return: The rewritten import node.
        """
        updated_node = self._resolve_relative_import(updated_node)
        return self._rewrite_prefixed_module_name(updated_node)

    def _resolve_relative_import(
        self, node: libcst.ImportFrom
    ) -> libcst.ImportFrom:
        """Resolve a relative import to an absolute import path."""
        if len(node.relative) == 0:
            return node
        current_module_parts = self.source_module.__name__.split(".")
        is_package = hasattr(self.source_module, "__path__")
        pkg_parts = current_module_parts if is_package else current_module_parts[:-1]

        levels_up = len(node.relative) - 1
        if levels_up > 0:
            pkg_parts = pkg_parts[:-levels_up]

        base_module = ".".join(pkg_parts)
        module_name = self._get_module_name_str(node.module)

        if module_name:
            absolute_module = f"{base_module}.{module_name}" if base_module else module_name
        else:
            absolute_module = base_module

        return node.with_changes(
            relative=[],
            module=RoleNodeFactory.to_cst_expression(absolute_module) if absolute_module else None,
        )

    def _rewrite_prefixed_module_name(
        self, node: libcst.ImportFrom
    ) -> libcst.ImportFrom:
        """Rewrite the last module segment to include the file name prefix."""
        module_name = self._get_module_name_str(node.module)
        new_module_node = node.module

        if module_name:
            last_part = module_name.split(".")[-1]
            all_target_modules = [self.source_module] + self.taker_modules
            all_target_module_names = {
                m.__name__.split(".")[-1] for m in all_target_modules
            }
            if last_part in all_target_module_names:
                prefix = self.file_name_prefix
                if prefix and not prefix.endswith("_"):
                    prefix = f"{prefix}_"
                new_last_part = f"{prefix}{last_part}"
                new_module_node = self._update_last_module_part(node.module, new_last_part)

        return node.with_changes(module=new_module_node)

    def _get_module_name_str(
        self, node: libcst.BaseExpression | None
    ) -> str | None:
        """Extract the dotted module name string from a CST expression node."""
        if node is None:
            return None
        if isinstance(node, libcst.Name):
            return node.value
        if isinstance(node, libcst.Attribute):
            base = self._get_module_name_str(node.value)
            if base:
                return f"{base}.{node.attr.value}"
        return None

    def _update_last_module_part(
        self, node: libcst.BaseExpression, new_name: str
    ) -> libcst.BaseExpression:
        """Replace the last segment of a dotted module expression with new_name."""
        if isinstance(node, libcst.Name):
            return libcst.Name(new_name)
        if isinstance(node, libcst.Attribute):
            return node.with_changes(attr=libcst.Name(new_name))
        return node

    def leave_Module(
        self, original_node: libcst.Module, updated_node: libcst.Module
    ) -> libcst.Module:
        """
        Capture the transformed original module and produce the mixin module AST.

        :param original_node: The module node before any transformations.
        :param updated_node: The module node after all child transformations.
        :return: The generated mixin module AST.
        """
        self.transformed_module = updated_node
        return self._generate_mixin_module_ast(updated_node)

    def _generate_mixin_module_ast(self, updated_node: libcst.Module) -> libcst.Module:
        """
        Build the complete mixin module AST from the transformed node and collected mixins.

        :param updated_node: The module node after all class transformations.
        :return: A new Module node containing only the mixin classes and their imports.
        """
        all_mixin_classes = list(self.role_attributes.values()) + list(
            self.role_for.values()
        )
        return self._import_orchestrator.build_mixin_module(
            updated_node, all_mixin_classes, self._factory
        )

    def _resolve_name_to_module(self, name: str) -> str | None:
        """
        Look up the source module for the given identifier name.

        :param name: The identifier to resolve.
        :return: The fully-qualified module name, or None if unresolvable.
        """
        return self._resolver.resolve(name, self.current_class)

    def _transform_role_taker(
        self, role_taker_node: libcst.ClassDef, wrapped_class: WrappedClass
    ) -> list[libcst.ClassDef]:
        """Transform a role taker class by adding RoleAttributes as a base if required."""
        self.make_role_for_node(role_taker_node, wrapped_class)

        if self.should_make_role_attributes_for_node(role_taker_node, wrapped_class):
            self.make_role_attributes_node(wrapped_class)
            role_attributes_name = self.get_role_attributes_name(wrapped_class)
            role_taker_class_bases = list(role_taker_node.bases)
            if not any(
                RoleNodeFactory.get_name_from_base_node(base.value) == role_attributes_name
                for base in role_taker_class_bases
            ):
                role_taker_class_bases.insert(
                    0, RoleNodeFactory.make_argument(role_attributes_name)
                )
            role_taker_node = role_taker_node.with_changes(bases=role_taker_class_bases)

            module_name = self.source_module.__name__
            package_name = ".".join(module_name.split(".")[:-1])
            last_part = module_name.split(".")[-1]
            mixin_module_name = f"{package_name}.role_mixins.{last_part}_role_mixins"
            self.require_original_import(mixin_module_name, [role_attributes_name])

        return [role_taker_node]

    def should_make_role_attributes_for_node(
        self, node: libcst.ClassDef, wrapped_class: WrappedClass
    ) -> bool:
        """
        Determine whether a RoleAttributes class should be generated for the given taker.

        :param node: The role taker class node to check.
        :param wrapped_class: The wrapped class of the role taker.
        :return: True if a RoleAttributes class should be generated.
        """
        return not (
            any(RoleNodeFactory._is_role_base(base.value) for base in node.bases)
            or self.bases_of_class_that_are_role_takers(wrapped_class)
        )

    def bases_of_class_that_are_role_takers(
        self, wrapped_class: WrappedClass
    ) -> dict[str, type]:
        """
        Return all direct base classes of the wrapped class that are also role takers.

        :param wrapped_class: Wrapped class of the role taker.
        :return: Dictionary of base class names to base class types for role takers.
        """
        return {
            base.__name__: base
            for base in wrapped_class.clazz.__bases__
            if base in self.class_diagram.role_takers
        }

    def make_role_attributes_node(self, wrapped_class: WrappedClass) -> None:
        """
        Generate and store the RoleAttributes dataclass node for the given role taker.

        :param wrapped_class: The wrapped class for which to generate the RoleAttributes node.
        """
        propagated_fields = self._get_propagated_fields(wrapped_class)
        role_attributes_node = RoleNodeFactory.make_dataclass(
            self.get_role_attributes_name(wrapped_class), body=propagated_fields
        )
        self.role_attributes[wrapped_class] = role_attributes_node

    @classmethod
    def get_role_attributes_name(cls, wrapped_class: WrappedClass) -> str:
        """
        Return the name of the RoleAttributes dataclass for the given taker.

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
        Create a RoleFor<RoleTaker> class for the given role taker class node.
        Roles of this role taker will inherit from this class.

        :param node: The role taker class node to transform.
        :param wrapped_class: The wrapped class of the role taker.
        """
        role_for_name = self.get_role_for_name(wrapped_class.clazz)
        role_for_node = RoleNodeFactory.get_renamed_node(node, role_for_name)
        role_attributes_name = self.get_role_attributes_name(wrapped_class)

        role_for_bases = self.make_role_for_bases(
            role_for_node, wrapped_class, role_attributes_name
        )
        role_for_node = role_for_node.with_changes(bases=role_for_bases)

        all_taker_fields = self._collect_base_taker_field_names(wrapped_class)
        role_for_body = self.make_role_for_properties(wrapped_class, all_taker_fields)
        role_for_body.update(self.make_role_for_methods(wrapped_class))

        flattened_body = [
            method_node
            for method_nodes in role_for_body.values()
            for method_node in method_nodes
        ]
        self.role_for[wrapped_class] = RoleNodeFactory.get_node_with_new_body(
            role_for_node, flattened_body
        )

    def _collect_base_taker_field_names(
        self, wrapped_class: WrappedClass
    ) -> list[str]:
        """Collect all field names from base taker classes."""
        all_taker_fields = []
        for base_name, taker_type in self.bases_of_class_that_are_role_takers(
            wrapped_class
        ).items():
            wrapped_taker = self.class_diagram.get_wrapped_class(taker_type)
            all_taker_fields.extend([f.name for f in wrapped_taker.fields])
        return all_taker_fields

    def make_role_for_methods(
        self, wrapped_class: WrappedClass
    ) -> dict[str, list[libcst.FunctionDef]]:
        """
        Add delegation methods to the RoleFor class for each method of the role taker.

        :param wrapped_class: Wrapped class of the role taker.
        :return: Dictionary mapping method names to their corresponding FunctionDef nodes.
        """
        # Identify base takers to avoid redundant delegation
        base_takers = []
        for base in wrapped_class.clazz.__mro__[1:]:
            if base in self.class_diagram.role_takers:
                base_takers.append(base)
        if issubclass(wrapped_class.clazz, Role):
            base_takers.append(wrapped_class.clazz.get_role_taker_type())

        role_for_body = {}
        for method_name, method_object in inspect.getmembers(
            wrapped_class.clazz, predicate=inspect.isfunction
        ):
            if method_name in _ALWAYS_EXCLUDED_METHODS:
                continue
            if _is_from_role_class(method_name, wrapped_class.clazz):
                continue

            # Skip if already delegated in a base taker mixin
            if any(method_name in dir(base_taker) for base_taker in base_takers):
                continue

            method_node = self.make_method_node(method_name, method_object)
            if method_node is not None:
                role_for_body[method_name] = [method_node]
        return role_for_body

    def make_method_node(
        self, name: str, method: Callable
    ) -> libcst.FunctionDef | None:
        """
        Create a delegation FunctionDef node for a method of the role taker.

        :param name: The name of the method.
        :param method: The method to create the delegation node for.
        :return: A libcst FunctionDef node, or None if the source cannot be retrieved.
        """
        method_source = self._parse_method_source(method)
        if method_source is None:
            return None

        method_node = libcst.parse_module(dedent(method_source)).body[0]
        if not isinstance(method_node, libcst.FunctionDef):
            raise RoleTransformerError(
                f"Expected FunctionDef, got {type(method_node).__name__}"
            )

        self._resolve_signature_types(method)
        method_node = self._handle_decorators(method_node, method)

        return self._generate_delegation_body(method_node, name, method)

    def _parse_method_source(self, method: Callable) -> str | None:
        """Retrieve the source code of a method, returning None if unavailable."""
        try:
            return inspect.getsource(method)
        except OSError:
            return None

    def _resolve_signature_types(self, method: Callable) -> None:
        """
        Register name-to-module mappings for all types appearing in a method's signature.

        :param method: The method whose type annotations should be registered.
        """
        try:
            self._register_type_hints_from_method(method)
        except Exception:
            self._register_signature_annotations(method)
        self._resolver.register_from_callable_globals(method)

    def _register_type_hints_from_method(self, method: Callable) -> None:
        """Register types via get_type_hints (preferred path)."""
        type_hints = get_type_hints_of_object(method)
        for type_obj in type_hints.values():
            self._get_consistent_type_name(type_obj)

    def _register_signature_annotations(self, method: Callable) -> None:
        """Register types via inspect.signature (fallback path)."""
        parameters = inspect.signature(method).parameters
        for param in parameters.values():
            if param.annotation is not inspect.Parameter.empty:
                self._get_consistent_type_name(param.annotation)
        return_annotation = inspect.signature(method).return_annotation
        if return_annotation is not inspect.Signature.empty:
            self._get_consistent_type_name(return_annotation)

    def _handle_decorators(
        self, method_node: libcst.FunctionDef, method: Callable
    ) -> libcst.FunctionDef:
        """
        Register the source module of each decorator used on the method.

        :param method_node: The parsed FunctionDef node containing decorator nodes.
        :param method: The live method object, used for runtime name resolution.
        :return: The unchanged method_node (side effect: updates name_to_module_map).
        """
        for decorator in method_node.decorators:
            decorator_node = decorator.decorator
            decorator_name = self._get_decorator_name(decorator_node)
            if decorator_name:
                try:
                    decorator_object = resolve_name_in_hierarchy(decorator_name, method)
                    if hasattr(decorator_object, "__module__"):
                        self._resolver.name_to_module_map[decorator_name] = decorator_object.__module__
                except Exception:
                    pass
        return method_node

    def _get_decorator_name(self, decorator_node: libcst.BaseExpression) -> str | None:
        """Extract the simple name from a decorator expression node."""
        if isinstance(decorator_node, libcst.Name):
            return decorator_node.value
        if isinstance(decorator_node, libcst.Call) and isinstance(decorator_node.func, libcst.Name):
            return decorator_node.func.value
        return None

    def _generate_delegation_body(
        self, method_node: libcst.FunctionDef, name: str, method: Callable
    ) -> libcst.FunctionDef:
        """
        Replace the method body with a delegation call to ``self.role_taker.<name>``.

        :param method_node: The original parsed method node.
        :param name: The method name to delegate to on the role taker.
        :param method: The live method object used to obtain parameter names.
        :return: The method node with a delegation body.
        """
        parameters = inspect.signature(method).parameters
        call_params = [p for p in parameters.keys() if p != "self"]
        return method_node.with_changes(
            body=libcst.IndentedBlock(
                [
                    libcst.parse_statement(
                        f"return self.role_taker.{name}({', '.join(call_params)})"
                    )
                ]
            )
        )

    def make_role_for_bases(
        self,
        node: libcst.ClassDef,
        wrapped_class: WrappedClass,
        role_attributes_name: str,
    ) -> list[libcst.Arg]:
        """
        Generate the base class arguments for a RoleFor class.

        :param node: The original taker class node.
        :param wrapped_class: The taker wrapped class.
        :param role_attributes_name: Name for the role attributes dataclass.
        :return: List of Arg nodes representing the base classes.
        """
        role_for_bases = []
        bases_that_are_takers = self.bases_of_class_that_are_role_takers(wrapped_class)
        for base in node.bases:
            base_name = RoleNodeFactory.get_name_from_base_node(base.value)
            if base_name in bases_that_are_takers:
                taker_role_for = RoleNodeFactory.make_argument(
                    self.get_role_for_name(bases_that_are_takers[base_name])
                )
                role_for_bases.append(taker_role_for)
            elif RoleNodeFactory._is_role_base(base.value) and issubclass(
                wrapped_class.clazz, Role
            ):
                taker_type = wrapped_class.clazz.get_role_taker_type()
                taker_role_for = RoleNodeFactory.make_argument(self.get_role_for_name(taker_type))
                role_for_bases.append(taker_role_for)

        if self.should_make_role_attributes_for_node(node, wrapped_class):
            role_for_bases.insert(0, RoleNodeFactory.make_argument(role_attributes_name))

        role_for_bases.append(RoleNodeFactory.make_argument("ABC"))

        return role_for_bases

    def make_role_for_properties(
        self, taker_wrapped_class: WrappedClass, all_taker_fields: list[str]
    ) -> dict[str, list[libcst.FunctionDef]]:
        """
        Generate property getter and setter methods for the RoleFor class fields.

        :param taker_wrapped_class: Wrapped class of the role taker.
        :param all_taker_fields: List of field names already covered by base taker mixins.
        :return: Dictionary mapping field names to lists of getter/setter FunctionDef nodes.
        """
        taker_type_name = self._normaliser.get_type_name(taker_wrapped_class.clazz)
        result: dict[str, list[libcst.FunctionDef]] = {
            "role_taker": [
                RoleNodeFactory.make_property_getter_node("role_taker", taker_type_name, "...")
            ]
        }
        result.update(self._make_field_properties(taker_wrapped_class, all_taker_fields, taker_type_name))
        result.update(self._make_data_descriptor_properties(taker_wrapped_class))
        return result

    def _make_field_properties(
        self,
        taker_wrapped_class: WrappedClass,
        all_taker_fields: list[str],
        taker_type_name: str,
    ) -> dict[str, list[libcst.FunctionDef]]:
        """Build getter/setter properties for each initialised field of the taker."""
        field_properties: dict[str, list[libcst.FunctionDef]] = {}
        for field_ in taker_wrapped_class.fields:
            if field_.name in all_taker_fields:
                continue
            if field_.field.kw_only or field_.field.init:
                field_type_name = self._get_consistent_type_name(field_.field.type)
                field_properties[field_.name] = RoleNodeFactory.make_property_getter_and_setter_nodes(
                    field_.name,
                    field_type_name,
                    f"self.role_taker.{field_.name}",
                    f"self.role_taker.{field_.name} = value",
                )
        return field_properties

    def _make_data_descriptor_properties(
        self, taker_wrapped_class: WrappedClass
    ) -> dict[str, list[libcst.FunctionDef]]:
        """Build getter/setter properties for each data descriptor on the taker class."""
        descriptor_properties: dict[str, list[libcst.FunctionDef]] = {}
        for property_name, property_value in inspect.getmembers(
            taker_wrapped_class.clazz, inspect.isdatadescriptor
        ):
            if not isinstance(property_value, property):
                continue
            if _is_from_role_class(property_name, taker_wrapped_class.clazz):
                continue
            return_annotation = (
                property_value.fget.__annotations__["return"]
                if "return" in property_value.fget.__annotations__
                else None
            )
            if return_annotation:
                return_annotation = self._get_consistent_type_name(return_annotation)
            if property_value.fset is not None:
                descriptor_properties[property_name] = RoleNodeFactory.make_property_getter_and_setter_nodes(
                    property_name,
                    return_annotation,
                    f"self.role_taker.{property_name}",
                    f"self.role_taker.{property_name} = value",
                )
            else:
                descriptor_properties[property_name] = [
                    RoleNodeFactory.make_property_getter_node(
                        property_name,
                        return_annotation,
                        f"self.role_taker.{property_name}",
                    )
                ]
        return descriptor_properties

    def _get_consistent_type_name(self, type_obj: Any) -> str:
        """
        Return a normalised string representation of a type for use in generated code.

        :param type_obj: The type object to normalise.
        :return: A string type name suitable for inclusion in generated source code.
        """
        return self._normaliser.normalise(type_obj)

    def _transform_role(
        self, node: libcst.ClassDef, wrapped_class: WrappedClass
    ) -> libcst.ClassDef:
        """
        Adjust a primary role class by replacing Role bases with RoleFor bases.

        :param node: The original class node.
        :param wrapped_class: The wrapped class information.
        :return: The updated class node with corrected bases.
        """
        role_type = RoleType.get_role_type(wrapped_class)
        logger.debug(
            "Transforming role %s, type: %s", wrapped_class.clazz.__name__, role_type
        )
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
        logger.debug("  role_bases keys: %s", list(role_bases.keys()))
        for base in node.bases:
            new_bases.append(base)
            base_name = RoleNodeFactory.get_name_from_base_node(base.value)
            logger.debug("  Checking base %s", base_name)

            # Check if this base is a Role class in our diagram
            is_role_base = False
            if base_name == "Role":
                is_role_base = True
            else:
                for wrapped in self.class_diagram.wrapped_classes:
                    if wrapped.clazz.__name__ == base_name and issubclass(
                        wrapped.clazz, Role
                    ):
                        is_role_base = True
                        break

            if is_role_base:
                role_for_name = self.get_role_for_name(taker_type)
                if not any(
                    RoleNodeFactory.get_name_from_base_node(base.value) == role_for_name
                    for base in node.bases
                ):
                    logger.debug("  Adding %s", role_for_name)
                    new_bases.append(RoleNodeFactory.make_argument(role_for_name))

                taker_module = sys.modules[taker_type.__module__]
                module_name = taker_module.__name__
                package_name = ".".join(module_name.split(".")[:-1])
                last_part = module_name.split(".")[-1]
                mixin_module_name = f"{package_name}.role_mixins.{last_part}_role_mixins"
                self.require_original_import(mixin_module_name, [role_for_name])

        return node.with_changes(bases=new_bases)

    @classmethod
    def get_role_for_name(cls, taker_class: type) -> str:
        """Return the name of the RoleFor class for the given taker class."""
        return f"RoleFor{taker_class.__name__}"

    def _get_propagated_fields(
        self, wrapped_class: WrappedClass
    ) -> list[libcst.BaseStatement]:
        """
        Collect the field nodes to propagate from roles to the root role taker's RoleAttributes.

        :param wrapped_class: The wrapped class for the role taker.
        :return: A list of libcst nodes representing the fields to be propagated.
        """
        if not self._is_root_taker(wrapped_class):
            return []
        root_taker = wrapped_class.clazz
        candidate_fields = self._collect_candidate_role_fields(root_taker)
        seen_field_names = {f.name for f in wrapped_class.fields}
        return self._deduplicate_fields(candidate_fields, seen_field_names)

    def _is_root_taker(self, wrapped_class: WrappedClass) -> bool:
        """Return True if the wrapped class is the root (non-role) role taker."""
        root_taker = wrapped_class.clazz
        if issubclass(root_taker, Role):
            root_taker = root_taker.get_root_role_taker_type()
        return wrapped_class.clazz == root_taker

    def _collect_candidate_role_fields(
        self, root_taker: type
    ) -> list[WrappedField]:
        """Collect all role fields for the root taker, excluding the taker attribute field."""
        roles = self._get_all_roles_for_taker(root_taker)
        candidate_fields: list[WrappedField] = []
        for role_wrapped in roles:
            taker_attr_name = role_wrapped.clazz.role_taker_attribute_name()
            candidate_fields.extend(
                role_field
                for role_field in role_wrapped.fields
                if role_field.name != taker_attr_name
            )
        return candidate_fields

    def _deduplicate_fields(
        self,
        candidate_fields: list[WrappedField],
        seen_field_names: set[str],
    ) -> list[libcst.BaseStatement]:
        """Return field nodes for candidate fields not already in seen_field_names."""
        fields_to_propagate: list[libcst.BaseStatement] = []
        for role_field in candidate_fields:
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
        kw_only: bool | None = None,
    ) -> libcst.SimpleStatementLine:
        """Create a libcst annotated-assignment node for a dataclass field."""
        field_copy = self._apply_field_init_flags(wrapped_field, init, kw_only)
        value_cst = self._parse_field_default_value(field_copy, wrapped_field)
        type_str = wrapped_field.type_name.replace("typing.", "").replace("typing_extensions.", "")
        return libcst.SimpleStatementLine(
            body=[
                libcst.AnnAssign(
                    target=libcst.Name(wrapped_field.name),
                    annotation=libcst.Annotation(
                        annotation=RoleNodeFactory.to_cst_expression(type_str)
                    ),
                    value=value_cst,
                )
            ]
        )

    def _apply_field_init_flags(
        self,
        wrapped_field: WrappedField,
        init: bool,
        kw_only: bool | None,
    ):
        """Return a copy of the field with init and kw_only flags applied."""
        field_copy = copy(wrapped_field.field)
        if not init:
            field_copy.init = False
            field_copy.default = dataclasses.MISSING
            field_copy.default_factory = dataclasses.MISSING
            field_copy.kw_only = False
        else:
            field_copy.kw_only = field_copy.kw_only or (
                not wrapped_field.is_required and field_copy.init
            )
        if kw_only is not None:
            field_copy.kw_only = kw_only
        return field_copy

    def _parse_field_default_value(
        self, field_copy, wrapped_field: WrappedField
    ) -> libcst.BaseExpression | None:
        """Parse the default value expression for a field, returning None if absent."""
        field_representation = FieldRepresentation(field_copy)
        representation_string = field_representation.representation.strip()
        if representation_string.startswith("="):
            val_str = representation_string[1:].strip()
            try:
                return libcst.parse_expression(val_str)
            except Exception:
                return libcst.Name("None")
        return None

    def require_import(self, module: str, names: str | list[str]):
        """
        Record an import that must appear in the generated mixin module.

        :param module: The module to import from.
        :param names: The name or list of names to import.
        """
        self._import_orchestrator.require_import(module, names)

    def _get_all_roles_for_taker(self, taker_type: type) -> list[WrappedClass]:
        """
        Recursively find all role WrappedClasses associated with a taker type.

        :param taker_type: The role taker class to search from.
        :return: All role wrapped classes for this taker, including inherited ones.
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
        return hash((self.__class__, self.source_module))
