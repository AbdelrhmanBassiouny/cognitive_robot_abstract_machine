"""Ripple-Down-Rules engine for the Entity Query Language."""

from krrood.entity_query_language.rdr.serialization import (
    load_rdr,
    rdr_to_python,
    save_rdr,
    save_rdr_with_case,
)
from krrood.entity_query_language.rdr.underspecified import (
    MultipleInferenceTargets,
    NoInferenceTarget,
    UnderspecifiedMatch,
    UnsupportedInferenceTarget,
    is_ellipsis_target,
)
