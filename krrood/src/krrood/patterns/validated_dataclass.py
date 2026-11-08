"""
Dataclasses whose fields are validated whenever an instance is made or read from JSON.
"""

from __future__ import annotations

import dataclasses

from pydantic import ConfigDict, TypeAdapter
from pydantic.dataclasses import dataclass as pydantic_dataclass
from typing_extensions import Any, Self, dataclass_transform

from krrood.adapters.json_field import JSONField
from krrood.adapters.json_serializer import SubclassJSONSerializer

# %% validated dataclasses


@dataclass_transform(field_specifiers=(dataclasses.field,))
class ValidatedDataclass(SubclassJSONSerializer):
    """
    A dataclass for data whose shape someone else controls, checked against its field
    types when an instance is made or read from JSON.

    Every subclass is a pydantic dataclass on definition, so it carries no dataclass
    decorator. Pass a subclass its own pydantic settings as the class keyword
    ``config``; its subclasses inherit them. A field the data names differently declares
    that key as its pydantic alias, and is still set by its name in code.
    """

    __pydantic_config__ = ConfigDict(validate_by_name=True, validate_by_alias=True)
    """
    The pydantic settings every subclass starts from.
    """

    def __init_subclass__(cls, config: ConfigDict | None = None, **kwargs) -> None:
        """
        Make the subclass a pydantic dataclass.

        :param config: The pydantic settings of the subclass, on top of those it
            inherits.
        """
        super().__init_subclass__(**kwargs)
        cls.__pydantic_config__ = ConfigDict(
            **cls.__pydantic_config__, **(config or {})
        )
        pydantic_dataclass(cls)

    def to_json(self, **kwargs) -> dict[str, Any]:
        """
        :meth:`SubclassJSONSerializer.to_json`, followed by every field in its JSON form
        under its alias where it has one.
        """
        return {
            **super().to_json(**kwargs),
            **TypeAdapter(type(self)).dump_python(self, mode="json", by_alias=True),
        }

    @classmethod
    def _from_json(cls, data: dict[str, Any], **kwargs) -> Self:
        """
        Read an instance, the class of every nested object given by its field.

        :raises pydantic.ValidationError: If a value is missing or has the wrong type.
        """
        return TypeAdapter(cls).validate_python(
            {key: value for key, value in data.items() if key not in JSONField}
        )
