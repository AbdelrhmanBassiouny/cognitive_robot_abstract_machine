from __future__ import annotations

from dataclasses import dataclass

from typing_extensions import Optional, Self, TYPE_CHECKING

from krrood_core.field_metadata import FieldMetadata as CoreFieldMetadata
from krrood_core.field_metadata import JSONMetadata

if TYPE_CHECKING:
    from krrood.class_diagrams.wrapped_field import WrappedField


@dataclass
class FieldMetadata(CoreFieldMetadata):
    """
    Krrood-specific metadata carried inside a dataclass field's ``metadata`` mapping,
    which can also be read off a field of a class diagram.
    """

    @classmethod
    def of_wrapped_field(cls, wrapped_field: WrappedField) -> Optional[Self]:
        """
        :return: the instance of *cls* attached to the dataclass field behind
            *wrapped_field*, or ``None`` when that field carries no metadata of type *cls*.

        ..note:: The lookup goes through the dataclass field name, which may differ from
            the public name under which the field is addressed.
        """
        return cls.of_field(wrapped_field.clazz.clazz, wrapped_field.field.name)
