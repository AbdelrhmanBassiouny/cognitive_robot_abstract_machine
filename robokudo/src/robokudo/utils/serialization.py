"""
@author: Max Gandyra

Based on: "https://github.com/jsonpickle/jsonpickle"

Can encode/decode any object as JSON-object and also store and load them from files/strings.

:param json_backend: JSON module to use (e.g. json, ujson)
:type json_backend: ModuleType, optional
:param bytes_to_base64: Whether to encode bytes as base64
:type bytes_to_base64: bool, optional
:param use_bytes_references: Whether to use references for bytes objects
:type use_bytes_references: bool, optional
:param use_module_references: Whether to use references for modules
:type use_module_references: bool, optional
:param use_module_function_references: Whether to use references for module functions
:type use_module_function_references: bool, optional
:param use_set_references: Whether to use references for sets
:type use_set_references: bool, optional
:param use_string_references: Whether to use references for strings
:type use_string_references: bool, optional
:param use_tuple_references: Whether to use references for tuples
:type use_tuple_references: bool, optional
:param use_type_references: Whether to use references for types
:type use_type_references: bool, optional
:param replacement_names: Mapping of old to new module/class names
:type replacement_names: dict, optional

Dependencies
-----------
* json/orjson/rapidjson for JSON serialization
* numpy for array serialization
* open3d for point cloud serialization
* base64 for binary data encoding

See Also
--------
* :mod:`robokudo.utils.file_loader` : File path resolution
* :mod:`robokudo.utils.transform` : Transform serialization

"""

import io
import types
from enum import Enum
import base64
from abc import ABC, abstractmethod
import importlib

# import typing as ty
import typing_extensions as ty

type_swap_obj = ty.Union[object, ty.MutableSequence, ty.MutableMapping]
type_set_func = ty.Callable[[type_swap_obj, ty.Any, "_PlaceholderObject"], None]
type_placeholders = ty.Dict[
    ty.Any, ty.List[ty.Tuple[type_swap_obj, ty.Any, ty.Any, type_set_func]]
]


# special keys
BYTES: str = "<bytes>"
ID: str = "<id>"
JSON_KEY: str = "<json_key>:"
MODULE: str = "<module>"
MODULE_FUNCTION: str = "<module_function>"
NEWARGS: str = "<newargs>"
NEWARGS_EX: str = "<newargs_ex>"
OBJECT: str = "<object>"
REDUCE: str = "<reduce>"
SET: str = "<set>"
STATE: str = "<state>"
TUPLE: str = "<tuple>"
TYPE: str = "<type>"

FlattenKeys: ty.Set[str] = {
    BYTES,
    ID,
    JSON_KEY,
    MODULE,
    MODULE_FUNCTION,
    NEWARGS,
    NEWARGS_EX,
    OBJECT,
    REDUCE,
    SET,
    STATE,
    TUPLE,
    TYPE,
}


# JSON backend to use for encoding/decoding
# list of all possible JSON backends, first element has the highest priority
JSON_BACKEND_LIST: ty.List[str] = ["ujson", "json"]


def get_json_backend() -> types.ModuleType:
    """Get the first available JSON serialization backend.

    Tries to load backends in order from JSON_BACKEND_LIST until one succeeds.

    :return: Loaded JSON backend module
    :rtype: types.ModuleType
    :raises ImportError: If no backend could be loaded
    """
    try:
        return get_json_backend._backend
    except AttributeError:
        # init with first existing backend
        for name in JSON_BACKEND_LIST:
            try:
                # try to load json backend
                get_json_backend._backend = importlib.import_module(name)

                # return loaded backend
                return get_json_backend._backend
            except ImportError:
                # ignore
                pass
        else:
            raise ImportError(
                "None of the JSON backends in list <{}> could be imported.".format(
                    JSON_BACKEND_LIST
                )
            )


# test functions to identify object
def is_builtin_function(obj: ty.Any) -> bool:
    return obj.__class__ is types.BuiltinFunctionType


def is_builtin_method(obj: ty.Any) -> bool:
    return obj.__class__ is types.BuiltinMethodType


def is_bool(obj: ty.Any) -> bool:
    return obj.__class__ is bool


def is_bytes(obj: ty.Any) -> bool:
    return obj.__class__ is bytes


def is_dictionary(obj: ty.Any) -> bool:
    return obj.__class__ is dict


def is_enum(obj: ty.Any) -> bool:
    return isinstance(obj, Enum)


def is_function(obj: ty.Any) -> bool:
    return obj.__class__ is types.FunctionType


def is_lambda_function(obj: ty.Any) -> bool:
    return obj.__class__ is types.LambdaType


def is_list(obj: ty.Any) -> bool:
    return obj.__class__ is list


def is_method(obj: ty.Any) -> bool:
    return obj.__class__ is types.MethodType


def is_module(obj: ty.Any) -> bool:
    return obj.__class__ is types.ModuleType


def is_number(obj: ty.Any) -> bool:
    return isinstance(obj, (int, float))


def is_none(obj: ty.Any) -> bool:
    return obj is None


def is_set(obj: ty.Any) -> bool:
    return obj.__class__ is set


def is_string(obj: ty.Any) -> bool:
    return obj.__class__ is str


def is_tuple(obj: ty.Any) -> bool:
    return obj.__class__ is tuple


def is_type(obj: ty.Any) -> bool:
    return isinstance(obj, type)


def is_generic_function(obj: ty.Any) -> bool:
    return (
        is_function(obj)
        or is_method(obj)
        or is_builtin_function(obj)
        or is_builtin_method(obj)
        or is_lambda_function(obj)
    )


def is_object(obj: ty.Any) -> bool:
    return isinstance(obj, object) and not (is_type(obj) or is_generic_function(obj))


def is_module_function(obj: ty.Any) -> bool:
    return (
        (
            is_function(obj)
            or is_method(obj)
            or is_builtin_function(obj)
            or is_builtin_method(obj)
        )
        and hasattr(obj, "__module__")
        and hasattr(obj, "__name__")
        and obj.__name__ != "<lambda>"
    )  # using 'is_lambda_function' does not always work


def is_primitive(obj: ty.Any) -> bool:
    return is_bool(obj) or is_none(obj) or is_number(obj) or is_string(obj)


def attr_in_dict(obj: object, attr: ty.Any, default: ty.Any = None):
    return attr in obj.__dict__ if hasattr(obj, "__dict__") else default


def attr_in_slots(obj: object, attr: ty.Any, default: ty.Any = None):
    return attr in obj.__slots__ if hasattr(obj, "__slots__") else default


def has_attr_with_class_filter(
    obj: object, attr: str, class_only: bool = False, exclude_list: ty.List[type] = None
) -> bool:
    if exclude_list is None:
        exclude_list = []

    if not hasattr(obj, attr):
        # no where found
        return False

    if is_type(obj):
        obj_cls: type = obj
    else:
        if not class_only:
            # search in instance for the attribute
            if attr_in_dict(obj, attr) or attr_in_slots(obj, attr):
                return True

        obj_cls: type = obj.__class__

    for base_cls in obj_cls.__mro__:
        if base_cls in exclude_list:
            # ignore this class
            continue

        if attr_in_dict(base_cls, attr) or attr_in_slots(base_cls, attr):
            # found the attribute
            return True

    # did not find the attribute
    return False


# module and class name storing and loading
def combine_module_class_name(module_name: str, class_name: str) -> str:
    return "{}><{}".format(module_name, class_name)


def split_module_class_name(module_class_name: str) -> ty.List[str]:
    return module_class_name.split("><")


def class_to_module_class_name(
    cls: type,
    replacement_names: ty.Optional[ty.Dict[str, str]] = None,
) -> str:
    """Returns the combination of the module and fully qualified name of the class.

    :parameter cls: The class to get the name for
    :type cls: type
    :parameter replacement_names: Dictionary mapping old module.class names to new ones, by default None
    :type replacement_names: dict, optional
    :returns: Combined module and class name in the format "module><class"
    :rtype: str

    .. note
    This function handles special cases like:

    * Classes without modules
    * Classes with __self__ attributes
    * Name replacements for refactoring
    """
    # try to use the fully-qualified name
    class_name = getattr(cls, "__qualname__", cls.__name__)

    # get module name with path
    module_name = cls.__module__

    if not module_name and hasattr(cls, "__self__"):
        # search for module name in its class
        module_name = getattr(
            cls.__self__, "__module__", cls.__self__.__class__.__module__
        )

    module_class_name = "{}><{}".format(module_name, class_name)

    if replacement_names:
        # check if a replacement value for 'module_class_name' is available, e.g. because of renaming/refactoring.
        module_class_name = replacement_names.get(module_class_name, module_class_name)

    return module_class_name


