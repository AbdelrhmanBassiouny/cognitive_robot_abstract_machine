"""Object-oriented recognition layer for EQL-based Ripple Down Rules.

Recognizes domain views in a world by separating recall-oriented candidate
generation from precision-oriented, refinable definitions (hypothesise-and-test,
:cite:t:`erman1980hearsay`; Specification pattern, :cite:t:`evans2003domain`).
"""

from krrood.entity_query_language.rdr.recognition.candidate_generator import (
    CandidateGenerator,
)
from krrood.entity_query_language.rdr.recognition.definition import Definition
from krrood.entity_query_language.rdr.recognition.engine import RecognitionEngine
from krrood.entity_query_language.rdr.recognition.exceptions import (
    CyclicDefinitionDependency,
    RecognitionError,
    UnregisteredView,
)
from krrood.entity_query_language.rdr.recognition.registry import (
    DefinitionRegistry,
    RecognizableView,
)

__all__ = [
    "CandidateGenerator",
    "Definition",
    "DefinitionRegistry",
    "RecognizableView",
    "RecognitionEngine",
    "RecognitionError",
    "CyclicDefinitionDependency",
    "UnregisteredView",
]
