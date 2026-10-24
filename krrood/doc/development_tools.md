# Development Tools

krrood ships the tools its own repository is developed with, so any Python repository
can use the same conventions:

- `krrood format FILE...` formats Python files with `ruff format`, then applies
  docformatter's docstring changes only where a second ruff pass leaves them unchanged.
  docformatter can disagree with ruff about the blank lines after an attribute docstring
  that precedes a decorated definition; for such a file ruff's output is kept, so the two
  tools never oscillate.
- `krrood agents-md [--rule-sets SET ...] [--check]` keeps the block of shared rules in
  the repository's `AGENTS.md` equal to the rules of the chosen rule sets. It rewrites
  only what lies between the block's two marker lines and keeps the repository's own
  text around it; without an `AGENTS.md` it writes one holding just the block. With
  `--check` it writes nothing and exits non-zero when the block differs; run that in CI.

Both commands exit with 1 when they modified a file, following pre-commit's convention
for formatting hooks.

## Rule sets

The rules are grouped into rule sets, and `--rule-sets` chooses which ones the block
contains (all of them by default):

- `python`: rules for any Python repository.
- `krrood`: conventions for a repository built on krrood, naming the krrood API each one
  uses (`DataclassException`, `classproperty`, `PathEnumeration`, the JSON serializer,
  `SubClassSafeGeneric`).

A repository that does not use krrood generates its block with `--rule-sets python`, in
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
        name: Update the shared rules in AGENTS.md
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

- A rule for one repository only is written directly in that repository's `AGENTS.md`,
  anywhere outside the block of shared rules.
- A shared rule is never edited inside the block: the comment above it names the file it
  comes from, `krrood/development_tools/rules/<rule set>/<section>.md` (under
  `krrood/src` in cognitive_robot_abstract_machine), one file per section of the rules.
  A rule that names krrood's API goes in the `krrood` rule set; every other rule goes in
  `python`. A new section is a new member of `RuleSection` in
  `krrood/src/krrood/development_tools/agent_instructions.py`, which sets the order the
  sections appear in.

After changing a shared rule, run `krrood agents-md` (the pre-commit hook does this) and
commit the regenerated `AGENTS.md` with the change; CI fails when the block is stale or
was edited by hand. A shared rule reaches other repositories with the next krrood
release.

To adopt the block in an existing `AGENTS.md`, run `krrood agents-md`: it stops with an
error naming the two marker lines to add where the shared rules belong. Add them and run
it again.