def locate_and_load_module(
    module_class_name: str, seperator: ty.Optional[str] = "."
) -> type:
    """Load a module from its fully qualified name.

    :param module_class_name: Fully qualified module/class name
    :type module_class_name: str
    :type seperator: str, optional
    :param separator: Separator between module parts, by default "."
    :returns: Loaded module class
    :rtype: type
    :raises ImportError: If module cannot be loaded or does not exist
    """
    if not len(module_class_name):
        raise ImportError("Given module/class path is empty.")

    # split name into separated module and class name parts
    parts = module_class_name.split(seperator)

    try:
        # try to load the first module
        cls = importlib.import_module(parts[0])
    except ModuleNotFoundError as exec_import:
        raise ImportError(
            "Could not load module <{}> from module/class path <{}>.".format(parts[0]),
            module_class_name,
        ) from exec_import

    for i in range(1, len(parts)):
        try:
            cls = getattr(cls, parts[i])
        except AttributeError as exec_attr:
            if is_module(cls):
                sub_module_path = ".".join(parts[: i + 1])
                try:
                    cls = importlib.import_module(sub_module_path)
                except ModuleNotFoundError as exec_import:
                    raise ImportError(
                        "Could not load module <{}> from module/class path <{}>.".format(
                            sub_module_path, module_class_name
                        )
                    ) from exec_import
                continue
            else:
                raise ImportError(
                    "The module <{}> from module/class path has no attribute <{}>.".format(
                        module_class_name, ".".join(parts[:i]), parts[i]
                    )
                ) from exec_attr

    return cls


def module_class_name_to_class(
    module_class_name: str,
    replacement_names: ty.Optional[ty.Dict[str, str]] = None,
    cache: ty.Optional[ty.Dict[str, type]] = None,
    seperator: ty.Optional[str] = ".",
    module_class_seperator: ty.Optional[str] = "><",
) -> type:
    """Returns the class described via the combined module and fully qualified class name.

    :param module_class_name: Fully qualified module/class name
    :type module_class_name: str
    :param replacement_names: Mapping of old to new module names
    :type replacement_names: dict, optional
    :param cache: Cache of previously loaded classes
    :type cache: dict, optional
    :param seperator: Separator between module parts, by default "."
    :type seperator: str, optional
    :param module_class_seperator: Separator between module and class, by default "><"
    :type module_class_seperator: str, optional
    :returns: Loaded class
    :rtype: type
    :raises ImportError: If class cannot be loaded
    :raises ValueError: If module/class path format is invalid
    """
    if replacement_names:
        # check if a replacement value for 'module_class_name' is available, e.g. because of renaming/refactoring.
        module_class_name = replacement_names.get(module_class_name, module_class_name)

    if (
        module_class_name == "builtins><NoneType"
        or module_class_name == "builtins.NoneType"
    ):
        # special case, because 'NoneType' cannot be imported
        return type(None)

    # check in cache, if already loaded
    if cache and module_class_name in cache:
        return cache[module_class_name]

    # check if splitting in module name and class name is possible
    parts = (
        module_class_name.split(module_class_seperator)
        if module_class_seperator
        else [module_class_name, ""]
    )
    if len(parts) == 1:
        # need to try out all possible splits
        cls = locate_and_load_module(module_class_name, seperator=seperator)
    elif len(parts) == 2:
        # use module name and class name
        module_name, class_name = parts

        if not len(module_name):
            raise ImportError("Given module path is empty.")

        # load module
        cls = importlib.import_module(module_name)

        if len(class_name):
            # load most inner class
            for sub_name in class_name.split(seperator):
                cls = getattr(cls, sub_name)
    else:
        raise ValueError(
            "The module/class path <{}> should only contain one special seperator symbol <{}>.".format(
                module_class_name, module_class_seperator
            )
        )

    if cache is not None:
        # update cache
        cache[module_class_name] = cls

    return cls


# helper functions for object id references and placeholder objects
def make_object_reference(
    obj: ty.Any, obj_to_id: ty.Dict[ty.Any, int], id_to_obj: ty.List[ty.Any]
) -> ty.Tuple[bool, int]:
    obj_id: int = id(obj)

    if obj_id in obj_to_id:
        # known object
        return False, obj_to_id[obj_id]
    else:
        # new object
        new_id: int = len(obj_to_id)
        obj_to_id[obj_id] = new_id
        id_to_obj.append(obj)

        return True, new_id


def swap_object_reference(
    old_obj: ty.Any,
    new_obj: ty.Any,
    obj_to_id: ty.Dict[ty.Any, int],
    id_to_obj: ty.List[ty.Any],
) -> None:
    old_obj_id: int = id(old_obj)
    new_obj_id: int = id(new_obj)

    ref_id: int = obj_to_id[old_obj_id]
    obj_to_id[new_obj_id] = ref_id
    del obj_to_id[old_obj_id]

    id_to_obj[ref_id] = new_obj


class _PlaceholderObject(object):
    def __init__(self):
        self.obj: ty.Any = None


def _object_set_attr_with_placeholder(
    obj: object, attr: ty.Any, placeholder: _PlaceholderObject
) -> None:
    setattr(obj, attr, placeholder.obj)


def _object_set_value_with_placeholder(
    obj: ty.Union[ty.MutableSequence, ty.MutableMapping],
    index: ty.Any,
    placeholder: _PlaceholderObject,
) -> None:
    obj[index] = placeholder.obj


def make_new_placeholder_reference(
    obj_to_id: ty.Dict[ty.Any, int], id_to_obj: ty.List[ty.Any]
) -> ty.Tuple[_PlaceholderObject, bool, int]:
    place_holder: _PlaceholderObject = _PlaceholderObject()
    return place_holder, *make_object_reference(place_holder, obj_to_id, id_to_obj)  # type: ignore


def try_add_value_placeholder_swap(
    obj: type_swap_obj,
    attr: ty.Any,
    value: ty.Any,
    set_func: type_set_func,
    placeholders: type_placeholders,
) -> None:
    if isinstance(value, _PlaceholderObject):
        # needs to be replaced later with the real object
        placeholders.setdefault(value, []).append((obj, attr, value, set_func))


def set_and_swap_placeholder_with_object(
    placeholder: _PlaceholderObject,
    obj: ty.Any,
    obj_to_id: ty.Dict[ty.Any, int],
    id_to_obj: ty.List[ty.Any],
    placeholders: type_placeholders,
) -> None:
    placeholder.obj = obj

    swap_object_reference(placeholder, obj, obj_to_id, id_to_obj)

    if placeholder in placeholders:
        # replace all placeholder references with real object
        for obj, attr, value, set_func in placeholders[placeholder]:
            set_func(obj, attr, value)

        del placeholders[placeholder]


