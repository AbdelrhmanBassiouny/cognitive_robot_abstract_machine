# cram-development-tools

Development tooling for Python repositories, installed from PyPI instead of copied
between repositories:

- `cram-development-tools format FILE...` formats Python files with black, then applies
  docformatter's docstring changes only where a second black pass leaves them unchanged.
  docformatter can disagree with black about the blank lines after an attribute docstring
  that precedes a decorated definition; for such a file black's output is kept, so the
  two tools never oscillate.
- `cram-development-tools agents-md [--check]` writes the repository's `AGENTS.md`: a
  generated-file notice, the generic agent rules this package ships, then the
  repository's own `AGENTS.project.md` if it has one. With `--check` it writes nothing
  and exits non-zero when the committed `AGENTS.md` differs; run that in CI.

Both commands exit with 1 when they modified a file, following pre-commit's convention
for formatting hooks.

## Installation

```bash
pip install cram-development-tools
```

## Use with pre-commit

The simplest set-up needs no other repository: pre-commit installs the package into the
hook's own environment.

```yaml
repos:
  - repo: local
    hooks:
      - id: cram-development-tools-format
        name: Format Python (black, then docformatter)
        entry: cram-development-tools format
        language: python
        additional_dependencies: ["cram-development-tools==0.1.0"]
        types: [python]
      - id: cram-development-tools-agents-md
        name: Generate AGENTS.md
        entry: cram-development-tools agents-md
        language: python
        additional_dependencies: ["cram-development-tools==0.1.0"]
        pass_filenames: false
        always_run: true
```

The same hooks are published in the `.pre-commit-hooks.yaml` at the root of
[cognitive_robot_abstract_machine](https://github.com/cram2/cognitive_robot_abstract_machine).
They run the `cram-development-tools` command already installed in your development
environment (`language: system`), because pre-commit would otherwise install that whole
repository rather than this package:

```yaml
repos:
  - repo: https://github.com/cram2/cognitive_robot_abstract_machine
    rev: <commit on main>
    hooks:
      - id: cram-development-tools-format
      - id: cram-development-tools-agents-md
```

## Agent instructions

Write the rules that only apply to your repository in `AGENTS.project.md`, run
`cram-development-tools agents-md`, and commit the generated `AGENTS.md`. Never edit
`AGENTS.md` by hand; CI runs `cram-development-tools agents-md --check` to catch it.

## Releasing

The package has its own version, in `cram_development_tools/pyproject.toml`, independent
of the repository's `VERSION`, so a change to the tooling can be released without
releasing every other package. It is published the same way as the other packages:
`.github/workflows/cram-development-tools-publish-to-pypi.yml` runs on every push to
`main` that touches `cram_development_tools/`, and publishes with PyPI trusted publishing
whenever that version is not on PyPI yet.

One-time set-up: on PyPI, add a trusted publisher for the project
`cram-development-tools` with the repository's owner and name, the workflow
`cram-development-tools-publish-to-pypi.yml` and the environment `pypi` (for the first
release, as a pending publisher).

To release, raise `version` in `cram_development_tools/pyproject.toml`, together with the
`additional_dependencies` pins in this README, and merge the change into `main`.
