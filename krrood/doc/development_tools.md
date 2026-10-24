# Development Tools

krrood ships the tools its own repository is developed with, so any Python repository
can use the same conventions:

- `krrood format FILE...` formats Python files with `ruff format`, then applies
  docformatter's docstring changes only where a second ruff pass leaves them unchanged.
  docformatter can disagree with ruff about the blank lines after an attribute docstring
  that precedes a decorated definition; for such a file ruff's output is kept, so the two
  tools never oscillate.
- `krrood agents-md [--rule-sets SET ...] [--check]` writes the repository's `AGENTS.md`:
  a generated-file notice, the rules of the chosen rule sets, then the repository's own
  `AGENTS.project.md` if it has one. With `--check` it writes nothing and exits non-zero
  when the committed `AGENTS.md` differs; run that in CI.

Both commands exit with 1 when they modified a file, following pre-commit's convention
for formatting hooks.

## Rule sets

The rules are grouped into rule sets, and `--rule-sets` chooses which ones `AGENTS.md`
contains (all of them by default):

- `python`: rules for any Python repository.
- `krrood`: conventions for a repository built on krrood, naming the krrood API each one
  uses (`DataclassException`, `classproperty`, `PathEnumeration`, the JSON serializer,
  `SubClassSafeGeneric`).

A repository that does not use krrood generates its file with `--rule-sets python`, in
its pre-commit hook and in its CI check alike.

## Installation

The formatting tools are an optional dependency, pinned so every repository formats
alike:

```bash
pip install "krrood[development-tools]"
```

## Use with pre-commit

pre-commit installs krrood into the hook's own environment:

```yaml
repos:
  - repo: local
    hooks:
      - id: krrood-format
        name: Format Python (ruff, then docformatter)
        entry: krrood format
        language: python
        additional_dependencies: ["krrood[development-tools]==<version>"]
        types: [python]
      - id: krrood-agents-md
        name: Generate AGENTS.md
        entry: krrood agents-md
        language: python
        additional_dependencies: ["krrood[development-tools]==<version>"]
        pass_filenames: false
        always_run: true
```

To use rules that are not released yet, replace the requirement with a commit of
cognitive_robot_abstract_machine:
`krrood[development-tools] @ git+https://github.com/cram2/cognitive_robot_abstract_machine@<commit>#subdirectory=krrood`.

The same hooks are published in the `.pre-commit-hooks.yaml` at the root of
[cognitive_robot_abstract_machine](https://github.com/cram2/cognitive_robot_abstract_machine).
They run the `krrood` command already installed in your development environment
(`language: system`), because pre-commit would otherwise install that whole repository
rather than krrood.

## Changing a rule

`AGENTS.md` is generated; never edit it by hand, and CI fails when it is stale.

- A rule for one repository only goes in that repository's `AGENTS.project.md`.
- A shared rule lives in `krrood/src/krrood/development_tools/rules/<rule set>/<section>.md`,
  one file per section of the rules. A rule that names krrood's API goes in the `krrood`
  rule set; every other rule goes in `python`. A new section is a new member of
  `RuleSection` in `krrood/src/krrood/development_tools/agent_instructions.py`, which
  sets the order the sections appear in.

Then run `krrood agents-md` (the pre-commit hook does this) and commit the regenerated
`AGENTS.md` with the change. A shared rule reaches other repositories with the next
krrood release.