# handlers for custom flatten/unflatten of certain object types/class
class HandlerRegistry(object):
    """Registry for custom object serialization handlers.

    This class manages handlers for serializing custom objects to JSON format.
    It supports:

    * Registration of handlers for specific types
    * Base class handlers for subclass serialization
    * Primary and secondary handler chains
    * Normal and base handler modes

    Attributes
    ----------
    _primary_handlers : dict
        Mapping of types to primary handlers
    _secondary_handlers : dict
        Mapping of types to secondary handlers
    _primary_base_handlers : dict
        Mapping of base types to primary handlers
    _secondary_base_handlers : dict
        Mapping of base types to secondary handlers
    """

    class HandlerBase(ABC):
        """Abstract base class for custom serialization handlers.

        :param context: The Flatten or Unflatten context object
        :type context: Union["Flatten", "Unflatten"]
        """

        def __init__(self, context):
            # uses either 'Flatten' or 'Unflatten' object as context
            self.context: ty.Union["Flatten", "Unflatten"] = context

        @classmethod
        def can_handle(cls, obj_cls: type) -> bool:
            """Check if this handler can handle the given class.

            :param obj_cls: The class to check
            :type obj_cls: type
            :return: True if can handle, False otherwise
            :rtype: bool
            """
            return True

        @abstractmethod
        def flatten(self, obj: object, data: ty.Dict) -> ty.Dict:
            """Flatten an object to a dictionary format.

            :param obj: Object to flatten
            :type obj: object
            :param data: Dictionary to store flattened data
            :type data: dict
            :return: Dictionary containing flattened object
            :rtype: dict
            :raises NotImplementedError: Must be implemented by subclass
            """
            raise NotImplementedError()

        @abstractmethod
        def unflatten(self, data: ty.Dict, obj: ty.Optional[object]) -> object:
            """Unflatten a dictionary back into an object.

            :param data: Dictionary containing flattened data
            :type data: dict
            :param obj: Optional existing object to unflatten into
            :type obj: object, optional
            :return: Reconstructed object
            :rtype: object
            :raises NotImplementedError: Must be implemented by subclass
            """
            raise NotImplementedError()

    def __init__(self):
        # handlers to use only for the exact matching class
        self._primary_handlers: ty.Dict[type, HandlerRegistry.HandlerBase] = (
            {}
        )  # used before normal object pickling
        self._secondary_handlers: ty.Dict[type, HandlerRegistry.HandlerBase] = (
            {}
        )  # used after normal object pickling

        # handlers for all subclasses, used only if no normal handler is available
        self._primary_base_handlers: ty.Dict[type, HandlerRegistry.HandlerBase] = (
            {}
        )  # used before normal object pickling
        self._secondary_base_handlers: ty.Dict[type, HandlerRegistry.HandlerBase] = (
            {}
        )  # used after normal object pickling

    def _get_handler_dicts(
        self, primary_handler: bool = True
    ) -> ty.Tuple[ty.Dict[type, HandlerBase], ty.Dict[type, HandlerBase]]:
        if primary_handler:
            return self._primary_handlers, self._primary_base_handlers
        else:
            return self._secondary_handlers, self._secondary_base_handlers

    def get(
        self,
        cls_or_name: ty.Union[str, type],
        primary_handler: bool = True,
        default: ty.Optional[HandlerBase] = None,
    ) -> ty.Optional[HandlerBase]:
        if is_string(cls_or_name):
            # get class/type
            cls_or_name = module_class_name_to_class(cls_or_name)
        if not is_type(cls_or_name):
            raise TypeError(
                "The parameter 'cls_or_name' with value <{}> is not a class"
                " or the module and fully qualified class name.".format(cls_or_name)
            )

        # get normal handler and base handler dicts
        handlers, base_handlers = self._get_handler_dicts(primary_handler)

        # search for a normal handler
        handler: ty.Optional[HandlerRegistry.HandlerBase] = handlers.get(cls_or_name)

        if handler is None or not handler.can_handle(cls_or_name):
            # search for a base class handler
            for base_cls, base_handler in base_handlers.items():
                if issubclass(cls_or_name, base_cls) and base_handler.can_handle(
                    cls_or_name
                ):
                    return base_handler

        return default if handler is None else handler

    def register(
        self,
        cls_or_name: ty.Union[str, type],
        handler: ty.Optional[HandlerBase] = None,
        primary_handler: bool = True,
        as_normal: bool = True,
        as_base: bool = False,
    ) -> ty.Optional[ty.Callable[[HandlerBase], HandlerBase]]:
        if handler is None:
            # use as decorator for 'HandlerBase' class
            def wrapper(
                handler_cls: HandlerRegistry.HandlerBase,
            ) -> HandlerRegistry.HandlerBase:
                nonlocal cls_or_name, primary_handler, as_normal, as_base

                self.register(
                    cls_or_name,
                    handler=handler_cls,
                    primary_handler=primary_handler,
                    as_normal=as_normal,
                    as_base=as_base,
                )

                return handler_cls  # otherwise the class is lost

            return wrapper

        if is_string(cls_or_name):
            # get class/type
            cls_or_name = module_class_name_to_class(cls_or_name)
        if not is_type(cls_or_name):
            raise TypeError(
                "The parameter 'cls_or_name' with value <{}> is not a class"
                " or the module and fully qualified class name.".format(cls_or_name)
            )

        # get normal handler and base handler dicts
        handlers, base_handlers = self._get_handler_dicts(primary_handler)

        if as_normal:
            # use as normal handler
            handlers[cls_or_name] = handler

        if as_base:
            # use as handler for all subclasses
            base_handlers[cls_or_name] = handler

    def unregister(
        self, cls_or_name: ty.Union[str, type], primary_handler: bool = True
    ):
        if is_string(cls_or_name):
            # get class/type
            cls_or_name = module_class_name_to_class(cls_or_name)
        if not is_type(cls_or_name):
            raise TypeError(
                "The parameter 'cls_or_name' with value <{}> is not a class"
                " or the module and fully qualified class name.".format(cls_or_name)
            )

        # get normal handler and base handler dicts
        handlers, base_handlers = self._get_handler_dicts(primary_handler)

        handlers.pop(cls_or_name, None)
        base_handlers.pop(cls_or_name, None)


# static values of the module
handler_registry: HandlerRegistry = HandlerRegistry()


