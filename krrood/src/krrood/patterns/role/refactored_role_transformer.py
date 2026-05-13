"""
Refactored role transformer: wires analysis, planning, and execution layers.

This module provides a :class:`RefactoredRoleTransformer` that separates
the concerns of transformation into three distinct phases:

1. **Analyze** — walk the class diagram and produce a
   :class:`~krrood.patterns.code_generation.specs.ModuleTransformationSpec`.
2. **Plan** — convert the spec into an
   :class:`~krrood.patterns.code_generation.actions.ActionPlan`.
3. **Execute** — apply the plan to the source module and write the result.

Each phase is independent and replaceable.  The analysis and planning layers
are generic and reusable for other code-generation tasks (RDR, ORMatic).
"""

from __future__ import annotations

import dataclasses
import enum
import sys
from dataclasses import dataclass, field
from pathlib import Path
from types import ModuleType

import libcst
from typing_extensions import Type

from krrood.class_diagrams import AllFieldsIntrospector, ClassDiagram
from krrood.class_diagrams.utils import (
    classes_of_module,
    same_package,
)
from krrood.patterns.code_generation import (
    GeneratedCodeFileWriter,
    ImportNameResolver,
    LibCSTNodeFactory,
    TypeNormaliser,
)
from krrood.patterns.code_generation.actions import (
    ActionExecutor,
    ActionPlan,
    CreateClass,
)
from krrood.patterns.code_generation.analysis import (
    AnalysisContext,
    DelegationAnalyzer,
    RolePatternAnalyzer,
)
from krrood.patterns.code_generation.exceptions import CodeGenerationError
from krrood.patterns.code_generation.planners import (
    PlanningContext,
    RoleTransformationPlanner,
)
from krrood.patterns.code_generation.specs import (
    ClassTransformationSpec,
    DelegationSpec,
    ModuleTransformationSpec,
    RoleClassTransformationSpec,
)
from krrood.patterns.property_delegator import PropertyDelegator
from krrood.patterns.subclass_safe_generic import SubClassSafeGeneric
from krrood.patterns.role.role import HasRoles, Role

DELEGATEE_ATTR = "delegatee"
ROLE_MIXINS_FOLDER = "role_mixins"
ROLE_MIXINS_SUFFIX = "_role_mixins"
_ALWAYS_EXCLUDED_METHODS: frozenset[str] = frozenset(
    {"__init__", "__post_init__", "__new__"}
)


class TransformationMode(str, enum.Enum):
    """Enumeration of transformation mode identifiers used as file-name prefixes."""

    GROUND_TRUTH = "_ground_truth_"
    TRANSFORMED = "transformed_"


def _normalize_type(t: type) -> type:
    from typing_extensions import get_origin

    origin = get_origin(t)
    return origin if origin is not None else t


def _is_from_property_delegator_class(name: str, clazz: type) -> bool:
    """Return True if *name* is inherited from the PropertyDelegator hierarchy
    without being overridden by *clazz*.

    Members from PropertyDelegator or SubClassSafeGeneric should not be
    delegated — they are part of the delegation infrastructure itself.
    """
    for klass in clazz.__mro__:
        if name in vars(klass):
            return issubclass(klass, PropertyDelegator) or klass is SubClassSafeGeneric
    return False


# ── module-level helpers (copied from role_transformer.py to avoid circular imports)


def _sort_modules_by_dependency(
    modules: list[ModuleType], class_diagram: ClassDiagram
) -> list[ModuleType]:
    module_set = set(modules)
    deps: dict[ModuleType, set[ModuleType]] = {m: set() for m in modules}
    all_types = {wc.clazz for wc in class_diagram.wrapped_classes}
    for clazz in all_types:
        concrete = _normalize_type(clazz)
        clazz_module = sys.modules.get(concrete.__module__)
        if clazz_module not in module_set:
            continue
        for ancestor in concrete.__mro__[1:]:
            if ancestor is object:
                continue
            ancestor_module = sys.modules.get(ancestor.__module__)
            if (
                ancestor_module is not None
                and ancestor_module in module_set
                and ancestor_module is not clazz_module
            ):
                deps[clazz_module].add(ancestor_module)
    result: list[ModuleType] = []
    visited: set[ModuleType] = set()

    def visit(m: ModuleType) -> None:
        if m in visited:
            return
        visited.add(m)
        for dep in deps.get(m, set()):
            visit(dep)
        result.append(m)

    for m in modules:
        visit(m)
    return result


