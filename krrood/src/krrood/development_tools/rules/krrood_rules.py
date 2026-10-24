"""
The rules for a repository built on krrood.
"""

from __future__ import annotations

from krrood.development_tools.agent_rule import KrroodRule, RuleCatalogue, RuleSection


class KrroodRules(RuleCatalogue):
    """
    The rules for a repository built on krrood, one member per rule, each naming the
    krrood API it uses.
    """

    SUBCLASS_DATACLASS_EXCEPTION = KrroodRule(
        RuleSection.ERRORS,
        (
            "Custom exceptions subclass `krrood.exceptions.DataclassException`, "
            "implementing its `error_message` and `suggest_correction`"
        ),
    )

    USE_KRROOD_CLASSPROPERTY = KrroodRule(
        RuleSection.CONSTANTS_AND_CLASS_LEVEL_VALUES,
        "Use the `classproperty` `krrood` provides",
    )

    PATH_ENUMS_SUBCLASS_PATH_ENUMERATION = KrroodRule(
        RuleSection.STRUCTURED_DATA,
        (
            "A path enum subclasses "
            "`krrood.patterns.path_enumeration.PathEnumeration`, so every path derived "
            "from a member is a plain `Path`; its members' `name` is the path's last "
            "component, so read the member name as `_name_`"
        ),
    )

    SERIALIZE_JSON_WITH_KRROOD = KrroodRule(
        RuleSection.STRUCTURED_DATA,
        (
            "JSON that our own classes round-trip goes through "
            "`krrood.adapters.json_serializer`: use `DataclassJSONSerializer` wherever "
            "it can (de)serialize the class; where a class needs more, subclass "
            "`SubclassJSONSerializer` and build on "
            "`DataclassJSONSerializer.to_json`/`from_json`. Never hand-write "
            "field-by-field `to_json`/`from_json`"
        ),
    )

    SUBCLASS_SAFE_GENERICS = KrroodRule(
        RuleSection.TYPE_HINTS,
        (
            "Generic classes inherit `Generic[...]` and then "
            "`krrood.patterns.subclass_safe_generic.SubClassSafeGeneric`, which "
            "narrows field types when a subclass binds a parameter. Read a bound type "
            "with `get_type_of_generic_parameter`, never via `__orig_bases__`. Such "
            "classes cannot be frozen dataclasses"
        ),
    )