# flatten and encoding functions
class Flatten(object):
    """Convert Python objects to JSON-serializable format.

    This class handles flattening complex Python objects into simple types
    that can be serialized to JSON. It supports:

    * Circular references
    * Custom object handlers
    * Maximum recursion depth
    * Various reference types (bytes, modules, etc.)

    Parameters
    ----------
    max_depth : int, optional
        Maximum recursion depth, by default None (unlimited)
    json_backend : ModuleType, optional
        JSON module to use (e.g. json, ujson), by default None
    bytes_to_base64 : bool, optional
        Whether to encode bytes as base64, by default True
    use_bytes_references : bool, optional
        Whether to use references for bytes objects, by default True
    use_module_references : bool, optional
        Whether to use references for modules, by default True
    use_module_function_references : bool, optional
        Whether to use references for module functions, by default True
    use_set_references : bool, optional
        Whether to use references for sets, by default True
    use_string_references : bool, optional
        Whether to use references for strings, by default True
    use_tuple_references : bool, optional
        Whether to use references for tuples, by default True
    use_type_references : bool, optional
        Whether to use references for types, by default True
    replacement_names : dict, optional
        Mapping of old to new module/class names, by default None
    """

    def __init__(
        self,
        max_depth: ty.Optional[int] = None,
        json_backend: ty.Optional[types.ModuleType] = None,
        bytes_to_base64: bool = True,
        use_bytes_references: bool = True,
        use_module_references: bool = True,
        use_module_function_references: bool = True,
        use_set_references: bool = True,
        use_string_references: bool = True,
        use_tuple_references: bool = True,
        use_type_references: bool = True,
        replacement_names: ty.Optional[ty.Dict[str, str]] = None,
    ):
        # current recursive depth
        self._depth: int = 0

        # maximal recursive depth before stopping
        # Note: 'None' means never stop
        self.max_depth: ty.Optional[int] = max_depth

        # used to encode non-string dictionary keys
        self.json_backend: ty.Optional[types.ModuleType] = json_backend

        # encode byte strings with base64 as normal strings
        self.bytes_to_base64: bool = bytes_to_base64

        # remove duplicates of these objects/types using reference ids
        self.use_bytes_references: bool = use_bytes_references  # bytes
        self.use_module_references: bool = use_module_references  # module
        self.use_module_function_references: bool = (
            use_module_function_references  # module function
        )
        self.use_set_references: bool = use_set_references  # set
        self.use_string_references: bool = use_string_references  # string
        self.use_tuple_references: bool = use_tuple_references  # tuple
        self.use_type_references: bool = use_type_references  # class/type

        # replace the determined module/class name with this one
        # Note: Useful to hide the actual module structure or to handle later expected renaming/refactoring
        self.replacement_names: ty.Optional[ty.Dict[str, str]] = replacement_names

        # mapping between object id (memory address) and for the flattening used reference id
        self._obj_to_id: ty.Dict[ty.Any, int] = {}

        # holds a references of all object who are stored in '_obj_to_id' to prevent garbage collection
        # Note: Reused code from the 'Unflatten' class
        self._id_to_obj: ty.List[ty.Any] = []

        # holds the id of the current recursive call stack to detect reference cycles
        self._id_stack: ty.List[int] = []

    def _reset(self):
        self._depth: int = 0
        self._max_depth: int = -1
        self._obj_to_id: ty.Dict[ty.Any, int] = {}
        self._id_to_obj: ty.List[ty.Any] = []
        self._id_stack: ty.List[int] = []

    def _class_to_module_class_name(self, cls: ty.Type) -> str:
        return class_to_module_class_name(cls, self.replacement_names)

    def _flatten_bytes(self, obj: bytes) -> ty.Dict:
        if self.bytes_to_base64:
            # encode bytes to string
            obj: str = base64.b64encode(obj).decode("ascii")

        return {BYTES: obj}

    def _flatten_dict_object(self, obj: ty.Dict, data: ty.Dict) -> ty.Dict:
        for k, v in obj.items():
            if k in FlattenKeys:
                raise ValueError(
                    "The object <{}> has the key <{}>,"
                    " which is a reserved key word for the flattening.".format(obj, k)
                )

            if not isinstance(k, str) and self.json_backend:
                # transform to json string
                flatt_k: str = JSON_KEY + self.json_backend.dumps(self._flatten(k))
            else:
                # use directly as key
                flatt_k: ty.Any = k

            data[flatt_k] = self._flatten(v)

        return data

    def _flatten_dict(self, obj: ty.Dict) -> ty.Dict:
        return self._flatten_dict_object(obj, {})

    def _flatten_id(self, ref_id) -> ty.Dict:
        return {ID: ref_id}

    def _flatten_list_object(self, obj: ty.Iterable) -> ty.List:
        return [self._flatten(v) for v in obj]

    def _flatten_list(self, obj: ty.List) -> ty.List:
        return self._flatten_list_object(obj)

    def _flatten_module(self, obj: types.ModuleType) -> ty.Dict:
        return {MODULE: obj.__name__}

    def _flatten_module_function(self, obj: type) -> ty.Dict:
        return {MODULE_FUNCTION: self._class_to_module_class_name(obj)}

    def _flatten_slots_obj(self, obj: object, data: ty.Dict) -> ty.Dict:
        for base_cls in obj.__class__.__mro__:
            base_slots: ty.Union[ty.Tuple, str] = getattr(base_cls, "__slots__", ())

            if isinstance(base_slots, str):
                # single element
                base_slots: ty.Tuple = (base_slots,)

            for k in base_slots:
                if k.startswith("__"):
                    # name mangling
                    k: str = "_{}{}".format(obj.__class__.__name__, k)

                try:
                    value: ty.Any = getattr(obj, k)
                except AttributeError:
                    # no value available
                    continue

                if k not in data:
                    # flatten new value
                    data[k] = self._flatten(value)

        return data

    def _flatten_object(self, obj: object) -> ty.Dict:
        # find primary handler
        obj_cls: type = obj.__class__
        module_class_name: str = self._class_to_module_class_name(obj_cls)
        handler: ty.Optional[HandlerRegistry.HandlerBase] = handler_registry.get(
            obj_cls, primary_handler=True
        )

        if handler:
            # use handler
            data: ty.Dict = {OBJECT: module_class_name}
            return handler(self).flatten(obj, data)

        # no handler found
        has_dict: bool = hasattr(obj, "__dict__")
        has_slots: bool = hasattr(obj, "__slots__")

        # pickle methods
        has_getnewargs: bool = hasattr(obj, "__getnewargs__")
        has_getnewargs_ex: bool = hasattr(obj, "__getnewargs__")
        has_getstate: bool = has_attr_with_class_filter(
            obj, "__getstate__", True, [object]
        )
        has_reduce: bool = has_attr_with_class_filter(obj, "__reduce__", True, [object])
        has_reduce_ex: bool = has_attr_with_class_filter(
            obj, "__reduce_ex__", True, [object]
        )

        # if '__reduce__' or '__reduce_ex__' exist use it to flatten object
        reduce_val: ty.Optional[ty.Union[ty.Tuple, str]] = None

        if has_reduce_ex:
            # prefer over 'has_reduce'
            try:
                reduce_val = obj.__reduce_ex__(4)
            except TypeError:
                # likely a builtin method so ignore error
                pass
        elif has_reduce:
            try:
                reduce_val = obj.__reduce__()
            except TypeError:
                # likely a builtin method so ignore error
                pass

        if reduce_val:
            if is_string(reduce_val):
                # special case: string value describing the name of a global variable
                # return self._flatten(locate_and_load_module(reduce_val))
                raise NotImplementedError(
                    "The function '__reduce__' or '__reduce_ex__' returned <{}>, which is an unsupported case.".format(
                        reduce_val
                    )
                )
            else:
                # max 6 values as tuple
                rv_len: int = len(reduce_val)
                list_reduce_val: ty.List = [None] * 6
                list_reduce_val[0:rv_len] = reduce_val

                init_func, args, state, list_items, dict_items, setstate_func = (
                    list_reduce_val
                )

                if not (state and has_getstate):
                    if list_items:
                        # iterator to list
                        list_reduce_val[3] = list(list_items)
                    if dict_items:
                        # iterator to list with key value pairs (pairs as lists is more compact)
                        list_reduce_val[4] = [[k, v] for k, v in dict_items]

                    # flatten after removing unnecessary 'None' values
                    list_reduce_val_data = self._flatten(list_reduce_val[:rv_len])

                    return {REDUCE: list_reduce_val_data}

        # no reduce method available
        data: ty.Dict = {OBJECT: module_class_name}

        if has_getnewargs_ex:
            # prefer over '__getnewargs__'
            data[NEWARGS_EX] = self._flatten(list(obj.__getnewargs_ex__()))
        elif has_getnewargs:
            data[NEWARGS] = self._flatten(obj.__getnewargs__())

        # use '__getstate__' to flatten object
        if has_getstate:
            try:
                state: ty.Any = obj.__getstate__()

                data[STATE] = self._flatten(state)

                return data
            except TypeError:
                # likely a builtin method so ignore error
                pass

        # find secondary handler
        handler = handler_registry.get(obj_cls, primary_handler=False)

        if handler:
            # use handler
            return handler(self).flatten(obj, data)

        # no special methods available
        if has_dict:
            # '__dict__' object
            self._flatten_dict_object(obj.__dict__, data)
        if has_slots:
            # __slots__' object
            self._flatten_slots_obj(obj, data)

        # return normal flatten object
        return data

    def _flatten_primitive(self, obj: ty.Any) -> ty.Any:
        # nothing to do
        return obj

    def _flatten_set(self, obj: ty.Set) -> ty.Dict:
        return {SET: [self._flatten(v) for v in obj]}

    def _flatten_tuple(self, obj: ty.Tuple) -> ty.Dict:
        return {TUPLE: [self._flatten(v) for v in obj]}

    def _flatten_type(self, obj: type) -> ty.Dict:
        return {TYPE: self._class_to_module_class_name(obj)}

    def _get_flattener(self, obj: ty.Any) -> ty.Tuple[ty.Callable, bool, bool]:
        # easy cases
        if is_primitive(obj):
            # bool, None, int, float, str
            return (
                self._flatten_primitive,
                (isinstance(obj, str) and self.use_string_references),
                False,
            )
        elif is_bytes(obj):
            # bytes
            return self._flatten_bytes, self.use_bytes_references, False
        elif is_list(obj):
            # list
            return self._flatten_list, True, False
        elif is_dictionary(obj):
            # dictionary
            return self._flatten_dict, True, False
        elif is_set(obj):
            # set
            return self._flatten_set, self.use_set_references, True
        elif is_tuple(obj):
            # tuple
            return self._flatten_tuple, self.use_tuple_references, True
        # more complex cases
        elif is_module(obj):
            # module
            return self._flatten_module, self.use_module_references, False
        elif is_module_function(obj):
            # module functions
            return (
                self._flatten_module_function,
                self.use_module_function_references,
                False,
            )
        elif is_object(obj):
            # 'normal' object
            return self._flatten_object, True, False
        elif is_type(obj):
            # type
            return self._flatten_type, self.use_type_references, False

        # don't know what the object is or how to handle it
        raise TypeError("Objects like <{}> are currently not supported.".format(obj))

    def _flatten(self, obj: ty.Any) -> ty.Any:
        # increase depth
        self._depth += 1

        if self.max_depth and self._depth > self.max_depth:
            raise ValueError(
                "Reached max depth of <{}>, but the object is even deeper.".format(
                    self.max_depth
                )
            )

        # get flattener function
        _flatten_impl, use_reference, can_only_have_duplicates = self._get_flattener(
            obj
        )

        if use_reference:
            # check if the object is already known
            is_new, ref_id = make_object_reference(
                obj, self._obj_to_id, self._id_to_obj
            )

            if is_new or (can_only_have_duplicates and ref_id in self._id_stack):
                # new object or special to ignore cycle reference
                # add id to stack
                self._id_stack.append(ref_id)

                result = _flatten_impl(obj)

                # remove id from stack
                self._id_stack.pop()
            else:
                # return reference id of the known object
                result = self._flatten_id(ref_id)
        else:
            # do not use references
            # flatten object
            result = _flatten_impl(obj)

        # decrease depth
        self._depth -= 1

        return result

    def flatten(
        self,
        obj: ty.Any,
        pre_reset: bool = True,
        post_reset: bool = True,
        post_restore: bool = False,
    ) -> ty.Any:
        if post_restore:
            old_depth: int = self._depth
            old_max_depth: int = self.max_depth
            old_obj_to_id: ty.Dict[ty.Any, int] = self._obj_to_id
            old_id_to_obj: ty.List[ty.Any] = self._id_to_obj
            old_id_stack: ty.List[int] = self._id_stack

        if pre_reset:
            self._reset()

        data: ty.Any = self._flatten(obj)

        if post_restore:
            self._depth = old_depth
            self.max_depth = old_max_depth
            self._obj_to_id = old_obj_to_id
            self._id_to_obj = old_id_to_obj
            self._id_stack = old_id_stack
        elif post_reset:
            self._reset()

        return data