def _build_role_diagram(
    module: ModuleType,
    taker_modules: list[ModuleType],
) -> tuple[ClassDiagram, list[ModuleType], set[type]]:
    classes = classes_of_module(module)
    role_classes = [clazz for clazz in classes if issubclass(clazz, Role)]
    pd_only_classes = [
        clazz
        for clazz in classes
        if issubclass(clazz, PropertyDelegator) and not issubclass(clazz, Role)
    ]
    updated_taker_modules = list(taker_modules)

    def add_delegatee_class(delegatee_class: Type):
        concrete = _normalize_type(delegatee_class)
        if concrete not in classes:
            classes.append(concrete)
        delegatee_module = sys.modules[concrete.__module__]
        if delegatee_module not in updated_taker_modules:
            updated_taker_modules.append(delegatee_module)

    for clazz in role_classes:
        role_taker_type = clazz.get_role_taker_type()
        if role_taker_type not in classes:
            add_delegatee_class(role_taker_type)

    pd_only_delegatees: set[type] = set()
    for clazz in pd_only_classes:
        delegatee_type = clazz.get_delegatee_type()
        if delegatee_type not in classes:
            add_delegatee_class(delegatee_type)
        pd_only_delegatees.add(delegatee_type)

    delegatee_classes = [
        c for c in classes if c not in role_classes and c not in pd_only_classes
    ]
    for delegatee in list(delegatee_classes):
        concrete = _normalize_type(delegatee)
        for ancestor in concrete.__mro__:
            if ancestor is object or ancestor is concrete:
                continue
            if not same_package(ancestor.__module__, concrete.__module__):
                continue
            if ancestor not in classes:
                add_delegatee_class(ancestor)

    return (
        ClassDiagram(classes, introspector=AllFieldsIntrospector()),
        updated_taker_modules,
        pd_only_delegatees,
    )


# ── RefactoredRoleTransformer ────────────────────────────────────────


