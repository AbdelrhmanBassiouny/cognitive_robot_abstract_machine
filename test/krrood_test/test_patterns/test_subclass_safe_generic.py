import inspect

from typing_extensions import get_type_hints, List, get_args, get_origin, ForwardRef

from dataset.classes_with_generic import (
    SubClassGenericThatUpdatesGenericTypeToBuiltInType,
    SubClassGenericThatUpdatesGenericTypeToTypeDefinedInSameModule,
    SubClassGenericThatUpdatesGenericTypeToAForwardReferencedClass,
    SubClassGenericThatUpdatesGenericTypeToTypeDefinedInImportedModuleOfThisLibrary,
)
from krrood.class_diagrams.utils import resolve_type
from krrood.entity_query_language.core.mapped_variable import MappedVariable
from krrood.entity_query_language.factories import variable, variable_from
from krrood.patterns.subclass_safe_generic import SubClassSafeGeneric
from krrood.utils import T, get_generic_type_param
from ..dataset.classes_with_generic import FirstGeneric


def test_resolve_generic_type_same_class():
    _assert_generic_type_is_resolved(FirstGeneric)


def test_resolve_generic_type_subclass_with_built_in_type_as_generic_type():
    cls = SubClassGenericThatUpdatesGenericTypeToBuiltInType
    _assert_generic_type_is_resolved(cls)


def test_resolve_generic_type_subclass_with_type_defined_in_same_module_as_generic_type():
    cls = SubClassGenericThatUpdatesGenericTypeToTypeDefinedInSameModule
    _assert_generic_type_is_resolved(cls)


def test_resolve_generic_type_subclass_with_type_defined_in_imported_module_of_this_library():
    cls = (
        SubClassGenericThatUpdatesGenericTypeToTypeDefinedInImportedModuleOfThisLibrary
    )
    _assert_generic_type_is_resolved(cls)


def test_resolve_generic_type_subclass_with_forward_referenced_type_as_generic_type():
    cls = SubClassGenericThatUpdatesGenericTypeToAForwardReferencedClass
    _assert_generic_type_is_resolved(cls)


def _assert_generic_type_is_resolved(cls):
    resolved_hints = get_type_hints(cls, include_extras=True)
    generic_type = get_generic_type_param(cls, SubClassSafeGeneric)[0]
    if isinstance(generic_type, ForwardRef):
        generic_type = eval(
            generic_type.__forward_arg__, inspect.getmodule(cls).__dict__
        )
    assert (
        resolved_hints[variable_from(cls).attribute_using_generic._attribute_name_]
        is generic_type
    )
    nested_generic_type = resolved_hints[
        variable_from(cls).generic_attribute_using_generic._attribute_name_
    ]
    assert (
        get_origin(nested_generic_type) is list
        and get_args(nested_generic_type)[0] is generic_type
    )
