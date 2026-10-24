"""
The rules for this repository only, which ``krrood agents-md`` writes into ``AGENTS.md``
alongside the shared rules.
"""

from __future__ import annotations

from krrood.development_tools.agent_rule import (
    ProjectRule,
    RuleCatalogue,
    RuleSection,
    SectionHeading,
    SectionHeadings,
)

# %% sections


class CramSection(SectionHeadings):
    """
    The sections of this repository's own rules, listed after the shared sections.
    """

    PROJECT_RULES = SectionHeading("Project Rules", 1)
    GENERATED_ORM_INTERFACES = SectionHeading("Generated ORM Interfaces", 2)
    KRROOD_ISOLATION = SectionHeading("krrood Isolation", 2)
    DOMAIN_SPECIFIC_CONVENTIONS = SectionHeading("Domain-Specific Conventions", 2)


# %% rules


class CramRules(RuleCatalogue):
    """
    The rules for this repository only, one member per rule.
    """

    NEVER_EDIT_ORM_INTERFACES = ProjectRule(
        CramSection.GENERATED_ORM_INTERFACES,
        (
            "`ormatic_interface.py` files are generated, never written, and "
            "git-ignored (see `.gitignore`). Never edit them, and never read them to "
            "debug an ORM problem; regenerate them with "
            "`scripts/regenerate_all_orm.py` instead"
        ),
    )

    BUILD_ORM_INTERFACES_LOCALLY = ProjectRule(
        CramSection.GENERATED_ORM_INTERFACES,
        (
            "The test suite builds them for its runs; a local checkout builds them "
            "with `scripts/regenerate_all_orm.py`"
        ),
    )

    NEVER_TRACK_ORM_INTERFACES = ProjectRule(
        CramSection.GENERATED_ORM_INTERFACES,
        (
            "Never track one again: git refuses to overwrite a tracked path a checkout "
            "has generated its own copy of, which makes every branch switch fail"
        ),
    )

    ASK_ABOUT_PERSISTENT_ORM_PROBLEMS = ProjectRule(
        CramSection.GENERATED_ORM_INTERFACES,
        (
            "When regenerating the ORM interfaces does not fix an ORM problem, ask the "
            "developer"
        ),
    )

    ASK_ABOUT_ORM_IMPORT_CYCLES = ProjectRule(
        CramSection.GENERATED_ORM_INTERFACES,
        (
            "If an ORM import creates an import cycle, ask the user if a local import "
            "is fine"
        ),
    )

    NEVER_BUILD_ORM_INTERFACES_IN_TEST_RUNS = ProjectRule(
        RuleSection.RUNNING_TESTS,
        (
            "Pass `--orm-build never`, and regenerate the ORM interfaces explicitly "
            "with `scripts/regenerate_all_orm.py` when a change needs it"
        ),
    )

    KRROOD_IMPORTS_NO_WORKSPACE_PACKAGE = ProjectRule(
        CramSection.KRROOD_ISOLATION,
        (
            "`krrood`, including its tests under `test/krrood_test`, never imports "
            "another workspace package - in particular not `coraplex`, "
            "`semantic_digital_twin`, `giskardpy`, `physics_simulators`, `robokudo` or "
            "`experiments`. The only exceptions are `random_events` and "
            "`probabilistic_model`, which `krrood`'s source already depends on"
        ),
    )

    MIMIC_OTHER_PACKAGES_IN_KRROOD_TESTS = ProjectRule(
        CramSection.KRROOD_ISOLATION,
        (
            "When a `krrood` test needs behaviour another package triggers, mimic the "
            "relevant classes and patterns in `test/krrood_test/dataset` and test "
            "against the mimics. Keep the test in `krrood` and do not depend on "
            "another package to reproduce the scenario"
        ),
    )

    MIMICS_IMPORT_ONLY_KRROOD_DEPENDENCIES = ProjectRule(
        CramSection.KRROOD_ISOLATION,
        (
            "Those mimic classes import only `krrood`, `random_events` and "
            "`probabilistic_model`"
        ),
    )

    FOLLOW_THE_SPATIAL_STYLE_GUIDE = ProjectRule(
        CramSection.DOMAIN_SPECIFIC_CONVENTIONS,
        (
            "For spatial types and connections, follow "
            "`semantic_digital_twin/doc/style_guide.md`"
        ),
    )
