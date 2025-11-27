from dataclasses import dataclass

from krrood.adapters.json_serializer import JSON_TYPE_NAME, JSONSerializableTypeRegistry
from krrood.utils import get_full_class_name
from typing_extensions import Any, Dict


class MotionStatechartError(Exception):
    pass


class GoalInitalizationException(MotionStatechartError):
    pass


class EmptyMotionStatechartError(MotionStatechartError):
    def __init__(self):
        super().__init__("MotionStatechart is empty.")


@dataclass
class NodeNotFoundError(MotionStatechartError):
    name: str

    def __post_init__(self):
        super().__init__(f"Node '{self.name}' not found in MotionStatechart.")


@dataclass
class NotInMotionStatechartError(MotionStatechartError):
    name: str

    def __post_init__(self):
        super().__init__(
            f"Operation can't be performed because node '{self.name}' does not belong to a MotionStatechart."
        )


@dataclass
class InvalidConditionError(MotionStatechartError):
    expression: Any

    def __post_init__(self):
        super().__init__(
            f"Invalid condition: {self.expression}. Did you forget '.observation_variable'?"
        )


def serialize_exception(obj: Exception) -> Dict[str, Any]:

    return {
        JSON_TYPE_NAME: get_full_class_name(type(obj)),
        "value": str(obj),
    }


def deserialize_exception(data: Dict[str, Any]) -> Exception:

    return Exception(data["value"])


JSONSerializableTypeRegistry().register(
    Exception, serialize_exception, deserialize_exception
)
