# ── exceptions ──────────────────────────────────────────────────────
from krrood.patterns.code_generation.exceptions import (
    ActionApplyError,
    ActionError,
    ActionPreconditionError,
    ActionReverseError,
    ClassNotFoundError,
    CodeGenerationError,
    DelegationAnalysisError,
    FileWriteError,
    ImportResolutionError,
    InitMethodNotFoundError,
    InvalidCSTNodeError,
    InvalidSpecError,
    PlannerError,
    TypeNormalisationError,
)

# ── legacy (preserved for backward compatibility) ────────────────────
from krrood.patterns.code_generation.libcst_node_factory import LibCSTNodeFactory
from krrood.patterns.code_generation.type_normaliser import TypeNormaliser
from krrood.patterns.code_generation.import_name_resolver import ImportNameResolver
from krrood.patterns.code_generation.import_orchestrator import (
    GeneratedModuleImportOrchestrator,
)
from krrood.patterns.code_generation.generated_code_file_writer import (
    GeneratedCodeFileWriter,
)
from krrood.patterns.code_generation.delegation_generator import DelegationGenerator

# ── new modular architecture ─────────────────────────────────────────
from krrood.patterns.code_generation import (
    actions,
    analysis,
    planners,
    specs,
)
