"""
The base classes of the conversion between the circuits of the ``rx`` package and the
layered circuits of the ``tensorized`` package.

Neither package knows about the other; every conversion lives in a converter class
here. A converter handles one input type and is found by the base class it derives
from, so adding a conversion is subclassing a base class, without any registration.
"""

from __future__ import annotations

from abc import ABC
from dataclasses import dataclass, field

from krrood.exceptions import DataclassException
from krrood.utils import recursive_subclasses
from typing_extensions import Any, Generic, Type, TypeVar, get_args

InputType = TypeVar("InputType")
OutputType = TypeVar("OutputType")


@dataclass
class CannotConvertError(DataclassException):
    """
    Raised when no converter handles an object.
    """

    data_type: Type = field(kw_only=True)
    """
    The type of the object that could not be converted.
    """

    def error_message(self) -> str:
        return f"No converter handles {self.data_type.__name__}."

    def suggest_correction(self) -> str:
        return (
            "Subclass the converter base class for the type, binding it as the input "
            "type."
        )


class Converter(ABC, Generic[InputType, OutputType]):
    """
    Base class for converters from one representation to another.

    A concrete converter binds the input and output type and overrides :meth:`convert`.
    """

    @classmethod
    def input_type(cls) -> Type[InputType]:
        """
        :return: The type this converter converts.
        """
        return get_args(cls.__orig_bases__[0])[0]

    @classmethod
    def output_type(cls) -> Type[OutputType]:
        """
        :return: The type this converter converts into.
        """
        return get_args(cls.__orig_bases__[0])[1]

    @classmethod
    def can_convert(cls, data: Any) -> bool:
        """
        Override this to customize which objects this converter handles.

        :param data: The object to convert.
        :return: Whether this converter handles the object.
        """
        return type(data) is cls.input_type()

    @classmethod
    def converter_for(cls, data: Any) -> Type[Converter]:
        """
        :param data: The object to convert.
        :return: The subclass of this class that handles the object.
        :raises CannotConvertError: If no subclass handles it.
        """
        for converter in recursive_subclasses(cls):
            if isinstance(converter.input_type(), TypeVar):
                continue
            if converter.can_convert(data):
                return converter
        raise CannotConvertError(data_type=type(data))

    @classmethod
    def convert(cls, data: InputType, *context: Any) -> OutputType:
        """
        Convert an object with the converter that handles it.

        :param data: The object to convert.
        :param context: The state of the conversion the object is part of.
        :return: The converted object.
        """
        return cls.converter_for(data).convert(data, *context)


class RustworkxToTensorizedConverter(Converter[InputType, OutputType], ABC):
    """
    Base class for converters from the ``rx`` package to the ``tensorized`` package.
    """


class TensorizedToRustworkxConverter(Converter[InputType, OutputType], ABC):
    """
    Base class for converters from the ``tensorized`` package to the ``rx`` package.
    """
