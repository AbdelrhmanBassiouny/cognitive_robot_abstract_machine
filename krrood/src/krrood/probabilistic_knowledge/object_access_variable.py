from dataclasses import dataclass
from typing import Any, assert_never, Never

from typing_extensions import List

from random_events.variable import Variable


@dataclass
class ObjectAccessVariable:
    """
    Class to represent a variable that accesses an object field.
    """

    variable: Variable
    """
    The random events variable used to represent the object field.
    """

    access_path: List[str | int]
    """
    The list of access paths used to access the object field.
    """

    def set_value(self, obj: Any, value: Any):
        """
        Set the field of the object at the access path to the given value.

        :param obj: The object to be updated.
        :param value: The value to set.
        """
        current = obj
        for access_value in self.access_path[:-1]:
            if isinstance(access_value, int):
                current = current[access_value]
            elif isinstance(access_value, str):
                current = getattr(current, access_value)
            else:
                assert_never(access_value)

        if isinstance(self.access_path[-1], int):
            current[self.access_path[-1]] = value
        elif isinstance(self.access_path[-1], str):
            setattr(current, self.access_path[-1], value)
