"""
Exceptions raised by the code generation package.

Each exception is a :class:`dataclass` whose **fields are the error context**.
The human-readable message is computed from those fields by
:meth:`_format_message`, never stored redundantly.  Every exception carries
an optional ``fix_suggestion`` hint.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(kw_only=True)
class CodeGenerationError(ValueError):
    """Base exception for all code generation errors.

    Subclasses add specific fields that describe the failure.  The string
    representation is built from those fields, so callers can either catch
    a specific subclass and inspect its fields, or just call ``str(exc)``
    for a readable message.

    All fields are keyword-only so that subclasses can add required fields
    without running into dataclass ordering constraints.

    Attributes:
        fix_suggestion: A hint about how the caller might resolve the error.
    """

    fix_suggestion: str = ""

    # ── internal ──────────────────────────────────────────────────────

    def __post_init__(self):
        if not self.args:
            ValueError.__init__(self, str(self))

    def __str__(self) -> str:
        parts = [self._format_message()]
        if self.fix_suggestion:
            parts.append(f"Fix: {self.fix_suggestion}")
        return "\n".join(parts)

    def _format_message(self) -> str:
        """Return the human-readable error message derived from this
        exception's fields.  Override in every subclass."""
        return type(self).__name__


# ── module / class errors ───────────────────────────────────────────


@dataclass
class ClassNotFoundError(CodeGenerationError):
    """Raised when a target class is not found in a :class:`libcst.Module`.

    Attributes:
        target_class: The name of the class that was looked for.
        module_name: The dotted name of the module being processed.
    """

    target_class: str
    module_name: str = ""

    def _format_message(self) -> str:
        msg = f"Class '{self.target_class}' not found"
        if self.module_name:
            msg += f" in module '{self.module_name}'"
        return msg

    def __post_init__(self):
        if not self.fix_suggestion:
            self.fix_suggestion = (
                f"Verify that a class named '{self.target_class}' exists in "
                f"the source module"
                f"{f' ({self.module_name})' if self.module_name else ''}."
            )
        super().__post_init__()


@dataclass
class InitMethodNotFoundError(CodeGenerationError):
    """Raised when ``__init__`` is expected but not found on a class.

    Attributes:
        target_class: The name of the class missing ``__init__``.
    """

    target_class: str

    def _format_message(self) -> str:
        return (
            f"Class '{self.target_class}' has no __init__ method, but one "
            f"was expected for super-init injection."
        )

    def __post_init__(self):
        if not self.fix_suggestion:
            self.fix_suggestion = (
                f"Either add an explicit __init__ to '{self.target_class}' or "
                f"remove the EnsureSuperInitCall action for this class."
            )
        super().__post_init__()


@dataclass
class InvalidCSTNodeError(CodeGenerationError):
    """Raised when a CST node has an unexpected type during transformation.

    Attributes:
        expected_type: The expected CST node type name (e.g. ``FunctionDef``).
        actual_type: The actual type that was encountered.
    """

    expected_type: str
    actual_type: str

    def _format_message(self) -> str:
        return f"Expected {self.expected_type}, got {self.actual_type}."

    def __post_init__(self):
        if not self.fix_suggestion:
            self.fix_suggestion = (
                "Check that the source code being transformed matches the "
                "expected structure for this transformation."
            )
        super().__post_init__()


# ── spec errors ──────────────────────────────────────────────────────


@dataclass
class InvalidSpecError(CodeGenerationError):
    """Raised when a spec dataclass is invalid or inconsistent.

    Attributes:
        spec_type: The type name of the invalid spec (e.g. ``DelegationSpec``).
        field_name: The name of the problematic field, if known.
    """

    spec_type: str
    field_name: str = ""

    def _format_message(self) -> str:
        msg = f"Invalid {self.spec_type} spec"
        if self.field_name:
            msg += f": field '{self.field_name}' is invalid or missing"
        return msg

    def __post_init__(self):
        if not self.fix_suggestion:
            self.fix_suggestion = (
                f"Check the construction of the {self.spec_type} in the "
                f"analyzer that produced it."
            )
        super().__post_init__()


# ── action errors ────────────────────────────────────────────────────


@dataclass
class ActionError(CodeGenerationError):
    """Base for errors raised during action application or reversal.

    Attributes:
        action_description: The :attr:`Action.description` of the failing action.
    """

    action_description: str

    def _format_message(self) -> str:
        return f"Action error: {self.action_description}"


@dataclass
class ActionPreconditionError(ActionError):
    """Raised when an action's precondition is not met.

    Attributes:
        precondition_detail: What specific condition failed.
    """

    precondition_detail: str = ""

    def _format_message(self) -> str:
        msg = f"Precondition failed for '{self.action_description}'"
        if self.precondition_detail:
            msg += f": {self.precondition_detail}"
        return msg

    def __post_init__(self):
        if not self.fix_suggestion:
            self.fix_suggestion = (
                "Ensure the module is in the expected state before applying "
                "this action. Run the appropriate analyzer to verify the spec."
            )
        super().__post_init__()


