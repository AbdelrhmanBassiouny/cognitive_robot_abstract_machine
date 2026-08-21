"""
The workflow tooling for this repository - the Python behind the ``.claude/`` stack
tooling, plan dashboards and hook scripts, importable from the repository root with no
installation step.

The name is the German word for someone who builds things themselves, and shares its
first letters with the repository owner's surname.

..note:: This package is repository tooling, not part of the robot stack: it is never
    published and is not part of any default install. The ``pyproject.toml`` inside this
    directory exists only for optional installation, e.g. by a workflow running outside a
    checkout of the repository root.

..note:: The modules here span three dependency tiers, and the boundary is load-bearing
    rather than incidental: a hook may reach only what imports with no third-party module
    present at all, while the dashboard build imports jinja2, markdown and nh3 of its own.
    :mod:`bastler.plan_model` exists because the two tiers still have to agree on what a
    plan item's status means. ``test/bastler_test/test_package_contract.py`` holds the
    boundary to its stated shape.
"""