def flatten(
    obj: ty.Any,
    max_depth: ty.Optional[int] = None,
    json_backend: ty.Optional[types.ModuleType] = None,
    bytes_to_base64: bool = True,
    use_bytes_references: bool = True,
    use_module_references: bool = True,
    use_module_function_references: bool = True,
    use_set_references: bool = True,
    use_string_references: bool = True,
    use_tuple_references: bool = True,
    use_type_references: bool = True,
    replacement_names: ty.Optional[ty.Dict[str, str]] = None,
) -> ty.Any:

    context: Flatten = Flatten(
        max_depth=max_depth,
        json_backend=json_backend,
        bytes_to_base64=bytes_to_base64,
        use_bytes_references=use_bytes_references,
        use_module_references=use_module_references,
        use_module_function_references=use_module_function_references,
        use_set_references=use_set_references,
        use_string_references=use_string_references,
        use_tuple_references=use_tuple_references,
        use_type_references=use_type_references,
        replacement_names=replacement_names,
    )

    return context.flatten(
        obj=obj, pre_reset=True, post_reset=False, post_restore=False
    )


def encode(
    obj: ty.Any,
    max_depth: ty.Optional[int] = None,
    json_backend: ty.Optional[types.ModuleType] = None,
    bytes_to_base64: bool = True,
    use_bytes_references: bool = True,
    use_module_references: bool = True,
    use_module_function_references: bool = True,
    use_set_references: bool = True,
    use_string_references: bool = True,
    use_tuple_references: bool = True,
    use_type_references: bool = True,
    replacement_names: ty.Optional[ty.Dict[str, str]] = None,
    *args,
    **kwargs,
) -> str:
    """Encode a Python object to a JSON string.

    This is a convenience function that combines flattening an object and
    converting it to a JSON string.

    :param obj: The Python object to encode
    :type obj: Any
    :param max_depth: Maximum recursion depth
    :type max_depth: int, optional
    :param json_backend: JSON module to use
    :type json_backend: ModuleType, optional
    :param bytes_to_base64: Whether to encode bytes as base64
    :type bytes_to_base64: bool, optional
    :param use_bytes_references: Whether to use references for bytes
    :type use_bytes_references: bool, optional
    :param use_module_references: Whether to use references for modules
    :type use_module_references: bool, optional
    :param use_module_function_references: Whether to use references for module functions
    :type use_module_function_references: bool, optional
    :param use_set_references: Whether to use references for sets
    :type use_set_references: bool, optional
    :param use_string_references: Whether to use references for strings
    :type use_string_references: bool, optional
    :param use_tuple_references: Whether to use references for tuples
    :type use_tuple_references: bool, optional
    :param use_type_references: Whether to use references for types
    :type use_type_references: bool, optional
    :param replacement_names: Mapping of old to new module/class names
    :type replacement_names: dict, optional
    :param *args: Additional arguments passed to json.dumps
    :param **kwargs: Additional keyword arguments passed to json.dumps
    :return: JSON string representation of the object
    :rtype: str

    See Also
    --------
    * :func:`decode` : Convert JSON string back to Python object
    * :func:`flatten` : Convert object to JSON-serializable format
    """
    if json_backend is None:
        json_backend: types.ModuleType = get_json_backend()

    return json_backend.dumps(
        flatten(
            obj=obj,
            max_depth=max_depth,
            json_backend=json_backend,
            bytes_to_base64=bytes_to_base64,
            use_bytes_references=use_bytes_references,
            use_module_references=use_module_references,
            use_module_function_references=use_module_function_references,
            use_set_references=use_set_references,
            use_string_references=use_string_references,
            use_tuple_references=use_tuple_references,
            use_type_references=use_type_references,
            replacement_names=replacement_names,
        ),
        *args,
        **kwargs,
    )


