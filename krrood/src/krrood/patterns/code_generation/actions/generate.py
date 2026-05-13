"""
Generation actions that create new code artifacts.

Each action is atomic and reversible: :meth:`Action.apply` creates the
artifact, :meth:`Action.reverse` deletes or restores it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import libcst

from krrood.patterns.code_generation.actions.base import (
    GenerationAction,
    TransformationAction,
)
from krrood.patterns.code_generation.actions.plan import ActionPlan
from krrood.patterns.code_generation.libcst_node_factory import LibCSTNodeFactory
from krrood.patterns.code_generation.specs.specs import (
    BaseClassSpec,
    FieldSpec,
    MemberSpec,
    MethodSpec,
    PropertySpec,
)


# ── helpers ───────────────────────────────────────────────────────────


def _make_arg(name: str) -> libcst.Arg:
    return libcst.Arg(value=libcst.Name(name))


def _find_class_in_module(
    module: libcst.Module, class_name: str
) -> tuple[int, libcst.ClassDef] | None:
    for i, stmt in enumerate(module.body):
        if isinstance(stmt, libcst.ClassDef) and stmt.name.value == class_name:
            return i, stmt
    return None


# ── concrete generation actions ───────────────────────────────────────


@dataclass
class CreateClass(GenerationAction):
    """Create a new class definition and add it to a module.

    Reverse operation removes the class from the module.
    """

    class_name: str
    """The name of the class to create."""

    bases: list[BaseClassSpec] = field(default_factory=list)
    """Base classes for the new class."""

    body: list[libcst.BaseStatement] = field(default_factory=list)
    """The body statements of the new class."""

    decorators: list[libcst.Decorator] = field(default_factory=list)
    """Decorators to apply to the class."""

    def apply(self, module: libcst.Module) -> libcst.Module:
        bases_args = [_make_arg(b.name) for b in self.bases]
        class_def = libcst.ClassDef(
            name=libcst.Name(self.class_name),
            bases=bases_args,
            body=libcst.IndentedBlock(body=self.body),
            decorators=self.decorators,
        )
        return module.with_changes(
            body=list(module.body) + [class_def]
        )

    def reverse(self, module: libcst.Module) -> libcst.Module:
        found = _find_class_in_module(module, self.class_name)
        if found is None:
            return module
        idx, _ = found
        new_body = list(module.body)
        new_body.pop(idx)
        return module.with_changes(body=new_body)

    @property
    def description(self) -> str:
        return f"Create class {self.class_name}"


@dataclass
class CreateDerivedClass(ActionPlan):
    """Create a ``@dataclass(eq=False)`` mixin class with an abstract delegatee property.

    This is an :class:`ActionPlan` that composes a :class:`CreateClass` action
    with the right bases, decorator, and delegatee-property body pre-configured.

    Usage::

        plan = CreateDerivedClass(
            class_name="DelegatorForPerson",
            delegatee_type_name="Person",
            bases=[BaseClassSpec(name="DelegatorForHasName")],
        )
    """

    def __init__(
        self,
        class_name: str,
        delegatee_type_name: str,
        delegatee_attr: str = "delegatee",
        bases: list[BaseClassSpec] | None = None,
        extra_body: list[libcst.BaseStatement] | None = None,
    ):
        bases = list(bases or [])
        # Ensure ABC is always the terminal base
        if not any(b.name == "ABC" for b in bases):
            bases.append(BaseClassSpec(name="ABC"))

        delegatee_getter = LibCSTNodeFactory.make_property_getter_node(
            delegatee_attr, delegatee_type_name, "..."
        )

        super().__init__(
            actions=[
                CreateClass(
                    class_name=class_name,
                    bases=bases,
                    body=[delegatee_getter] + (extra_body or []),
                    decorators=[LibCSTNodeFactory.make_dataclass_decorator()],
                )
            ],
            description=f"Create derived class {class_name}",
        )


@dataclass
class CreateModule(GenerationAction):
    """Create a new :class:`libcst.Module` from a list of statements.

    This is typically the first action in a plan that generates a brand-new
    module.  Reverse returns an empty module.
    """

    body: list[libcst.BaseStatement] = field(default_factory=list)
    """Top-level statements for the new module."""

    _previous_module: libcst.Module | None = field(
        default=None, init=False, repr=False
    )

    def apply(self, module: libcst.Module) -> libcst.Module:
        self._previous_module = module
        return libcst.Module(body=self.body)

    def reverse(self, module: libcst.Module) -> libcst.Module:
        if self._previous_module is not None:
            return self._previous_module
        return libcst.Module(body=[])

    @property
    def description(self) -> str:
        return "Create new module"


@dataclass
class WriteModule(GenerationAction):
    """Write a module's source code to a file on disk.

    Reverse restores the original file from backup, or deletes the file if
    it was newly created by this action.
    """

    file_path: Path
    """The path to write to."""

    source: str
    """The source code to write."""

    _backup: str | None = field(default=None, init=False, repr=False)
    """Original file content before writing, or ``None`` for new files."""

    def apply(self, module: libcst.Module) -> libcst.Module:
        # Backup original if it exists
        if self.file_path.exists():
            self._backup = self.file_path.read_text()
        else:
            self._backup = None
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        self.file_path.write_text(self.source)
        return module

    def reverse(self, module: libcst.Module) -> libcst.Module:
        if self._backup is not None:
            self.file_path.write_text(self._backup)
        elif self.file_path.exists():
            self.file_path.unlink()
        return module

    @property
    def description(self) -> str:
        return f"Write module to {self.file_path}"


# ── delegation actions (compose AddProperty / AddMethod) ──────────────


def _parse_type_annotation(type_str: str | None) -> libcst.BaseExpression | None:
    """Parse a type string into a libcst expression, or return None."""
    if not type_str:
        return None
    try:
        return libcst.parse_expression(type_str)
    except Exception:
        return libcst.Name(type_str)


def _build_delegation_method_node(
    member: MemberSpec, delegatee_attr: str
) -> libcst.FunctionDef:
    """Build a method node that delegates to ``self.<delegatee_attr>.<name>()``."""
    param_names = [p.name for p in member.parameters if p.name not in ("self", "cls")]
    call_args = ", ".join(param_names)
    delegatee_path = f"self.{delegatee_attr}.{member.name}"
    body = libcst.IndentedBlock(
        [libcst.parse_statement(f"return {delegatee_path}({call_args})")]
    )
    params = [libcst.Param(name=libcst.Name("self"))]
    for p in member.parameters:
        if p.name in ("self", "cls"):
            continue
        ann = (
            libcst.Annotation(annotation=_parse_type_annotation(p.type_annotation))
            if p.type_annotation
            else None
        )
        default = None
        if p.has_default:
            default = libcst.Name("None")
        params.append(
            libcst.Param(name=libcst.Name(p.name), annotation=ann, default=default)
        )
    returns = None
    if member.return_type:
        returns = libcst.Annotation(
            annotation=_parse_type_annotation(member.return_type)
        )
    return libcst.FunctionDef(
        name=libcst.Name(member.name),
        params=libcst.Parameters(params=tuple(params)),
        body=body,
        returns=returns,
    )


def _build_field_getter_node(
    member: MemberSpec, delegatee_attr: str
) -> libcst.FunctionDef:
    """Build a property getter that returns ``self.<delegatee_attr>.<name>``."""
    delegatee_path = f"self.{delegatee_attr}.{member.name}"
    return LibCSTNodeFactory.make_property_getter_node(
        member.name, member.return_type, delegatee_path
    )


def _build_field_setter_node(
    member: MemberSpec, delegatee_attr: str
) -> libcst.FunctionDef | None:
    """Build a property setter node, or None for read-only properties."""
    delegatee_path = f"self.{delegatee_attr}.{member.name}"
    return LibCSTNodeFactory.make_property_setter_node(
        member.name,
        member.return_type,
        f"{delegatee_path} = value",
    )


@dataclass
class DelegateField(TransformationAction):
    """Add getter + setter delegation for a dataclass field."""

    member: MemberSpec
    target_class: str
    delegatee_attr: str = "delegatee"

    def apply(self, module: libcst.Module) -> libcst.Module:
        getter = _build_field_getter_node(self.member, self.delegatee_attr)
        setter = _build_field_setter_node(self.member, self.delegatee_attr)
        from krrood.patterns.code_generation.actions.transform import AddProperty

        return AddProperty(self.target_class, getter, setter).apply(module)

    def reverse(self, module: libcst.Module) -> libcst.Module:
        getter = _build_field_getter_node(self.member, self.delegatee_attr)
        setter = _build_field_setter_node(self.member, self.delegatee_attr)
        from krrood.patterns.code_generation.actions.transform import AddProperty

        return AddProperty(self.target_class, getter, setter).reverse(module)

    @property
    def description(self) -> str:
        return f"Delegate field {self.member.name} to {self.target_class}"


@dataclass
class DelegateProperty(TransformationAction):
    """Add getter-only delegation for a Python property."""

    member: MemberSpec
    target_class: str
    delegatee_attr: str = "delegatee"

    def apply(self, module: libcst.Module) -> libcst.Module:
        getter = _build_field_getter_node(self.member, self.delegatee_attr)
        from krrood.patterns.code_generation.actions.transform import AddProperty

        return AddProperty(self.target_class, getter, None).apply(module)

    def reverse(self, module: libcst.Module) -> libcst.Module:
        getter = _build_field_getter_node(self.member, self.delegatee_attr)
        from krrood.patterns.code_generation.actions.transform import AddProperty

        return AddProperty(self.target_class, getter, None).reverse(module)

    @property
    def description(self) -> str:
        return f"Delegate property {self.member.name} to {self.target_class}"


@dataclass
class DelegateMethod(TransformationAction):
    """Add a delegating method that forwards to the delegatee."""

    member: MemberSpec
    target_class: str
    delegatee_attr: str = "delegatee"

    def apply(self, module: libcst.Module) -> libcst.Module:
        node = _build_delegation_method_node(self.member, self.delegatee_attr)
        from krrood.patterns.code_generation.actions.transform import AddMethod

        return AddMethod(self.target_class, node).apply(module)

    def reverse(self, module: libcst.Module) -> libcst.Module:
        node = _build_delegation_method_node(self.member, self.delegatee_attr)
        from krrood.patterns.code_generation.actions.transform import AddMethod

        return AddMethod(self.target_class, node).reverse(module)

    @property
    def description(self) -> str:
        return f"Delegate method {self.member.name} to {self.target_class}"
