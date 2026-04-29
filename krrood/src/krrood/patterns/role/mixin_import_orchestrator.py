"""
Orchestrator that collects and emits import statements for generated mixin modules.
"""

from __future__ import annotations

import dataclasses
from types import ModuleType
from typing import Protocol, runtime_checkable

import libcst
from libcst.codemod import CodemodContext
from libcst.codemod.visitors import AddImportsVisitor

from krrood.patterns.role.import_name_resolver import ImportNameResolver
from krrood.patterns.role.role_node_factory import (
    RoleNodeFactory,
    NameCollector,
    RuntimeNameCollector,
)


@runtime_checkable
class ImportContext(Protocol):
    """
    Minimal interface for recording needed imports.
    """

    def add_needed_import(self, module: str, name: str | None = None) -> None:
        """
        Record that an import of ``name`` from ``module`` is needed.

        :param module: The module to import from.
        :param name: The name to import, or None for a bare module import.
        """
        ...


@dataclasses.dataclass
class MixinImportOrchestrator:
    """
    Orchestrates the collection and emission of import statements for generated mixin modules.
    """

    mixin_context: CodemodContext
    original_context: CodemodContext
    resolver: ImportNameResolver
    source_module: ModuleType

    _TYPING_MODULES: frozenset[str] = dataclasses.field(
        default_factory=lambda: frozenset({"typing", "typing_extensions"}), init=False
    )
    _NON_IMPORTABLE_MODULES: frozenset[str] = dataclasses.field(
        default_factory=lambda: frozenset({"typing", "typing_extensions", "builtins"}),
        init=False,
    )

    def require_import(self, module: str, names: str | list[str]) -> None:
        """
        Record an import that must appear in the generated mixin module.

        :param module: The module to import from.
        :param names: The name or list of names to import.
        """
        if module in ["builtins", self.source_module.__name__]:
            return
        if isinstance(names, str):
            names = [names]
        for name in names:
            AddImportsVisitor.add_needed_import(
                self.mixin_context,
                module=module,
                obj=name,
            )

    def require_original_import(
        self, module: str, obj: str | list[str] | None = None
    ) -> None:
        """
        Record an import that must appear in the transformed original module.

        :param module: The module to import from.
        :param obj: The name or names to import from the module.
        """
        if module in ["builtins", self.source_module.__name__]:
            return
        if obj is None:
            AddImportsVisitor.add_needed_import(self.original_context, module)
        elif isinstance(obj, str):
            AddImportsVisitor.add_needed_import(self.original_context, module, obj)
        else:
            for o in obj:
                AddImportsVisitor.add_needed_import(self.original_context, module, o)

    def build_mixin_module(
        self,
        updated_module_node: libcst.Module,
        mixin_classes: list[libcst.ClassDef],
        factory: RoleNodeFactory,
    ) -> libcst.Module:
        """
        Build the complete mixin module AST with all imports.

        :param updated_module_node: The transformed source module node (used for header/footer).
        :param mixin_classes: The generated mixin class nodes to include.
        :param factory: The node factory for creating CST nodes.
        :return: A complete Module node ready to emit as source code.
        """
        used_names = self._collect_used_names_in_mixins(mixin_classes)
        self._add_required_mixin_imports(used_names)
        runtime_names = self._collect_runtime_names(mixin_classes)

        # Names that should be imported at top level (those used in decorators)
        top_level_names = runtime_names

        # Names for the TYPE_CHECKING block
        type_checking_names = used_names - top_level_names

        self._add_typing_imports(used_names)
        self._add_runtime_imports(top_level_names, mixin_classes)

        mixin_body = [self._create_future_annotations_import()]

        type_checking_block = self._create_type_checking_block(
            type_checking_names, mixin_classes, factory
        )
        if type_checking_block:
            mixin_body.append(type_checking_block)

        mixin_body.extend(mixin_classes)

        return libcst.Module(
            body=mixin_body,
            header=updated_module_node.header,
            footer=updated_module_node.footer,
        )

    def _collect_used_names_in_mixins(
        self, mixin_classes: list[libcst.ClassDef]
    ) -> set[str]:
        """Return all identifier names referenced inside the given mixin classes."""
        used_names: set[str] = set()
        for class_def in mixin_classes:
            collector = NameCollector()
            class_def.visit(collector)
            used_names.update(collector.names)
        return used_names

    def _collect_runtime_names(self, mixin_classes: list[libcst.ClassDef]) -> set[str]:
        """Collect all names used inside decorator expressions in the given mixin classes."""
        collector = RuntimeNameCollector()
        for class_def in mixin_classes:
            class_def.visit(collector)
        return collector.names

    def _add_required_mixin_imports(self, used_names: set[str] | None = None) -> None:
        """Record the standard imports that every generated mixin module needs."""
        dataclass_names = ["dataclass"]
        if used_names and "field" in used_names:
            dataclass_names.append("field")
        self.require_import("dataclasses", dataclass_names)
        self.require_import("abc", ["ABC", "abstractmethod"])
        self.require_import("typing_extensions", ["TYPE_CHECKING"])

    def _add_typing_imports(self, used_names: set[str]) -> None:
        """Add top-level imports for names whose source module is typing or typing_extensions."""
        for name in used_names:
            module = self.resolver.resolve(name)
            if module in self._TYPING_MODULES:
                self.require_import(module, name)

    def _add_runtime_imports(
        self, names: set[str], mixin_classes: list[libcst.ClassDef]
    ) -> None:
        """Record top-level imports for names that must be available at runtime."""
        common_names = {
            "dataclass",
            "field",
            "ABC",
            "abstractmethod",
            "TYPE_CHECKING",
        }
        mixin_defined_names = {cd.name.value for cd in mixin_classes}

        for name in names:
            if name in common_names or name in mixin_defined_names:
                continue
            module_name = self.resolver.resolve(name)
            if module_name:
                self.require_import(module_name, name)

    def _create_future_annotations_import(self) -> libcst.SimpleStatementLine:
        """Create a ``from __future__ import annotations`` statement node."""
        return libcst.SimpleStatementLine(
            body=[
                libcst.ImportFrom(
                    module=libcst.Name("__future__"),
                    names=[libcst.ImportAlias(name=libcst.Name("annotations"))],
                )
            ]
        )

    def _build_mixin_import_map(
        self, used_names: set[str], mixin_classes: list[libcst.ClassDef]
    ) -> dict[str, set[str]]:
        """Build a mapping of module name to the set of names to import for the mixin module."""
        excluded_names = {"dataclass", "field", "ABC", "abstractmethod", "TYPE_CHECKING"}
        mixin_defined_names = {cd.name.value for cd in mixin_classes}

        import_map: dict[str, set[str]] = {}
        for name in used_names:
            if name in excluded_names or name in mixin_defined_names:
                continue
            module_name = self.resolver.resolve(name)
            if module_name and module_name not in self._NON_IMPORTABLE_MODULES:
                import_map.setdefault(module_name, set()).add(name)
        return import_map

    def _create_type_checking_block(
        self,
        used_names: set[str],
        mixin_classes: list[libcst.ClassDef],
        factory: RoleNodeFactory,
    ) -> libcst.If | None:
        """Build an ``if TYPE_CHECKING:`` block containing all non-runtime imports."""
        import_map = self._build_mixin_import_map(used_names, mixin_classes)
        if not import_map:
            return None

        type_checking_body = []
        for module_name, names in sorted(import_map.items()):
            type_checking_body.append(
                self._create_import_from_node(module_name, names, factory)
            )

        return libcst.If(
            test=libcst.Name("TYPE_CHECKING"),
            body=libcst.IndentedBlock(body=type_checking_body),
        )

    def _create_import_from_node(
        self, module_name: str, names: set[str], factory: RoleNodeFactory
    ) -> libcst.SimpleStatementLine:
        """Build a ``from <module> import <names>`` CST node."""
        return libcst.SimpleStatementLine(
            body=[
                libcst.ImportFrom(
                    module=factory.to_cst_expression(module_name) if module_name else None,
                    names=[
                        libcst.ImportAlias(name=libcst.Name(n)) for n in sorted(names)
                    ],
                    relative=[],
                )
            ]
        )
