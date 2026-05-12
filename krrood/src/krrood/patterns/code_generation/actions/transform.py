"""
Transformation actions that modify an existing :class:`libcst.Module`.

Each action is atomic and reversible: :meth:`Action.apply` makes the change,
:meth:`Action.reverse` undoes it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Sequence

import libcst
from libcst.codemod import CodemodContext
from libcst.codemod.visitors import AddImportsVisitor

from krrood.patterns.code_generation.actions.base import TransformationAction
from krrood.patterns.code_generation.specs.specs import BaseClassSpec


# ── module-level helpers ─────────────────────────────────────────────


def _find_class(
    module: libcst.Module, class_name: str
) -> tuple[int, libcst.ClassDef] | None:
    """Return ``(index, ClassDef)`` for *class_name* in *module*, or ``None``."""
    for i, stmt in enumerate(module.body):
        if isinstance(stmt, libcst.ClassDef) and stmt.name.value == class_name:
            return i, stmt
    return None


def _find_class_in_body(
    body: Sequence[libcst.BaseStatement], class_name: str
) -> tuple[int, libcst.ClassDef] | None:
    """Return ``(index, ClassDef)`` for *class_name* in a body sequence, or ``None``."""
    for i, stmt in enumerate(body):
        if isinstance(stmt, libcst.ClassDef) and stmt.name.value == class_name:
            return i, stmt
    return None


def _replace_in_module(
    module: libcst.Module, index: int, new_stmt: libcst.BaseStatement
) -> libcst.Module:
    """Return *module* with the statement at *index* replaced by *new_stmt*."""
    new_body = list(module.body)
    new_body[index] = new_stmt
    return module.with_changes(body=new_body)


def _remove_from_module_body(
    body: Sequence[libcst.BaseStatement], index: int
) -> list[libcst.BaseStatement]:
    """Return a new body list with the element at *index* removed."""
    new_body = list(body)
    new_body.pop(index)
    return new_body


def _append_to_module_body(
    body: Sequence[libcst.BaseStatement], stmt: libcst.BaseStatement
) -> list[libcst.BaseStatement]:
    """Return a new body list with *stmt* appended."""
    return list(body) + [stmt]


def _make_arg(name: str) -> libcst.Arg:
    """Return a :class:`libcst.Arg` wrapping a plain :class:`libcst.Name`."""
    return libcst.Arg(value=libcst.Name(name))


# ── concrete transformation actions ──────────────────────────────────


@dataclass
class AddBaseClass(TransformationAction):
    """Add a base class to an existing class definition.

    Reverse operation removes the added base.
    """

    target_class: str
    """The name of the class to modify."""

    base_spec: BaseClassSpec
    """The base class to add."""

    def apply(self, module: libcst.Module) -> libcst.Module:
        found = _find_class(module, self.target_class)
        if found is None:
            raise ValueError(
                f"Class '{self.target_class}' not found in module."
            )
        idx, class_def = found
        new_bases = list(class_def.bases) + [_make_arg(self.base_spec.name)]
        new_class = class_def.with_changes(bases=new_bases)
        return _replace_in_module(module, idx, new_class)

    def reverse(self, module: libcst.Module) -> libcst.Module:
        found = _find_class(module, self.target_class)
        if found is None:
            return module
        idx, class_def = found
        new_bases = tuple(
            b for b in class_def.bases
            if libcst.Module([]).code_for_node(b) != self.base_spec.name
        )
        new_class = class_def.with_changes(bases=new_bases)
        return _replace_in_module(module, idx, new_class)

    @property
    def description(self) -> str:
        return f"Add {self.base_spec.name} base to {self.target_class}"


@dataclass
class RemoveBaseClass(TransformationAction):
    """Remove a base class from an existing class definition.

    The reverse operation re-adds the removed base.
    """

    target_class: str
    """The name of the class to modify."""

    base_name: str
    """The name of the base class to remove."""

    def apply(self, module: libcst.Module) -> libcst.Module:
        found = _find_class(module, self.target_class)
        if found is None:
            return module
        idx, class_def = found
        new_bases = tuple(
            b
            for b in class_def.bases
            if not self._is_named_arg(b, self.base_name)
        )
        new_class = class_def.with_changes(bases=new_bases)
        return _replace_in_module(module, idx, new_class)

    def reverse(self, module: libcst.Module) -> libcst.Module:
        found = _find_class(module, self.target_class)
        if found is None:
            return module
        idx, class_def = found
        new_bases = list(class_def.bases) + [_make_arg(self.base_name)]
        new_class = class_def.with_changes(bases=new_bases)
        return _replace_in_module(module, idx, new_class)

    @staticmethod
    def _is_named_arg(arg: libcst.Arg, name: str) -> bool:
        """Check whether *arg* is a plain ``Name`` argument matching *name*."""
        if isinstance(arg.value, libcst.Name):
            return arg.value.value == name
        return False

    @property
    def description(self) -> str:
        return f"Remove {self.base_name} base from {self.target_class}"


@dataclass
class AddMethod(TransformationAction):
    """Add a method (or function) to a class body.

    Reverse operation removes the method by name.
    """

    target_class: str
    """The name of the class to modify."""

    method: libcst.FunctionDef
    """The method node to add."""

    def apply(self, module: libcst.Module) -> libcst.Module:
        found = _find_class(module, self.target_class)
        if found is None:
            raise ValueError(
                f"Class '{self.target_class}' not found in module."
            )
        idx, class_def = found
        new_body = class_def.body.with_changes(
            body=list(class_def.body.body) + [self.method]
        )
        new_class = class_def.with_changes(body=new_body)
        return _replace_in_module(module, idx, new_class)

    def reverse(self, module: libcst.Module) -> libcst.Module:
        found = _find_class(module, self.target_class)
        if found is None:
            return module
        idx, class_def = found
        method_name = self.method.name.value
        new_body_nodes = [
            stmt
            for stmt in class_def.body.body
            if not (
                isinstance(stmt, libcst.FunctionDef)
                and stmt.name.value == method_name
            )
        ]
        new_body = class_def.body.with_changes(body=new_body_nodes)
        new_class = class_def.with_changes(body=new_body)
        return _replace_in_module(module, idx, new_class)

    @property
    def description(self) -> str:
        return f"Add method {self.method.name.value} to {self.target_class}"


@dataclass
class AddProperty(TransformationAction):
    """Add a property (getter and optional setter) to a class body.

    Reverse operation removes both getter and setter by name.
    """

    target_class: str
    """The name of the class to modify."""

    getter: libcst.FunctionDef
    """The property getter node."""

    setter: libcst.FunctionDef | None = None
    """The property setter node, or ``None`` for read-only properties."""

    def apply(self, module: libcst.Module) -> libcst.Module:
        found = _find_class(module, self.target_class)
        if found is None:
            raise ValueError(
                f"Class '{self.target_class}' not found in module."
            )
        idx, class_def = found
        new_nodes = list(class_def.body.body) + [self.getter]
        if self.setter is not None:
            new_nodes.append(self.setter)
        new_body = class_def.body.with_changes(body=new_nodes)
        new_class = class_def.with_changes(body=new_body)
        return _replace_in_module(module, idx, new_class)

    def reverse(self, module: libcst.Module) -> libcst.Module:
        found = _find_class(module, self.target_class)
        if found is None:
            return module
        idx, class_def = found
        prop_name = self.getter.name.value
        setter_name = self.setter.name.value if self.setter else None
        new_body_nodes = [
            stmt
            for stmt in class_def.body.body
            if not (
                isinstance(stmt, libcst.FunctionDef)
                and stmt.name.value in (prop_name, setter_name)
            )
        ]
        new_body = class_def.body.with_changes(body=new_body_nodes)
        new_class = class_def.with_changes(body=new_body)
        return _replace_in_module(module, idx, new_class)

    @property
    def description(self) -> str:
        return f"Add property {self.getter.name.value} to {self.target_class}"


@dataclass
class AddDecorator(TransformationAction):
    """Add a decorator to a class definition.

    Reverse operation removes the decorator.
    """

    target_class: str
    """The name of the class to modify."""

    decorator: libcst.Decorator
    """The decorator node to prepend."""

    def apply(self, module: libcst.Module) -> libcst.Module:
        found = _find_class(module, self.target_class)
        if found is None:
            raise ValueError(
                f"Class '{self.target_class}' not found in module."
            )
        idx, class_def = found
        new_decorators = [self.decorator] + list(class_def.decorators)
        new_class = class_def.with_changes(decorators=new_decorators)
        return _replace_in_module(module, idx, new_class)

    def reverse(self, module: libcst.Module) -> libcst.Module:
        found = _find_class(module, self.target_class)
        if found is None:
            return module
        idx, class_def = found
        deco_code = libcst.Module([]).code_for_node(self.decorator)
        new_decorators = [
            d
            for d in class_def.decorators
            if libcst.Module([]).code_for_node(d) != deco_code
        ]
        new_class = class_def.with_changes(decorators=new_decorators)
        return _replace_in_module(module, idx, new_class)

    @property
    def description(self) -> str:
        deco_code = libcst.Module([]).code_for_node(self.decorator)
        return f"Add decorator {deco_code} to {self.target_class}"


@dataclass
class AddImport(TransformationAction):
    """Add one or more imports to a module.

    Uses libcst's :class:`AddImportsVisitor` for correct placement and
    deduplication.  Reverse operation removes the import statement.
    """

    module_name: str
    """The dotted source module name (e.g. ``"typing"``)."""

    names: list[str] = field(default_factory=list)
    """The names to import from *module_name*."""

    is_type_checking: bool = False
    """If ``True``, place the import inside ``if TYPE_CHECKING:``."""

    def apply(self, module: libcst.Module) -> libcst.Module:
        if not self.names:
            return module
        ctx = CodemodContext()
        for name in self.names:
            AddImportsVisitor.add_needed_import(
                ctx, self.module_name, name
            )
        return AddImportsVisitor(ctx).transform_module(module)

    def reverse(self, module: libcst.Module) -> libcst.Module:
        # Remove the import statement that matches our names and module.
        new_body = []
        for stmt in module.body:
            if self._is_our_import(stmt):
                # Filter out only our specific names, keeping others.
                remaining = self._filter_names_from_import(stmt)
                if remaining is not None:
                    new_body.append(remaining)
                # If remaining is None (no names left), omit the statement.
            else:
                new_body.append(stmt)
        return module.with_changes(body=new_body)

    def _is_our_import(self, stmt: libcst.BaseStatement) -> bool:
        """Check whether *stmt* is an import from our target module."""
        if not isinstance(stmt, libcst.SimpleStatementLine):
            return False
        for body_stmt in stmt.body:
            if isinstance(body_stmt, libcst.ImportFrom):
                mod = libcst.Module([]).code_for_node(body_stmt.module)
                if mod is not None and mod == self.module_name:
                    return True
        return False

    def _filter_names_from_import(
        self, stmt: libcst.BaseStatement
    ) -> libcst.BaseStatement | None:
        """Return *stmt* with our names removed, or ``None`` if empty."""
        if not isinstance(stmt, libcst.SimpleStatementLine):
            return stmt
        new_inner = []
        for body_stmt in stmt.body:
            if isinstance(body_stmt, libcst.ImportFrom):
                our_set = set(self.names)
                new_names = [
                    alias
                    for alias in body_stmt.names
                    if alias.name.value not in our_set
                ]
                if not new_names:
                    return None  # remove entire statement
                new_import = body_stmt.with_changes(names=new_names)
                new_inner.append(new_import)
            else:
                new_inner.append(body_stmt)
        if not new_inner:
            return None
        return stmt.with_changes(body=new_inner)

    @property
    def description(self) -> str:
        names = ", ".join(self.names)
        return f"Add import of {names} from {self.module_name}"


@dataclass
class EnsureSuperInitCall(TransformationAction):
    """Ensure ``super_class.__init__(self)`` is called in a class's ``__init__``.

    Used to inject ``HasRoles.__init__(self)`` into role-taker classes that
    have an explicit ``__init__`` with ``init=False`` in ``@dataclass``.

    Reverse operation removes the injected statement.
    """

    target_class: str
    """The name of the class to modify."""

    super_class_name: str
    """The name of the super class whose ``__init__`` should be called."""

    _added: bool = field(default=False, init=False, repr=False)
    """Internal flag: ``True`` if a statement was actually added."""

    def apply(self, module: libcst.Module) -> libcst.Module:
        found = _find_class(module, self.target_class)
        if found is None:
            return module
        idx, class_def = found
        init_result = self._find_init(class_def.body)
        if init_result is None:
            return module
        init_idx, init_func = init_result

        expected_call = f"{self.super_class_name}.__init__"
        if self._has_call(init_func, expected_call):
            return module

        new_stmt = libcst.parse_statement(
            f"{self.super_class_name}.__init__(self)"
        )
        new_init_body = libcst.IndentedBlock(
            list(init_func.body.body) + [new_stmt]
        )
        new_init = init_func.with_changes(body=new_init_body)
        new_class_body = class_def.body.with_changes(
            body=list(class_def.body.body[:init_idx])
            + [new_init]
            + list(class_def.body.body[init_idx + 1:])
        )
        new_class = class_def.with_changes(body=new_class_body)
        self._added = True
        return _replace_in_module(module, idx, new_class)

    def reverse(self, module: libcst.Module) -> libcst.Module:
        if not self._added:
            return module
        found = _find_class(module, self.target_class)
        if found is None:
            return module
        idx, class_def = found
        init_result = self._find_init(class_def.body)
        if init_result is None:
            return module
        init_idx, init_func = init_result
        expected_call = f"{self.super_class_name}.__init__"
        new_stmts = [
            s
            for s in init_func.body.body
            if not self._is_call_to(s, expected_call)
        ]
        new_init_body = init_func.body.with_changes(body=new_stmts)
        new_init = init_func.with_changes(body=new_init_body)
        new_class_body = class_def.body.with_changes(
            body=list(class_def.body.body[:init_idx])
            + [new_init]
            + list(class_def.body.body[init_idx + 1:])
        )
        new_class = class_def.with_changes(body=new_class_body)
        return _replace_in_module(module, idx, new_class)

    @staticmethod
    def _find_init(
        body: libcst.IndentedBlock,
    ) -> tuple[int, libcst.FunctionDef] | None:
        for i, node in enumerate(body.body):
            if (
                isinstance(node, libcst.FunctionDef)
                and node.name.value == "__init__"
            ):
                return i, node
        return None

    @staticmethod
    def _has_call(func: libcst.FunctionDef, target: str) -> bool:
        for stmt in func.body.body:
            if EnsureSuperInitCall._is_call_to(stmt, target):
                return True
        return False

    @staticmethod
    def _is_call_to(
        stmt: libcst.BaseStatement, target: str
    ) -> bool:
        """Return True if *stmt* is an expression statement calling *target*."""
        return (
            isinstance(stmt, libcst.SimpleStatementLine)
            and len(stmt.body) == 1
            and isinstance(stmt.body[0], libcst.Expr)
            and isinstance(stmt.body[0].value, libcst.Call)
            and libcst.Module([]).code_for_node(
                stmt.body[0].value.func
            )
            == target
        )

    @property
    def description(self) -> str:
        return (
            f"Ensure {self.super_class_name}.__init__(self) "
            f"in {self.target_class}.__init__"
        )
