from copy import deepcopy
from dataclasses import dataclass, field

from typing_extensions import Callable, Dict, Any, Generic, TypeVar

from krrood.adapters.json_serializer import list_like_classes

T = TypeVar("T")


@dataclass
class HasFactoryAndKwargs(Generic[T]):
    """
    Mixin containing a hierarchy of factories and their keyword arguments.

    The attributes are underscore-wrapped because hosts of this mixin may hand their
    public attribute namespace to the constructed type (symbolic attribute delegation).
    """

    _factory_: Callable[..., T]
    """
    The factory function to construct `T` with the keyword arguments.
    """

    _kwargs_: Dict[str, Any] = field(default_factory=dict, kw_only=True)
    """
    The keyword arguments to pass to the factory.
    """

    def construct_instance(self):
        """
        Construct a python object from the CallableAndKwargs instance.

        ..note:: This method may work with ellipsis, but it's not guaranteed to work with all types.

        :return: The constructed object.
        """
        constructed_kwargs = {}
        for key, value in self._kwargs_.items():
            if isinstance(value, list_like_classes):
                constructed_kwargs[key] = type(value)(
                    self._recurse_construct_instance_and_get_value(element)
                    for element in value
                )
            else:
                constructed_kwargs[key] = (
                    self._recurse_construct_instance_and_get_value(value)
                )
        return self._factory_(**constructed_kwargs)

    def _recurse_construct_instance_and_get_value(self, value: Any):
        """
        Recursively construct an instance and return it.

        :param value: The value to construct.
        :return: The constructed instance.
        """
        if isinstance(value, HasFactoryAndKwargs):
            return value.construct_instance()
        return value

    def __deepcopy__(self, memo):
        return self.__class__(
            self._factory_,
            _kwargs_={name: deepcopy(value) for name, value in self._kwargs_.items()},
        )
