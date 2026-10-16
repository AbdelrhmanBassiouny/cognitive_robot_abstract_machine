from __future__ import annotations

import sys
from dataclasses import dataclass, Field, fields

from typing_extensions import Any, Dict, List, TypeVar, get_type_hints

from krrood.ormatic.utils import classproperty
from krrood.patterns.field_metadata import ParameterMetadata

T = TypeVar("T")


@dataclass(eq=False, kw_only=True)
class DesignatorParameters:
    """
    Reads back the parameters a designator was built with, off its dataclass fields.

    Carries no state of its own, so anything can mix it in to describe itself by the
    arguments it was given, whatever else it happens to be.
    """

    @classproperty
    def fields(cls) -> List[Field]:
        """
        The fields of this designator a caller sets: every field taking a constructor
        argument, unless it is marked as no parameter with
        :class:`~krrood.patterns.field_metadata.ParameterMetadata`.

        :return: The fields the caller parameterizes this designator with.
        """
        parameter_fields = [
            dataclass_field
            for dataclass_field in fields(cls)
            if dataclass_field.init and cls._is_parameter(dataclass_field)
        ]
        type_hints = cls.get_type_hints()
        for parameter_field in parameter_fields:
            parameter_field.type = type_hints[parameter_field.name]
        return parameter_fields

    @staticmethod
    def _is_parameter(dataclass_field: Field) -> bool:
        """
        :return: Whether `dataclass_field` is not marked as no parameter.
        """
        metadata = dataclass_field.metadata.get(ParameterMetadata)
        return metadata is None or metadata.is_parameter

    @property
    def designator_parameter(self) -> Dict[str, Any]:
        """
        :return: Every parameter of this designator, by the name it was given under.
        """
        return {f.name: getattr(self, f.name) for f in self.fields}

    @classmethod
    def get_type_hints(cls) -> Dict[str, Any]:
        """
        Returns the type hints of the __init__ method of this designator_description
        description.

        :return:
        """
        global_namespace = sys.modules[cls.__module__].__dict__
        return get_type_hints(cls.__init__, globalns=global_namespace)
