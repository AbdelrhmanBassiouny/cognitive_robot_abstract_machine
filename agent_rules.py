"""
The rules for this repository only, which ``krrood agents-md`` writes into ``AGENTS.md``
after the shared rule sets.
"""

from __future__ import annotations

from krrood.development_tools.agent_rule import AgentRule, ProjectRules


class RunningTests(ProjectRules):
    """
    The rules on running this repository's tests.
    """

    NEVER_BUILD_ORM_INTERFACES_IN_TEST_RUNS = AgentRule(
        (
            "Pass `--orm-build never`, and regenerate the ORM interfaces explicitly "
            "with `scripts/regenerate_all_orm.py` when a change needs it"
        ),
    )


class GeneratedORMInterfaces(ProjectRules):
    """
    The rules on the generated ORM interfaces.
    """

    NEVER_EDIT_ORM_INTERFACES = AgentRule(
        (
            "`ormatic_interface.py` files are generated, never written, and "
            "git-ignored (see `.gitignore`). Never edit them, and never read them to "
            "debug an ORM problem; regenerate them with "
            "`scripts/regenerate_all_orm.py` instead"
        ),
    )

    BUILD_ORM_INTERFACES_LOCALLY = AgentRule(
        (
            "The test suite builds them for its runs; a local checkout builds them "
            "with `scripts/regenerate_all_orm.py`"
        ),
    )

    NEVER_TRACK_ORM_INTERFACES = AgentRule(
        (
            "Never track one again: git refuses to overwrite a tracked path a checkout "
            "has generated its own copy of, which makes every branch switch fail"
        ),
    )

    ASK_ABOUT_PERSISTENT_ORM_PROBLEMS = AgentRule(
        (
            "When regenerating the ORM interfaces does not fix an ORM problem, ask the "
            "developer"
        ),
    )

    ASK_ABOUT_ORM_IMPORT_CYCLES = AgentRule(
        (
            "If an ORM import creates an import cycle, ask the user if a local import "
            "is fine"
        ),
    )


class KrroodIsolation(ProjectRules):
    """
    The rules keeping krrood independent of the other workspace packages.
    """

    KRROOD_IMPORTS_NO_WORKSPACE_PACKAGE = AgentRule(
        (
            "`krrood`, including its tests under `test/krrood_test`, never imports "
            "another workspace package - in particular not `coraplex`, "
            "`semantic_digital_twin`, `giskardpy`, `physics_simulators`, `robokudo` or "
            "`experiments`. The only exceptions are `random_events` and "
            "`probabilistic_model`, which `krrood`'s source already depends on"
        ),
    )

    MIMIC_OTHER_PACKAGES_IN_KRROOD_TESTS = AgentRule(
        (
            "When a `krrood` test needs behaviour another package triggers, mimic the "
            "relevant classes and patterns in `test/krrood_test/dataset` and test "
            "against the mimics. Keep the test in `krrood` and do not depend on "
            "another package to reproduce the scenario"
        ),
    )

    MIMICS_IMPORT_ONLY_KRROOD_DEPENDENCIES = AgentRule(
        (
            "Those mimic classes import only `krrood`, `random_events` and "
            "`probabilistic_model`"
        ),
    )


class DomainSpecificConventions(ProjectRules):
    """
    The rules pointing to the conventions of one domain.
    """

    FOLLOW_THE_SPATIAL_STYLE_GUIDE = AgentRule(
        (
            "For spatial types and connections, follow "
            "`semantic_digital_twin/doc/style_guide.md`"
        ),
    )