@dataclass
class RefactoredRoleTransformer:
    """Transform role-pattern modules using the separated analysis → plan → execute pipeline.

    This is the refactored equivalent of :class:`RoleTransformer`.  It
    delegates analysis to :class:`DelegationAnalyzer` and
    :class:`RolePatternAnalyzer`, planning to :class:`RoleTransformationPlanner`,
    and execution to :class:`ActionExecutor`.

    Usage::

        transformer = RefactoredRoleTransformer(module=my_module)
        sources = transformer.transform(write=True)
    """

    module: ModuleType
    taker_modules: list[ModuleType] = field(default_factory=list)
    class_diagram: ClassDiagram = field(init=False)
    pd_only_delegatees: set[type] = field(init=False, default_factory=set)
    path: Path | None = None
    file_name_prefix: str = ""

    def __post_init__(self):
        if self.path is None:
            self.path = self.get_generated_file_path(self.module)
        self._refresh_diagram()

    def _refresh_diagram(self) -> None:
        self.class_diagram, self.taker_modules, self.pd_only_delegatees = (
            _build_role_diagram(self.module, self.taker_modules)
        )

    # ── public API ─────────────────────────────────────────────────

    def transform(self, write: bool = False) -> dict[ModuleType, tuple[str, str]]:
        """Transform the module and its taker modules.

        :param write: When True, writes generated files to disk.
        :return: Mapping of module → (transformed_source, mixin_source).
        """
        import importlib

        all_modules = list(self.taker_modules)
        if self.module not in all_modules:
            all_modules.append(self.module)

        all_modules = _sort_modules_by_dependency(all_modules, self.class_diagram)
        for module in all_modules:
            importlib.reload(module)
        self._refresh_diagram()

        all_modules = _sort_modules_by_dependency(all_modules, self.class_diagram)

        all_modules_sources: dict[ModuleType, tuple[str, str]] = {}
        for module in all_modules:
            with open(self.get_module_file_path(module), "r") as f:
                source = f.read()

            tree = libcst.parse_module(source)
            transformed, mixin = self._transform_one_module(module, tree)
            all_modules_sources[module] = (transformed, mixin)

        if write:
            writer = GeneratedCodeFileWriter()
            writer.write(all_modules_sources, self.get_generated_file_path)

        return all_modules_sources

    def _transform_one_module(
        self, module: ModuleType, tree: libcst.Module
    ) -> tuple[str, str]:
        """Run the full analysis → plan → execute pipeline for a single module.

        :returns: ``(transformed_original_code, mixin_code)``.
        """
        source = tree.code

        # Build contexts
        resolver = ImportNameResolver(
            source_module=module,
            companion_modules=list(self.taker_modules),
            class_diagram=self.class_diagram,
        )
        normaliser = TypeNormaliser(
            resolver=resolver, class_diagram=self.class_diagram
        )
        all_delegatees = self._compute_all_delegatees()
        # Only cross-module bases are "already covered."  Same-module bases
        # need their own DelegatorFor generated by THIS module's planner.
        cross_module_covered = {
            d
            for d in all_delegatees
            if d.__module__ != module.__name__
        }
        analysis_ctx = AnalysisContext(
            class_diagram=self.class_diagram,
            resolver=resolver,
            normaliser=normaliser,
            already_covered_bases=cross_module_covered,
            pd_only_delegatees=self.pd_only_delegatees,
            module_name=module.__name__,
            source_module=module,
        )

        # Phase 1 — Analyze every class in this module
        class_specs: list[ClassTransformationSpec] = []
        for wrapped_class in self.class_diagram.wrapped_classes:
            if wrapped_class.clazz.__module__ != module.__name__:
                continue
            class_specs.append(self._analyze_class(wrapped_class, analysis_ctx))

        if not class_specs:
            return source, ""

        # Phase 2 — Build module spec
        module_spec = ModuleTransformationSpec(
            module_name=module.__name__,
            source_module=module,
            classes=class_specs,
        )

        # Phase 3 — Plan
        factory = LibCSTNodeFactory()
        planning_ctx = PlanningContext(
            factory=factory,
            normaliser=normaliser,
            resolver=resolver,
            delegatee_attr=DELEGATEE_ATTR,
            file_name_prefix=self.file_name_prefix,
            module=module,
        )
        planner = RoleTransformationPlanner(delegatee_attr=DELEGATEE_ATTR)
        plan = planner.plan(module_spec, planning_ctx)

        # Phase 4 — Execute on the original source tree
        executor = ActionExecutor()
        result = executor.execute(plan, tree)
        if not result.success:
            raise result.error or CodeGenerationError(
                fix_suggestion="Check the module source and class diagram for consistency."
            )

        # Split: the result module contains both transformed original classes
        # and newly generated mixin classes.  Separate them.
        transformed_code, mixin_code = self._split_result(
            result.module, module, source, resolver
        )

        return transformed_code, mixin_code

    def _analyze_class(
        self, wrapped_class, ctx: AnalysisContext
    ) -> RoleClassTransformationSpec:
        """Run role-pattern and delegation analyzers on one wrapped class."""
        role_analyzer = RolePatternAnalyzer()
        role_spec = role_analyzer.analyze(wrapped_class, ctx)

        delegation_spec: DelegationSpec | None = None
        if role_spec.is_role_taker or role_spec.role_type != "NOT_A_ROLE":
            delegation_analyzer = DelegationAnalyzer(
                delegatee_attribute_name=DELEGATEE_ATTR,
                excluded_method_names=_ALWAYS_EXCLUDED_METHODS,
                excluded_member_predicate=_is_from_property_delegator_class,
                is_excluded_defining_class=lambda klass: (
                    issubclass(klass, PropertyDelegator)
                    or klass is SubClassSafeGeneric
                ),
            )
            delegation_spec = delegation_analyzer.analyze(wrapped_class, ctx)

        return dataclasses.replace(role_spec, delegation=delegation_spec)

    @staticmethod
    def _split_result(
        result_module: libcst.Module | None,
        module: ModuleType,
        original_source: str,
        resolver: ImportNameResolver,
    ) -> tuple[str, str]:
        """Split the result module into transformed original and generated mixin.

        Original classes stay in the transformed module.  New classes
        (DelegatorFor*, RoleFor*) go to the mixin, whose imports are
        generated automatically via :class:`AddImportsVisitor`.
        """
        if result_module is None:
            return original_source, ""

        original_tree = libcst.parse_module(original_source)
        original_class_names: set[str] = {
            stmt.name.value
            for stmt in original_tree.body
            if isinstance(stmt, libcst.ClassDef)
        }

        transformed_body: list[libcst.BaseStatement] = []
        mixin_body: list[libcst.BaseStatement] = []
        for stmt in result_module.body:
            if isinstance(stmt, libcst.ClassDef):
                if stmt.name.value in original_class_names:
                    transformed_body.append(stmt)
                else:
                    mixin_body.append(stmt)
            else:
                transformed_body.append(stmt)

        transformed_code = result_module.with_changes(
            body=transformed_body
        ).code

        if not mixin_body:
            return transformed_code, ""

        # Build mixin module with auto-generated imports
        mixin_code = RefactoredRoleTransformer._build_mixin_module(
            mixin_body, resolver
        )

        return transformed_code, mixin_code

    @staticmethod
    def _build_mixin_module(
        mixin_classes: list[libcst.BaseStatement],
        resolver: ImportNameResolver,
    ) -> str:
        """Build a mixin module with imports resolved via :class:`AddImportsVisitor`.

        Uses :class:`NameCollector` to discover names used in the generated
        classes, resolves each name to its source module, and lets
        :class:`AddImportsVisitor` place import statements correctly.
        """
        from krrood.patterns.code_generation.analysis.imports import NameCollector
        from libcst.codemod import CodemodContext
        from libcst.codemod.visitors import AddImportsVisitor

        mixin_tree = libcst.Module(body=mixin_classes)

        # Collect names used in the mixin classes
        collector = NameCollector()
        mixin_tree.visit(collector)

        # Resolve each name to its module
        _EXCLUDED = {"ABC", "abstractmethod", "dataclass", "field", "TYPE_CHECKING"}
        codemod_ctx = CodemodContext()
        for name in collector.names:
            if name in _EXCLUDED:
                continue
            mod = resolver.resolve(name)
            if mod and mod not in ("builtins", "typing", "typing_extensions"):
                AddImportsVisitor.add_needed_import(codemod_ctx, mod, name)

        # Add standard imports that are always needed
        AddImportsVisitor.add_needed_import(codemod_ctx, "abc", "ABC")
        AddImportsVisitor.add_needed_import(codemod_ctx, "abc", "abstractmethod")
        AddImportsVisitor.add_needed_import(codemod_ctx, "dataclasses", "dataclass")

        mixin_tree = AddImportsVisitor(codemod_ctx).transform_module(mixin_tree)

        # Prepend __future__ import (must be first)
        future_stmt = libcst.parse_statement("from __future__ import annotations")
        mixin_tree = mixin_tree.with_changes(
            body=[future_stmt] + list(mixin_tree.body)
        )

        return mixin_tree.code

    def _compute_all_delegatees(self) -> set[type]:
        direct = set(self.class_diagram.role_takers) | self.pd_only_delegatees
        result = set(direct)
        for delegatee in direct:
            concrete = _normalize_type(delegatee)
            for ancestor in concrete.__mro__:
                if ancestor is object or ancestor is concrete:
                    continue
                if not same_package(ancestor.__module__, concrete.__module__):
                    continue
                result.add(ancestor)
        return result

    # ── path helpers ───────────────────────────────────────────────

    @staticmethod
    def get_module_file_path(module: ModuleType) -> Path:
        return Path(sys.modules[module.__name__].__file__)

    @staticmethod
    def _normalize_file_prefix(prefix: str) -> str:
        if prefix and not prefix.endswith("_"):
            return f"{prefix}_"
        return prefix

    def get_generated_file_path(
        self, module: ModuleType, is_mixin: bool = False
    ) -> Path:
        parent_directory = Path(self.get_module_file_path(module)).parent
        module_name = module.__name__.split(".")[-1]
        if is_mixin:
            role_mixins_folder = parent_directory / ROLE_MIXINS_FOLDER
            filename = f"{module_name}{ROLE_MIXINS_SUFFIX}.py"
            return role_mixins_folder / filename
        else:
            prefix = self._normalize_file_prefix(self.file_name_prefix)
            filename = f"{prefix}{module_name}.py"
            return parent_directory / filename
