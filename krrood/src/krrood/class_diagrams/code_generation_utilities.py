"""
Utilities for generating Python source code (e.g. dataclass class bodies)
and for inspecting callables (parameter names, annotations, module paths).
"""
from __future__ import annotations

import inspect
import typing
from typing_extensions import Callable, Dict, Optional, Tuple


class FunctionMissingAnnotationsError(TypeError):
    """Raised at decoration time when a function lacks required type annotations."""


def to_camel_case(name: str) -> str:
    """Convert snake_case to CamelCase. E.g. 'my_func' → 'MyFunc'."""
    return "".join(part.capitalize() for part in name.split("_"))


def generate_callable_import(func: Callable) -> Tuple[str, str]:
    """Return ``(import_line, access_expression)`` for *func*.

    :param func: The callable to generate an import for.
    :returns: A 2-tuple: the ``from … import …`` line and the name expression
        used to reference the callable after that import.

    Module-level function ``distance`` in ``my.module``::

        ("from my.module import distance", "distance")

    Method ``MyClass.distance`` in ``my.module``::

        ("from my.module import MyClass", "MyClass.distance")
    """
    module_name = func.__module__
    qualname = func.__qualname__
    qualname_parts = qualname.split(".")

    # A function is a method when the segment immediately before its name is a
    # valid identifier with no angle brackets.  Closures have <locals> in their
    # qualname, which disqualifies the outer function from being treated as a
    # class owner.
    parent_segment = qualname_parts[-2] if len(qualname_parts) >= 2 else None
    is_method = (
        parent_segment is not None
        and parent_segment.isidentifier()
        and "<" not in parent_segment
    )

    if is_method:
        class_name = parent_segment
        import_line = f"from {module_name} import {class_name}"
        access_expr = f"{class_name}.{func.__name__}"
    else:
        import_line = f"from {module_name} import {func.__name__}"
        access_expr = func.__name__

    return import_line, access_expr


def validate_annotations(func: Callable) -> None:
    """Raise :exc:`FunctionMissingAnnotationsError` if any required annotation is absent.

    Unannotated ``self`` and ``cls`` parameters are silently excluded.
    """
    sig = inspect.signature(func)
    for param_name, param in sig.parameters.items():
        if param_name in ("self", "cls"):
            continue
        if param.annotation is inspect.Parameter.empty:
            raise FunctionMissingAnnotationsError(
                f"Parameter '{param_name}' of '{func.__qualname__}' "
                f"lacks a type annotation."
            )
    if sig.return_annotation is inspect.Parameter.empty:
        raise FunctionMissingAnnotationsError(
            f"Function '{func.__qualname__}' lacks a return type annotation."
        )


def function_to_dataclass_source(
    func: Callable,
    base_class_fqn: str = (
        "krrood.entity_query_language.rdr.function_case.FunctionCase"
    ),
    class_name: Optional[str] = None,
) -> str:
    """Emit Python source for a ``@dataclass`` subclass of ``FunctionCase``.

    The emitted class has:

    - ``function: ClassVar[Callable] = <access_expr>`` — bound to the decorated
      callable via a module-level import (wrapped in try/except so the source
      can also be exec'd in isolated test namespaces).
    - One field per annotated parameter (``self`` / ``cls`` excluded).
    - ``_output: <return_annotation>`` — the attribute the RDR will predict.

    :param func: The callable to generate a case type for.
    :param base_class_fqn: Fully-qualified name of the base class to inherit from.
    :param class_name: Override for the generated class name.  When ``None`` the
        name is derived from ``func.__name__`` via :func:`to_camel_case`.  Pass
        an explicit name when re-generating a file for an already-named case type
        (e.g. ``SyntheticFunctionCase``) so the stored name is preserved.
    :raises FunctionMissingAnnotationsError: If any required annotation is absent.
    :returns: A Python source string that can be written to a ``.py`` file.
    """
    validate_annotations(func)

    if class_name is None:
        class_name = to_camel_case(func.__name__)
    import_line, access_expr = generate_callable_import(func)

    base_module, base_class_name = base_class_fqn.rsplit(".", 1)

    # Resolve string annotations (produced by `from __future__ import annotations`
    # in the caller's module) to actual type objects before formatting.
    # get_type_hints may fail for locally-defined functions whose forward refs
    # cannot be resolved in their module's __globals__ (e.g. closures in tests).
    try:
        type_hints: Dict[str, object] = typing.get_type_hints(func)
    except NameError:
        type_hints = {}

    # Collect custom types referenced by annotations.  Builtins (float, int, str,
    # bool, NoneType) are always available and need no import; everything else
    # must be imported as a bare name in the generated file so the @dataclass
    # machinery can resolve them when the file is loaded.
    sig = inspect.signature(func)
    referenced_types: Dict[str, type] = {}
    _safe_names = {"float", "int", "str", "bytes", "bool", "NoneType", "type", "Any"}
    for param_name, param in sig.parameters.items():
        if param_name in ("self", "cls"):
            continue
        t = type_hints.get(param_name, param.annotation)
        # t may be a string (unresolved forward ref) — skip those
        if isinstance(t, type) and t.__module__ not in ("builtins",):
            referenced_types[t.__name__] = t
    t_ret = type_hints.get("return", sig.return_annotation)
    if isinstance(t_ret, type) and t_ret.__module__ not in ("builtins",):
        referenced_types[t_ret.__name__] = t_ret

    # Generate type-import lines grouped by module.
    imports_by_module: Dict[str, set] = {}
    for type_name, type_obj in referenced_types.items():
        imports_by_module.setdefault(type_obj.__module__, set()).add(type_name)
    type_import_lines = "\n".join(
        f"from {module} import {', '.join(sorted(names))}"
        for module, names in sorted(imports_by_module.items())
    )
    type_imports_str = type_import_lines + "\n" if type_import_lines else ""

    def _type_name(raw_ann: object) -> str:
        """Convert a type annotation to its bare-name string representation."""
        return raw_ann.__name__ if isinstance(raw_ann, type) else str(raw_ann)

    field_lines = [
        f"    {param_name}: {_type_name(type_hints.get(param_name, param.annotation))}"
        for param_name, param in sig.parameters.items()
        if param_name not in ("self", "cls")
    ]
    return_ann_str = _type_name(type_hints.get("return", sig.return_annotation))

    lines = [
        "from __future__ import annotations",
        "from dataclasses import dataclass",
        "from typing_extensions import ClassVar, Callable",
        f"from {base_module} import {base_class_name}",
        type_imports_str,
        "try:",
        f"    {import_line}",
        "except ImportError:",
        "    pass",
        "",
        "",
        "@dataclass",
        f"class {class_name}({base_class_name}):",
        f'    """FunctionCase for the `{func.__name__}` function."""',
        *field_lines,
        f"    _output: {return_ann_str}",
        "",
        "",
        # Assign function ClassVar outside the class body so that Python's
        # @dataclass machinery (which sees string annotations under PEP 563)
        # never confuses it for an instance field with a default value.
        # Wrapped in try/except NameError: when the decorated function is not at
        # module level (e.g., in tests), the import above silently fails and the
        # assignment would raise NameError.  The @rdr decorator sets the ClassVar
        # explicitly after loading, so the fallback is safe.
        "try:",
        f"    {class_name}.function = {access_expr}",
        "except NameError:",
        "    pass",
        "",
    ]
    return "\n".join(lines)
