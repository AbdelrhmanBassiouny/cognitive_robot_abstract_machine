"""Ripple-Down-Rules engine for the Entity Query Language."""

from krrood.entity_query_language.rdr.underspecified import (
    MultipleInferenceTargets,
    NoInferenceTarget,
    UnderspecifiedMatch,
    UnsupportedInferenceTarget,
    is_ellipsis_target,
)
