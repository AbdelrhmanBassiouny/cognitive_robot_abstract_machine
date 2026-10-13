"""
Krrood keeps every name it moved to :mod:`krrood_core` importable from its old place, as
the same object, so an ``isinstance`` check or an ``except`` clause written against
either import matches both.
"""

import numpy as np
import pytest

import krrood.adapters.exceptions
import krrood.adapters.json_field
import krrood.adapters.json_serializer
import krrood.adapters.keyword_argument
import krrood.class_diagrams.attribute_introspector
import krrood.exceptions
import krrood.ormatic.data_access_objects.base
import krrood.ormatic.exceptions
import krrood.ormatic.utils
import krrood.patterns.field_metadata
import krrood.singleton
import krrood.utils
import krrood_core.adapters.exceptions
import krrood_core.adapters.json_field
import krrood_core.adapters.json_serializer
import krrood_core.adapters.keyword_argument
import krrood_core.attribute_introspector
import krrood_core.class_lookup
import krrood_core.class_property
import krrood_core.exceptions
import krrood_core.field_metadata
import krrood_core.generics
import krrood_core.singleton
from krrood.adapters.json_serializer import (
    JSONSerializableTypeRegistry,
    NumpyNDarrayJSONSerializer,
)


@pytest.mark.parametrize(
    "krrood_name, core_name",
    [
        (
            krrood.exceptions.DataclassException,
            krrood_core.exceptions.DataclassException,
        ),
        (
            krrood.ormatic.exceptions.NoGenericError,
            krrood_core.exceptions.NoGenericError,
        ),
        (krrood.singleton.SingletonMeta, krrood_core.singleton.SingletonMeta),
        (krrood.ormatic.utils.classproperty, krrood_core.class_property.classproperty),
        (
            krrood.ormatic.data_access_objects.base.HasGeneric,
            krrood_core.generics.HasGeneric,
        ),
        (
            krrood.utils.get_full_class_name,
            krrood_core.class_lookup.get_full_class_name,
        ),
        (
            krrood.utils.recursive_subclasses,
            krrood_core.class_lookup.recursive_subclasses,
        ),
        (
            krrood.utils.resolve_class_from_full_name,
            krrood_core.class_lookup.resolve_class_from_full_name,
        ),
        (
            krrood.patterns.field_metadata.JSONMetadata,
            krrood_core.field_metadata.JSONMetadata,
        ),
        (
            krrood.class_diagrams.attribute_introspector.DataclassOnlyIntrospector,
            krrood_core.attribute_introspector.DataclassOnlyIntrospector,
        ),
        (
            krrood.adapters.json_field.JSONField,
            krrood_core.adapters.json_field.JSONField,
        ),
        (
            krrood.adapters.keyword_argument.SerializationKeywordArgument,
            krrood_core.adapters.keyword_argument.SerializationKeywordArgument,
        ),
        (
            krrood.adapters.exceptions.JSONSerializationError,
            krrood_core.adapters.exceptions.JSONSerializationError,
        ),
        (
            krrood.adapters.json_serializer.SubclassJSONSerializer,
            krrood_core.adapters.json_serializer.SubclassJSONSerializer,
        ),
        (
            krrood.adapters.json_serializer.DataclassJSONSerializer,
            krrood_core.adapters.json_serializer.DataclassJSONSerializer,
        ),
        (
            krrood.adapters.json_serializer.to_json,
            krrood_core.adapters.json_serializer.to_json,
        ),
        (
            krrood.adapters.json_serializer.from_json,
            krrood_core.adapters.json_serializer.from_json,
        ),
    ],
)
def test_the_old_import_is_the_core_object(krrood_name, core_name):
    assert krrood_name is core_name


def test_krrood_field_metadata_extends_the_core_one():
    assert issubclass(
        krrood.patterns.field_metadata.FieldMetadata,
        krrood_core.field_metadata.FieldMetadata,
    )


def test_the_core_registry_finds_the_serializers_krrood_adds():
    assert (
        JSONSerializableTypeRegistry().get_external_serializer(np.ndarray)
        is NumpyNDarrayJSONSerializer
    )