# unflatten and decoding functions
class Unflatten(object):
    """Convert JSON-serializable format back to Python objects.

    This class handles unflattening simple JSON-serializable types back into
    complex Python objects.

    :param json_backend: JSON module to use (e.g. json, ujson)
    :type json_backend: ModuleType, optional
    :param bytes_to_base64: Whether bytes are base64 encoded
    :type bytes_to_base64: bool, optional
    :param use_bytes_references: Whether to handle bytes references
    :type use_bytes_references: bool, optional
    :param use_module_references: Whether to handle module references
    :type use_module_references: bool, optional
    :param use_module_function_references: Whether to handle module function references
    :type use_module_function_references: bool, optional
    :param use_set_references: Whether to handle set references
    :type use_set_references: bool, optional
    :param use_string_references: Whether to handle string references
    :type use_string_references: bool, optional
    :param use_tuple_references: Whether to handle tuple references
    :type use_tuple_references: bool, optional
    :param use_type_references: Whether to handle type references
    :type use_type_references: bool, optional
    :param replacement_names: Mapping of old to new module/class names
    :type replacement_names: dict, optional
    :param use_name_to_class_cache: Whether to cache loaded classes
    :type use_name_to_class_cache: bool, optional
    """

    def __init__(
        self,
        json_backend: ty.Optional[types.ModuleType] = None,
        bytes_to_base64: bool = True,
        use_bytes_references: bool = True,
        use_module_references: bool = True,
        use_module_function_references: bool = True,
        use_set_references: bool = True,
        use_string_references: bool = True,
        use_tuple_references: bool = True,
        use_type_references: bool = True,
        replacement_names: ty.Optional[ty.Dict[str, str]] = None,
        use_name_to_class_cache: bool = True,
    ):
        # used to encode non-string dictionary keys
        self.json_backend: ty.Optional[types.ModuleType] = json_backend

        # encode byte strings with base64 as normal strings
        self.bytes_to_base64: bool = bytes_to_base64

        # remove duplicates of these objects/types using reference ids
        self.use_bytes_references: bool = use_bytes_references  # bytes
        self.use_module_references: bool = use_module_references  # module
        self.use_module_function_references: bool = (
            use_module_function_references  # module function
        )
        self.use_set_references: bool = use_set_references  # set
        self.use_string_references: bool = use_string_references  # string
        self.use_tuple_references: bool = use_tuple_references  # tuple
        self.use_type_references: bool = use_type_references  # class/type

        # replace the determined module/class name with this one
        # Note: Useful to hide the actual module structure or to handle later expected renaming/refactoring
        self.replacement_names: ty.Optional[ty.Dict[str, str]] = replacement_names

        # cache of already loaded in class/modules
        self._name_to_class: ty.Optional[ty.Dict[str, str]] = (
            {} if use_name_to_class_cache else None
        )

        # bijective mapping between object id (memory address) and for the flattening used reference id
        self._obj_to_id: ty.Dict[ty.Any, int] = {}
        self._id_to_obj: ty.List[ty.Any] = []

        # all keys and attributes in objects with a placeholder
        self._placeholders: type_placeholders = {}

    def _reset(self):
        self._name_to_class: ty.Optional[ty.Dict[str, str]] = (
            None if self._name_to_class is None else {}
        )
        self._obj_to_id: ty.Dict[ty.Any, int] = {}
        self._id_to_obj: ty.List[ty.Any] = []
        self._placeholders: type_placeholders = {}

    def _module_class_name_to_class(
        self, module_class_name: str, is_module_only: bool = False
    ) -> type:
        if is_module_only:
            # only a module import, so it's pointless to try to split the path in module and non module part
            return module_class_name_to_class(
                module_class_name,
                self.replacement_names,
                self._name_to_class,
                module_class_seperator=None,
            )
        else:
            return module_class_name_to_class(
                module_class_name, self.replacement_names, self._name_to_class
            )

    def _make_object_reference(self, obj: ty.Any) -> ty.Tuple[bool, int]:
        return make_object_reference(obj, self._obj_to_id, self._id_to_obj)

    def _make_new_placeholder_reference(
        self,
    ) -> ty.Tuple[_PlaceholderObject, bool, int]:
        return make_new_placeholder_reference(self._obj_to_id, self._id_to_obj)

    def _set_and_swap_placeholder_with_object(
        self, placeholder: _PlaceholderObject, obj: ty.Any
    ) -> None:
        set_and_swap_placeholder_with_object(
            placeholder, obj, self._obj_to_id, self._id_to_obj, self._placeholders
        )

    def _try_add_value_placeholder_swap(
        self, obj: type_swap_obj, attr: ty.Any, value: ty.Any, set_func: type_set_func
    ) -> None:
        try_add_value_placeholder_swap(obj, attr, value, set_func, self._placeholders)

    def _unflatten_bytes(self, data: ty.Dict) -> bytes:
        obj: str = data[BYTES]

        if self.bytes_to_base64:
            # decode string to bytes
            obj: bytes = base64.b64decode(obj.encode("utf-8"))

        if self.use_bytes_references:
            self._make_object_reference(obj)

        return obj

    def _unflatten_dict_object(
        self, data: ty.Dict, obj: object, use_setattr: bool
    ) -> object:
        # unflatten 'normal' attributes
        for k, v in data.items():
            if k in FlattenKeys:
                # ignore special keys
                continue

            # unflatten key
            if k is not None and k.startswith(JSON_KEY):
                # contains JSON string
                key_data = self.json_backend.loads(k[len(JSON_KEY) :])
                k = self._unflatten(key_data)

            # unflatten value
            value = self._unflatten(v)

            if use_setattr:
                if k.startswith("__"):
                    # name mangling
                    k = "_{}{}".format(obj.__class__.__name__, k)

                setattr(obj, k, value)

                # 'value' could be a placeholder object
                self._try_add_value_placeholder_swap(
                    obj, k, value, _object_set_attr_with_placeholder
                )
            else:
                obj[k] = value

                # 'value' could be a placeholder object
                self._try_add_value_placeholder_swap(
                    obj, k, value, _object_set_value_with_placeholder
                )

        return obj

    def _unflatten_dict(self, data: ty.Dict) -> ty.Dict:
        obj: ty.Dict = {}
        self._make_object_reference(obj)

        return self._unflatten_dict_object(data, obj, False)

    def _unflatten_id(self, data: ty.Dict) -> ty.Any:
        return self._id_to_obj[data[ID]]

    def _unflatten_list_object(self, data, obj):
        # unflatten values
        if hasattr(obj, "extend"):
            # add items in one batch
            obj.extend(self._unflatten(v) for v in data)
        else:
            # add item one by one
            for v in data:
                obj.append(self._unflatten(v))

        # some values could be placeholder objects
        for i, e in enumerate(obj):
            self._try_add_value_placeholder_swap(
                obj, i, e, _object_set_value_with_placeholder
            )

        return obj

    def _unflatten_list(self, data: ty.List) -> ty.List:
        obj: ty.List = []
        self._make_object_reference(obj)

        return self._unflatten_list_object(data, obj)

    def _unflatten_module(self, data: ty.Dict) -> types.ModuleType:
        obj: types.ModuleType = self._module_class_name_to_class(
            data[MODULE], is_module_only=True
        )

        if self.use_module_references:
            self._make_object_reference(obj)

        return obj

    def _unflatten_module_function(self, data: ty.Dict) -> type:
        obj = self._module_class_name_to_class(data[MODULE_FUNCTION])

        if self.use_module_function_references:
            self._make_object_reference(obj)

        return obj

    def _unflatten_object(self, data: ty.Dict) -> object:
        module_class_name: str = data[OBJECT]
        obj_cls: type = self._module_class_name_to_class(module_class_name)

        # create temporary placeholder until the real object is available
        placeholder, _, _ = self._make_new_placeholder_reference()

        # find primary handler
        handler: ty.Optional[HandlerRegistry.HandlerBase] = handler_registry.get(
            obj_cls, primary_handler=True
        )

        if handler:
            # use handler
            obj = handler(self).unflatten(data, None)

            # replace placeholder with the real object
            self._set_and_swap_placeholder_with_object(placeholder, obj)

            return obj

        # no handler found
        # restore args and kwargs for '__new__'
        args: ty.List = []
        kwargs: ty.Dict = {}

        if NEWARGS_EX in data:
            # argument from '__getnewargs_ex__'
            args, kwargs = self._unflatten_list(data[NEWARGS_EX])
        elif NEWARGS in data:
            # argument from '__getnewargs__'
            args = self._unflatten(data[NEWARGS])

        # create initial object
        obj: object = obj_cls.__new__(obj_cls, *args, **kwargs)

        # replace placeholder with the real initial object
        self._set_and_swap_placeholder_with_object(placeholder, obj)

        # unflatten state
        if STATE in data:
            state = self._unflatten(data[STATE])
            if state != False:
                obj.__setstate__(state)

        # find secondary handler
        handler = handler_registry.get(obj_cls, primary_handler=False)

        if handler:
            # use handler
            return handler(self).unflatten(data, obj)

        # no special methods available
        return self._unflatten_dict_object(data, obj, True)

    def _unflatten_reduce(self, data: ty.Dict) -> object:
        # create temporary placeholder until the real object is available
        placeholder, _, _ = self._make_new_placeholder_reference()

        reduce_val: ty.List = self._unflatten_list(data[REDUCE])

        # max 6 values as tuple
        reduce_val.extend([None] * (6 - len(reduce_val)))

        init_func, args, state, list_items, dict_items, setstate_func = reduce_val

        # create initial object
        obj: object = init_func(*args)

        # replace placeholder with the real initial object
        self._set_and_swap_placeholder_with_object(placeholder, obj)

        # unflatten/restore state
        if state:
            if setstate_func:
                # higher priority as the '__setstate__' method
                setstate_func(obj, state)
            else:
                obj.__setstate__(state)

        if list_items:
            try:
                # add items in one batch
                obj.extend(list_items)
            except AttributeError:
                # add item one by one
                for v in list_items:
                    obj.append(v)

        if dict_items:
            for k, v in dict_items:
                obj[k] = v

        return obj

    def _unflatten_set(self, data: ty.Dict) -> ty.Set:
        if self.use_set_references:
            # create temporary placeholder until the real object is available
            placeholder, _, _ = self._make_new_placeholder_reference()

        # unflatten set
        obj: ty.Set = {self._unflatten(v) for v in data[SET]}

        if self.use_set_references:
            # replace placeholder with the real object
            self._set_and_swap_placeholder_with_object(placeholder, obj)

        return obj

    def _unflatten_tuple(self, data: ty.Dict) -> ty.Tuple:
        if self.use_tuple_references:
            # create temporary placeholder until the real object is available
            placeholder, _, _ = self._make_new_placeholder_reference()

        # unflatten tuple
        obj: ty.Tuple = tuple(self._unflatten(v) for v in data[TUPLE])

        if self.use_tuple_references:
            # replace placeholder with the real object
            self._set_and_swap_placeholder_with_object(placeholder, obj)

        return obj

    def _unflatten_type(self, data: ty.Dict) -> type:
        obj: type = self._module_class_name_to_class(data[TYPE])

        if self.use_type_references:
            self._make_object_reference(obj)

        return obj

    def _unflatten(self, data: ty.Any) -> ty.Any:
        # easy cases
        if is_primitive(data):
            # bool, None, int, float, str
            if self.use_string_references and is_string(data):
                self._make_object_reference(data)

            return data
        elif is_list(data):
            # list
            return self._unflatten_list(data)

        # complex cases
        elif is_dictionary(data):
            # flatten object
            if BYTES in data:
                # bytes
                return self._unflatten_bytes(data)
            elif ID in data:
                # return already unflatten object
                return self._unflatten_id(data)
            elif MODULE in data:
                # module
                return self._unflatten_module(data)
            elif MODULE_FUNCTION in data:
                # module function
                return self._unflatten_module_function(data)
            elif OBJECT in data:
                # object
                return self._unflatten_object(data)
            elif REDUCE in data:
                # '__reduce__' or '__reduce_ex__' method was available/used
                return self._unflatten_reduce(data)
            elif SET in data:
                # set
                return self._unflatten_set(data)
            elif TUPLE in data:
                # tuple
                return self._unflatten_tuple(data)
            elif TYPE in data:
                # type
                return self._unflatten_type(data)
            else:
                # no special flags found so a normal dict
                return self._unflatten_dict(data)
        else:
            raise TypeError("Data like <{}> are currently not supported.".format(data))

    def unflatten(
        self,
        data: ty.Any,
        pre_reset: bool = True,
        post_reset: bool = True,
        post_restore: bool = False,
    ) -> ty.Any:
        if post_restore:
            old_name_to_class: ty.Optional[ty.Dict[str, str]] = self._name_to_class
            old_obj_to_id: ty.Dict[ty.Any, int] = self._obj_to_id
            old_id_to_obj: ty.List[ty.Any] = self._id_to_obj
            old_placeholders: type_placeholders = self._placeholders

        if pre_reset:
            self._reset()

        obj: ty.Any = self._unflatten(data)

        if post_restore:
            self._name_to_class = old_name_to_class
            self._obj_to_id = old_obj_to_id
            self._id_to_obj = old_id_to_obj
            self._placeholders = old_placeholders
        elif post_reset:
            self._reset()

        return obj