@dataclass
class ActionApplyError(ActionError):
    """Raised when an action fails during :meth:`Action.apply`.

    Attributes:
        original_error: The exception that caused the failure, if any.
    """

    original_error: Exception | None = None

    def _format_message(self) -> str:
        msg = f"Failed to apply action '{self.action_description}'"
        if self.original_error:
            msg += f": {self.original_error}"
        return msg

    def __post_init__(self):
        if not self.fix_suggestion and self.original_error:
            self.fix_suggestion = (
                f"Underlying error: {self.original_error}. "
                f"Check the action implementation and the module state."
            )
        super().__post_init__()


@dataclass
class ActionReverseError(ActionError):
    """Raised when an action fails during :meth:`Action.reverse` (rollback).

    Attributes:
        original_error: The exception that caused the rollback failure.
    """

    original_error: Exception | None = None

    def _format_message(self) -> str:
        msg = f"Failed to reverse action '{self.action_description}'"
        if self.original_error:
            msg += f": {self.original_error}"
        return msg


# ── analysis errors ──────────────────────────────────────────────────


@dataclass
class DelegationAnalysisError(CodeGenerationError):
    """Raised when MRO walking or delegation analysis fails.

    Attributes:
        class_name: The class being analyzed for delegation.
        member_name: The member that triggered the error, if known.
    """

    class_name: str
    member_name: str = ""

    def _format_message(self) -> str:
        msg = f"Delegation analysis failed for class '{self.class_name}'"
        if self.member_name:
            msg += f", member '{self.member_name}'"
        return msg

    def __post_init__(self):
        if not self.fix_suggestion:
            self.fix_suggestion = (
                "Check the MRO and field/property/method definitions of "
                f"'{self.class_name}'."
            )
        super().__post_init__()


@dataclass
class ImportResolutionError(CodeGenerationError):
    """Raised when an import name cannot be resolved to a source module.

    Attributes:
        name: The identifier that could not be resolved.
        current_class: The class being processed when resolution failed.
    """

    name: str
    current_class: str = ""

    def _format_message(self) -> str:
        msg = f"Cannot resolve import for '{self.name}'"
        if self.current_class:
            msg += f" (while processing {self.current_class})"
        return msg

    def __post_init__(self):
        if not self.fix_suggestion:
            self.fix_suggestion = (
                f"Register '{self.name}' in the ImportNameResolver's "
                f"name_to_module_map, or add its source module to "
                f"companion_modules."
            )
        super().__post_init__()


@dataclass
class TypeNormalisationError(CodeGenerationError):
    """Raised when a Python type cannot be normalised to a source-code string.

    Attributes:
        type_obj: The type that failed normalisation.
        type_repr: String representation of the problematic type.
    """

    type_obj: Any = None
    type_repr: str = ""

    def _format_message(self) -> str:
        return f"Cannot normalise type '{self.type_repr or self.type_obj}'"

    def __post_init__(self):
        if not self.fix_suggestion:
            self.fix_suggestion = (
                "Register the type with the ImportNameResolver or use a "
                "string forward reference (e.g. 'MyClass' instead of MyClass)."
            )
        super().__post_init__()


# ── planner errors ───────────────────────────────────────────────────


@dataclass
class PlannerError(CodeGenerationError):
    """Raised when the planner cannot convert a spec into an action plan.

    Attributes:
        spec_type: The type name of the problematic spec.
        reason: Why the spec could not be planned.
    """

    spec_type: str
    reason: str = ""

    def _format_message(self) -> str:
        msg = f"Failed to plan {self.spec_type}"
        if self.reason:
            msg += f": {self.reason}"
        return msg

    def __post_init__(self):
        if not self.fix_suggestion:
            self.fix_suggestion = (
                f"Verify the {self.spec_type} is complete and consistent. "
                f"Check that all required fields are populated by the analyzer."
            )
        super().__post_init__()


# ── file I/O errors ──────────────────────────────────────────────────


@dataclass
class FileWriteError(CodeGenerationError):
    """Raised when a generated file cannot be written to disk.

    Attributes:
        file_path: The path that could not be written.
        reason: Why the write failed (e.g. permission denied).
    """

    file_path: Path | str
    reason: str = ""

    def _format_message(self) -> str:
        msg = f"Failed to write generated file '{self.file_path}'"
        if self.reason:
            msg += f": {self.reason}"
        return msg

    def __post_init__(self):
        if not self.fix_suggestion:
            self.fix_suggestion = (
                "Check that the target directory exists and is writable, "
                "and that no other process is holding the file open."
            )
        super().__post_init__()
