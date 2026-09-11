"""
A role whose taker is a JSON-serializable class that leaves a generic parameter free.

Mimics a recorded query playing the role of the question it answered: the question is
serialized as JSON rather than mapped to a table of its own, and it is generic over what
it answers with, so a concrete question binds that parameter while the role names only
the base.
"""

from __future__ import annotations

from dataclasses import dataclass

from typing_extensions import Any, Dict, Generic, Self, TypeVar

from krrood.adapters.json_serializer import SubclassJSONSerializer, from_json, to_json
from krrood.patterns.role import Role
from krrood.patterns.subclass_safe_generic import SubClassSafeGeneric

AnswerType = TypeVar("AnswerType")
"""
What a question answers with.
"""


@dataclass
class SerializableQuestion(
    SubclassJSONSerializer, Generic[AnswerType], SubClassSafeGeneric
):
    """
    A question kept as JSON, generic over its answer.
    """

    wording: str
    """
    The question as it is asked.
    """

    def to_json(self) -> Dict[str, Any]:
        return {**super().to_json(), "wording": to_json(self.wording)}

    @classmethod
    def _from_json(cls, data: Dict[str, Any], **kwargs) -> Self:
        return cls(wording=from_json(data["wording"]))


@dataclass
class YesOrNoQuestion(SerializableQuestion[bool]):
    """
    A question answered with yes or no.
    """


@dataclass(eq=False)
class AnsweredQuestion(Role[SerializableQuestion]):
    """
    A question playing the part of one answer given to it.
    """

    answer: str
    """
    What was answered.
    """