def unflatten(
    data: ty.Any,
    json_backend: ty.Optional[types.ModuleType] = None,
    bytes_to_base64: bool = True,
    use_bytes_references: bool = True,
    use_module_references: bool = True,
    use_module_function_references: bool = True,
    use_set_references: bool = True,
    use_string_references: bool = True,
    use_tuple_references: bool = True,
    use_type_references: bool = True,
    replacement_names: ty.Optional[ty.Dict[str, str]] = None,
    use_name_to_class_cache: bool = True,
) -> ty.Any:

    context: Unflatten = Unflatten(
        json_backend=json_backend,
        bytes_to_base64=bytes_to_base64,
        use_bytes_references=use_bytes_references,
        use_module_references=use_module_references,
        use_module_function_references=use_module_function_references,
        use_set_references=use_set_references,
        use_string_references=use_string_references,
        use_tuple_references=use_tuple_references,
        use_type_references=use_type_references,
        replacement_names=replacement_names,
        use_name_to_class_cache=use_name_to_class_cache,
    )

    return context.unflatten(
        data=data, pre_reset=True, post_reset=False, post_restore=False
    )


def decode(
    data: str,
    json_backend: ty.Optional[types.ModuleType] = None,
    bytes_to_base64: bool = True,
    use_bytes_references: bool = True,
    use_module_references: bool = True,
    use_module_function_references: bool = True,
    use_set_references: bool = True,
    use_string_references: bool = True,
    use_tuple_references: bool = True,
    use_type_references: bool = True,
    replacement_names: ty.Optional[ty.Dict[str, str]] = None,
    use_name_to_class_cache: bool = True,
    *args,
    **kwargs,
) -> ty.Any:
    """Decode a JSON string back to a Python object.

    This is a convenience function that combines parsing a JSON string and
    unflattening it back into a Python object.

    :param data: The JSON string to decode
    :type data: str
    :param json_backend: JSON module to use
    :type json_backend: ModuleType, optional
    :param bytes_to_base64: Whether bytes are base64 encoded
    :type bytes_to_base64: bool, optional
    :param use_bytes_references: Whether to handle bytes references
    :type use_bytes_references: bool, optional
    :param use_module_references: Whether to handle module references
    :type use_module_references: bool, optional
    :param use_module_function_references: Whether to handle module function references
    :type use_module_function_references: bool, optional
    :param use_set_references: Whether to handle set references
    :type use_set_references: bool, optional
    :param use_string_references: Whether to handle string references
    :type use_string_references: bool, optional
    :param use_tuple_references: Whether to handle tuple references
    :type use_tuple_references: bool, optional
    :param use_type_references: Whether to handle type references
    :type use_type_references: bool, optional
    :param replacement_names: Mapping of old to new module/class names
    :type replacement_names: dict, optional
    :param use_name_to_class_cache: Whether to cache loaded classes
    :type use_name_to_class_cache: bool, optional
    :param *args: Additional arguments passed to json.loads
    :param **kwargs: Additional keyword arguments passed to json.loads
    :return: Reconstructed Python object
    :rtype: Any

    See Also
    --------
    * :func:`encode` : Convert Python object to JSON string
    * :func:`unflatten` : Convert JSON-serializable format back to object
    """
    if json_backend is None:
        json_backend: types.ModuleType = get_json_backend()

    return unflatten(
        data=json_backend.loads(data, *args, **kwargs),
        json_backend=json_backend,
        bytes_to_base64=bytes_to_base64,
        use_bytes_references=use_bytes_references,
        use_module_references=use_module_references,
        use_module_function_references=use_module_function_references,
        use_set_references=use_set_references,
        use_string_references=use_string_references,
        use_tuple_references=use_tuple_references,
        use_type_references=use_type_references,
        replacement_names=replacement_names,
        use_name_to_class_cache=use_name_to_class_cache,
    )


def deepcopy(
    obj: ty.Any,
    max_depth: ty.Optional[int] = None,
    json_backend: ty.Optional[types.ModuleType] = None,
    bytes_to_base64: bool = True,
    use_bytes_references: bool = True,
    use_module_references: bool = True,
    use_module_function_references: bool = True,
    use_set_references: bool = True,
    use_string_references: bool = True,
    use_tuple_references: bool = True,
    use_type_references: bool = True,
    use_name_to_class_cache: bool = True,
    *args,
    **kwargs,
) -> ty.Any:
    if json_backend is None:
        json_backend = get_json_backend()

    data: str = encode(
        obj,
        max_depth=max_depth,
        json_backend=json_backend,
        bytes_to_base64=bytes_to_base64,
        use_bytes_references=use_bytes_references,
        use_module_references=use_module_references,
        use_module_function_references=use_module_function_references,
        use_set_references=use_set_references,
        use_string_references=use_string_references,
        use_tuple_references=use_tuple_references,
        use_type_references=use_type_references,
        replacement_names=None,
        *args,
        **kwargs,
    )
    return decode(
        data,
        json_backend=json_backend,
        bytes_to_base64=bytes_to_base64,
        use_bytes_references=use_bytes_references,
        use_module_references=use_module_references,
        use_module_function_references=use_module_function_references,
        use_set_references=use_set_references,
        use_string_references=use_string_references,
        use_tuple_references=use_tuple_references,
        use_type_references=use_type_references,
        replacement_names=None,
        use_name_to_class_cache=use_name_to_class_cache,
        *args,
        **kwargs,
    )


# some predefined handlers
# handler for 'Iterator'
# Warning: Can handle only some easy cases and loops over all the iterator
from itertools import islice
from collections.abc import Iterator


class IteratorHandler(HandlerRegistry.HandlerBase):
    """Handler for serializing iterator objects.

    This handler can serialize simple iterator objects by converting them to lists.
    Only handles a limited number of elements defined by max_num_iter.

    :ivar max_num_iter: Maximum number of elements to serialize from iterator
    :type max_num_iter: int, optional
    """

    class DummyIterator(object):
        """Dummy class used as placeholder for iterator serialization."""

        pass

    # maximum number of elements that are flatten from an iterable/iterator object,
    # if no other means to flatten it are available.
    # Note: 'None' means infinite
    max_num_iter: ty.Optional[int] = None

    def flatten(self, obj: ty.Iterator, data: ty.Dict) -> ty.Dict:
        """Flatten an iterator to a dictionary format.

        :param obj: Iterator to flatten
        :type obj: Iterator
        :param data: Dictionary to store flattened data
        :type data: dict
        :return: Dictionary containing flattened iterator data
        :rtype: dict
        """
        # overwrite '<object>' value with dummy class, because 'types.GeneratorType' objects cannot be created directly
        data[OBJECT] = self.context._class_to_module_class_name(
            IteratorHandler.DummyIterator
        )

        # store iterator elements as list
        data["data"] = self.context._flatten(
            list(islice(iter(obj), IteratorHandler.max_num_iter))
        )
        return data

    def unflatten(self, data: ty.Dict, obj: ty.Optional) -> Iterator:
        """Unflatten a dictionary back into an iterator.

        :param data: Dictionary containing flattened data
        :type data: dict
        :param obj: Ignored for iterators
        :type obj: object, optional
        :return: Reconstructed iterator
        :rtype: Iterator
        """
        return self.context._unflatten_list(data["data"])


handler_registry.register(
    cls_or_name=Iterator,
    handler=IteratorHandler,
    primary_handler=False,
    as_normal=False,
    as_base=True,
)
handler_registry.register(
    cls_or_name=IteratorHandler.DummyIterator,
    handler=IteratorHandler,
    primary_handler=True,
    as_normal=True,
    as_base=False,
)


