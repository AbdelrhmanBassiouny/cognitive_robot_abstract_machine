from enum import StrEnum


class JSONField(StrEnum):
    """
    The keys a serialized object is written under in its JSON object.
    """

    TYPE = "__json_type__"
    """
    The fully qualified name of the class the object was serialized from.
    """

    IS_CLASS = "__is_class__"
    """
    Whether what was serialized is a class rather than an instance of one, which
    :attr:`TYPE` cannot tell apart because the type of a class is usually just ``type``.
    """

    COLLECTION_TYPE = "__collection_type__"
    """
    The fully qualified name of the class of a ``list``-like field, so that reading it
    restores that class instead of defaulting to ``list``.
    """

    ITEMS = "__items__"
    """
    The serialized items of a ``list``-like field.
    """

    KEYS = "keys"
    """
    The serialized keys of a ``dict`` field.
    """

    VALUES = "values"
    """
    The serialized values of a ``dict`` field, in the order of :attr:`KEYS`.
    """

    ATTRIBUTE_NAME = "attribute_name"
    """
    The name of the attribute a serialized diff describes.
    """

    ADDED_VALUES = "added_values"
    """
    The values a serialized diff appends to the attribute.
    """

    REMOVED_VALUES = "removed_values"
    """
    The values a serialized diff takes out of the attribute.
    """

    VALUE = "value"
    """
    The whole of an object that is written as a single value, such as a UUID or the
    message of an exception.
    """

    DAYS = "days"
    """
    The whole days of a duration.
    """

    SECONDS = "seconds"
    """
    The seconds of a duration beyond its whole days.
    """

    MICROSECONDS = "microseconds"
    """
    The microseconds of a duration beyond its whole seconds.
    """

    MEMBER_NAME = "name"
    """
    The name of the enum member that was serialized.
    """

    ELEMENT_TYPE = "type"
    """
    The type the elements of a numpy array share.
    """

    ELEMENTS = "data"
    """
    The elements of a numpy array, nested as deeply as the array has dimensions.
    """
