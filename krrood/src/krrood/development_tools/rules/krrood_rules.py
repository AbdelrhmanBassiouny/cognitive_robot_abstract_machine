"""
The rules for a repository built on krrood, one section per class.
"""

from __future__ import annotations

from pathlib import Path

from typing_extensions import Generic

import krrood
from krrood.adapters import json_serializer
from krrood.adapters.json_serializer import (
    DataclassJSONSerializer,
    SubclassJSONSerializer,
)
from krrood.development_tools.agent_rule import (
    CodeReference,
    KrroodRules,
    Subsection,
)
from krrood.exceptions import DataclassException
from krrood.ormatic.utils import classproperty
from krrood.patterns.generic_enumeration import GenericEnumeration
from krrood.patterns.path_enumeration import PathEnumeration
from krrood.patterns.subclass_safe_generic import SubClassSafeGeneric
from krrood.utils import get_generic_type_parameters


class Errors(Subsection[KrroodRules]):
    """
    The krrood rules on errors.
    """

    SUBCLASS_DATACLASS_EXCEPTION = (
        f"Custom exceptions subclass {CodeReference(DataclassException).path}, "
        f"implementing its {CodeReference(DataclassException.error_message).name} "
        f"and {CodeReference(DataclassException.suggest_correction).name}"
    )


class ConstantsAndClassLevelValues(Subsection[KrroodRules]):
    """
    The krrood rules on constants and class-level values.
    """

    USE_KRROOD_CLASSPROPERTY = (
        f"Use the {CodeReference(classproperty).name} {CodeReference(krrood).name} "
        "provides"
    )


class StructuredData(Subsection[KrroodRules]):
    """
    The krrood rules on structured data.
    """

    PATH_ENUMS_SUBCLASS_PATH_ENUMERATION = (
        f"A path enum subclasses {CodeReference(PathEnumeration).path}, so every "
        f"path derived from a member is a plain {CodeReference(Path).name}; its "
        "members' `name` is the path's last "
        "component, so read the member name as `_name_`"
    )

    SERIALIZE_JSON_WITH_KRROOD = (
        "JSON that our own classes round-trip goes through "
        f"{CodeReference(json_serializer).path}: use "
        f"{CodeReference(DataclassJSONSerializer).name} wherever it can "
        "(de)serialize the class; where a class needs more, subclass "
        f"{CodeReference(SubclassJSONSerializer).name} and build on "
        f"{CodeReference(DataclassJSONSerializer).name}'s "
        f"{CodeReference(DataclassJSONSerializer.to_json).name}/"
        f"{CodeReference(DataclassJSONSerializer.from_json).name}. Never hand-write "
        f"field-by-field {CodeReference(SubclassJSONSerializer.to_json).name}/"
        f"{CodeReference(SubclassJSONSerializer.from_json).name}"
    )


class TypeHints(Subsection[KrroodRules]):
    """
    The krrood rules on type hints.
    """

    SUBCLASS_SAFE_GENERICS = (
        f"Generic classes inherit {CodeReference(Generic).name} and then "
        f"{CodeReference(SubClassSafeGeneric).path}, which narrows field types "
        "when a subclass binds a parameter. Read a bound type with "
        f"{CodeReference(SubClassSafeGeneric.get_type_of_generic_parameter).name}, "
        "never via `__orig_bases__`. Such "
        "classes cannot be frozen dataclasses"
    )

    GENERIC_ENUMERATIONS = (
        f"A generic enum inherits {CodeReference(Generic).name} and then "
        f"{CodeReference(GenericEnumeration).path} instead of "
        f"{CodeReference(SubClassSafeGeneric).name}, whose metaclass conflicts with "
        "the enum's, so a subclass binds the parameter by subscripting it "
        "(`class MemberOfFamily(Family[ConcreteType])`) while subscripting with a "
        "member's name still looks the member up. Read a bound type with "
        f"{CodeReference(get_generic_type_parameters).path}"
    )