# handler for subclasses of 'dict'
# Warning: Can handle only some easy cases
class DictSubClassHandler(HandlerRegistry.HandlerBase):
    """Handler for serializing dictionary subclasses.

    This handler can serialize dictionary subclasses that have additional attributes
    beyond the standard dictionary content.
    """

    def flatten(self, obj: ty.Dict, data: ty.Dict) -> ty.Dict:
        """Flatten a dictionary subclass to a dictionary format.

        :param obj: Dictionary subclass to flatten
        :type obj: dict
        :param data: Dictionary to store flattened data
        :type data: dict
        :return: Dictionary containing flattened object data
        :rtype: dict
        """
        # dictionary contend
        dict_data: ty.Dict = {}
        self.context._flatten_dict_object(obj, dict_data)
        data["data"] = dict_data

        # additional attributes
        if hasattr(obj, "__dict__"):
            # '__dict__' object
            self.context._flatten_dict_object(obj.__dict__, data)
        if hasattr(obj, "__slots__"):
            # __slots__' object
            self.context._flatten_slots_obj(obj, data)

        return data

    def unflatten(self, data: ty.Dict, obj: ty.Optional[object]) -> ty.Dict:
        """Unflatten a dictionary back into a dictionary subclass.

        :param data: Dictionary containing flattened data
        :type data: dict
        :param obj: Dictionary subclass instance to unflatten into
        :type obj: object, optional
        :return: Reconstructed dictionary subclass
        :rtype: dict
        """
        # dictionary contend
        dict_data: ty.Dict = data.pop("data")
        self.context._unflatten_dict_object(dict_data, obj, False)

        # additional attributes
        self.context._unflatten_dict_object(data, obj, True)

        return obj


handler_registry.register(
    cls_or_name=dict,
    handler=DictSubClassHandler,
    primary_handler=False,
    as_normal=False,
    as_base=True,
)


# handler for subclasses of 'list'
# Warning: Can handle only some easy cases
class ListSubClassHandler(HandlerRegistry.HandlerBase):
    """Handler for serializing list subclasses.

    This handler can serialize list subclasses that have additional attributes
    beyond the standard list content.
    """

    def flatten(self, obj: ty.List, data: ty.Dict) -> ty.Dict:
        """Flatten a list subclass to a dictionary format.

        :param obj: List subclass to flatten
        :type obj: list
        :param data: Dictionary to store flattened data
        :type data: dict
        :return: Dictionary containing flattened object data
        :rtype: dict
        """
        # list contend
        data["data"] = self.context._flatten_list_object(obj)

        # additional attributes
        if hasattr(obj, "__dict__"):
            # '__dict__' object
            self.context._flatten_dict_object(obj.__dict__, data)
        if hasattr(obj, "__slots__"):
            # __slots__' object
            self.context._flatten_slots_obj(obj, data)

        return data

    def unflatten(self, data: ty.Dict, obj: ty.Optional[ty.List]) -> ty.List:
        """Unflatten a dictionary back into a list subclass.

        :param data: Dictionary containing flattened data
        :type data: dict
        :param obj: List subclass instance to unflatten into
        :type obj: list, optional
        :return: Reconstructed list subclass
        :rtype: list
        """
        # list contend
        list_data = data.pop("data")
        self.context._unflatten_list_object(list_data, obj)

        # additional attributes
        self.context._unflatten_dict_object(data, obj, True)

        return obj


handler_registry.register(
    cls_or_name=list,
    handler=ListSubClassHandler,
    primary_handler=False,
    as_normal=False,
    as_base=True,
)


# handler for numpy.ndarray
try:
    import numpy as np

    class NumpyHandler(HandlerRegistry.HandlerBase):
        """Handler for serializing NumPy arrays and scalars.

        This handler serializes NumPy arrays and scalar values using NumPy's
        save/load functionality.
        """

        def flatten(
            self, obj: ty.Union[np.ndarray, np.generic], data: ty.Dict
        ) -> ty.Dict:
            """Flatten a NumPy array/scalar to a dictionary format.

            :param obj: NumPy array or scalar to flatten
            :type obj: Union[np.ndarray, np.generic]
            :param data: Dictionary to store flattened data
            :type data: dict
            :return: Dictionary containing flattened array data
            :rtype: dict
            """
            mem_file: io.BytesIO = io.BytesIO()
            np.save(mem_file, obj)
            data_bytes: bytes = mem_file.getvalue()

            if self.context.bytes_to_base64:
                # encode bytes to string
                data_bytes: str = base64.b64encode(data_bytes).decode("ascii")

            data["data"] = data_bytes

            return data

        def unflatten(
            self, data: ty.Dict, obj: ty.Optional
        ) -> ty.Union[np.ndarray, np.generic]:
            """Unflatten a dictionary back into a NumPy array/scalar.

            :param data: Dictionary containing flattened data
            :type data: dict
            :param obj: Ignored for NumPy arrays
            :type obj: object, optional
            :return: Reconstructed NumPy array or scalar
            :rtype: Union[np.ndarray, np.generic]
            :raises ValueError: If data key is missing or None
            """
            data_bytes: ty.Optional[bytes] = data.get("data", None)

            if data_bytes is None:
                raise ValueError(
                    "Could not find key 'data' or its value is 'None' in object <{}>.".format(
                        data
                    )
                )

            if self.context.bytes_to_base64:
                # decode string to bytes
                data_bytes: str = base64.b64decode(data_bytes.encode("utf-8"))

            mem_file: io.BytesIO = io.BytesIO()
            mem_file.write(data_bytes)
            mem_file.seek(0)

            obj: ty.Union[np.ndarray, np.generic] = np.load(mem_file)

            if np.ndim(obj) == 0:
                # scalar in 0d array object
                obj = obj[()]

            return obj

    handler_registry.register(
        cls_or_name=np.ndarray,
        handler=NumpyHandler,
        primary_handler=True,
        as_normal=True,
        as_base=True,
    )
    handler_registry.register(
        cls_or_name=np.generic,
        handler=NumpyHandler,
        primary_handler=True,
        as_normal=True,
        as_base=True,
    )
except ImportError:
    pass


# handler open3d.geometry.PointCloud
try:
    import tempfile
    import open3d as o3d

    class Open3DPointCloudHandler(HandlerRegistry.HandlerBase):
        """Handler for serializing Open3D point clouds.

        This handler serializes Open3D point cloud objects using Open3D's
        read/write functionality with temporary files.
        """

        def flatten(self, obj: o3d.geometry.PointCloud, data: ty.Dict) -> ty.Dict:
            """Flatten an Open3D point cloud to a dictionary format.

            :param obj: Point cloud to flatten
            :type obj: o3d.geometry.PointCloud
            :param data: Dictionary to store flattened data
            :type data: dict
            :return: Dictionary containing flattened point cloud data
            :rtype: dict
            """
            # cannot use in mem file as open3d writer needs a 'real' file name
            temp_file = tempfile.NamedTemporaryFile(suffix=".pcd")

            o3d.io.write_point_cloud(temp_file.name, obj)
            data_bytes: bytes = temp_file.read()

            if self.context.bytes_to_base64:
                # encode bytes to string
                data_bytes: str = base64.b64encode(data_bytes).decode("ascii")

            data["data"] = data_bytes

            temp_file.close()

            return data

        def unflatten(self, data: ty.Dict, obj: ty.Optional) -> o3d.geometry.PointCloud:
            """Unflatten a dictionary back into an Open3D point cloud.

            :param data: Dictionary containing flattened data
            :type data: dict
            :param obj: Ignored for point clouds
            :type obj: object, optional
            :return: Reconstructed point cloud
            :rtype: o3d.geometry.PointCloud
            :raises ValueError: If data key is missing or None
            """
            data_bytes: ty.Optional[str] = data.get("data", None)

            if data_bytes is None:
                raise ValueError(
                    "Could not find key 'data' or its value is 'None' in object <{}>.".format(
                        data
                    )
                )

            if self.context.bytes_to_base64:
                # decode string to bytes
                data_bytes: bytes = base64.b64decode(data_bytes.encode("utf-8"))

            # cannot use in mem file as open3d reader needs a 'real' file name
            temp_file = tempfile.NamedTemporaryFile(suffix=".pcd")
            temp_file.write(data_bytes)
            temp_file.flush()

            obj: o3d.geometry.PointCloud = o3d.io.read_point_cloud(temp_file.name)

            temp_file.close()

            return obj

    handler_registry.register(
        cls_or_name=o3d.geometry.PointCloud,
        handler=Open3DPointCloudHandler,
        primary_handler=True,
        as_normal=True,
        as_base=True,
    )
except ImportError:
    pass
