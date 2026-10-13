"""
JSON (de)serialization of classes, with the serializers for numpy and scipy types.

Everything independent of those types lives in
:mod:`krrood_core.adapters.json_serializer` and is importable from here as well.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass

import numpy as np
from scipy.sparse import coo_array, csr_array
from typing_extensions import Dict, Any, Self, Type

from krrood_core.adapters.json_field import JSONField
from krrood_core.adapters.json_serializer import (
    _compute_attribute_diff,
    AttributeDiffJSONKey,
    ClassJSONSerializer,
    DataclassJSONSerializer,
    EnumJSONKey,
    EnumJSONSerializer,
    ExceptionJSONKey,
    ExceptionJSONSerializer,
    ExternalClassJSONSerializer,
    from_json,
    JSON_DICT_TYPE,
    JSON_RETURN_TYPE,
    JSONAttributeDiff,
    JSONData,
    JSONSerializableTypeRegistry,
    leaf_types,
    list_like_classes,
    PatternJSONKey,
    PatternJSONSerializer,
    PurePathJSONKey,
    PurePathJSONSerializer,
    RangeJSONKey,
    RangeJSONSerializer,
    ReferencedType,
    ReferenceWriter,
    resolve_class_from_full_name,
    shallow_diff_json,
    SliceJSONSerializer,
    SubclassJSONSerializer,
    T,
    TimedeltaJSONKey,
    TimedeltaJSONSerializer,
    TimezoneJSONKey,
    TimezoneJSONSerializer,
    to_json,
    UUIDJSONKey,
    UUIDJSONSerializer,
)
from krrood_core.class_lookup import get_full_class_name


class NumpyArrayJSONKey(enum.StrEnum):
    """
    The keys of the JSON a numpy array is serialized to.
    """

    ELEMENT_TYPE = "type"
    """
    The type the elements of the array share.
    """

    ELEMENTS = "data"
    """
    The elements of the array, nested as deeply as the array has dimensions.
    """


@dataclass
class NumpyNDarrayJSONSerializer(ExternalClassJSONSerializer[np.ndarray]):
    """
    External JSON serializer for numpy ndarrays.
    """

    @classmethod
    def to_json(cls, obj: np.ndarray, **kwargs) -> Dict[str, Any]:
        return {
            JSONField.TYPE: get_full_class_name(type(obj)),
            NumpyArrayJSONKey.ELEMENT_TYPE: str(obj.dtype),
            NumpyArrayJSONKey.ELEMENTS: obj.tolist(),
        }

    @classmethod
    def from_json(
        cls, data: Dict[str, Any], clazz: Type[np.ndarray], **kwargs
    ) -> np.ndarray:
        return np.array(
            data[NumpyArrayJSONKey.ELEMENTS], dtype=data[NumpyArrayJSONKey.ELEMENT_TYPE]
        )


class CoordinateSparseArrayJSONKey(enum.StrEnum):
    """
    The keys of the JSON a sparse array in coordinate format is serialized to.
    """

    DATA = "data"
    """
    The values of the stored entries.
    """

    ROWS = "rows"
    """
    The row of every stored entry.
    """

    COLUMNS = "columns"
    """
    The column of every stored entry.
    """

    SHAPE = "shape"
    """
    The shape of the dense array the sparse array describes.
    """


class CoordinateSparseArrayJSONSerializer(ExternalClassJSONSerializer[coo_array]):
    """
    External JSON serializer for scipy sparse arrays in coordinate format.

    Every stored entry is kept, including an explicitly stored zero.
    """

    @classmethod
    def to_json(cls, obj: coo_array, **kwargs) -> Dict[str, Any]:
        return {
            JSONField.TYPE: get_full_class_name(type(obj)),
            CoordinateSparseArrayJSONKey.DATA: to_json(obj.data, **kwargs),
            CoordinateSparseArrayJSONKey.ROWS: to_json(obj.row, **kwargs),
            CoordinateSparseArrayJSONKey.COLUMNS: to_json(obj.col, **kwargs),
            CoordinateSparseArrayJSONKey.SHAPE: list(obj.shape),
        }

    @classmethod
    def from_json(
        cls, data: Dict[str, Any], clazz: Type[coo_array], **kwargs
    ) -> coo_array:
        return coo_array(
            (
                from_json(data[CoordinateSparseArrayJSONKey.DATA], **kwargs),
                (
                    from_json(data[CoordinateSparseArrayJSONKey.ROWS], **kwargs),
                    from_json(data[CoordinateSparseArrayJSONKey.COLUMNS], **kwargs),
                ),
            ),
            shape=tuple(data[CoordinateSparseArrayJSONKey.SHAPE]),
        )


class CompressedSparseRowArrayJSONSerializer(ExternalClassJSONSerializer[csr_array]):
    """
    External JSON serializer for scipy sparse arrays in compressed sparse row format.

    The array is written like a sparse array in coordinate format, through its stored
    entries.
    """

    @classmethod
    def to_json(cls, obj: csr_array, **kwargs) -> Dict[str, Any]:
        return {
            **CoordinateSparseArrayJSONSerializer.to_json(obj.tocoo(), **kwargs),
            JSONField.TYPE: get_full_class_name(type(obj)),
        }

    @classmethod
    def from_json(
        cls, data: Dict[str, Any], clazz: Type[csr_array], **kwargs
    ) -> csr_array:
        return csr_array(
            CoordinateSparseArrayJSONSerializer.from_json(data, coo_array, **kwargs)
        )


class NumpyFloatJSONKey(enum.StrEnum):
    """
    The keys of the JSON a numpy float is serialized to.
    """

    VALUE = "value"
    """
    The number the float holds.
    """


@dataclass
class NumpyFloatJSONSerializer(ExternalClassJSONSerializer[np.float32]):
    """
    External JSON serializer for numpy floats.
    """

    @classmethod
    def to_json(cls, obj: np.float32, **kwargs) -> Dict[str, Any]:
        return {
            JSONField.TYPE: get_full_class_name(type(obj)),
            NumpyFloatJSONKey.VALUE: float(obj),
        }

    @classmethod
    def from_json(cls, data: Dict[str, Any], clazz: Type, **kwargs) -> Self:
        return float(data[NumpyFloatJSONKey.VALUE])
