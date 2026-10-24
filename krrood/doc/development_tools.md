# Development Tools

krrood ships the tools its own repository is developed with, so any Python repository
can use the same conventions:

- `krrood format FILE...` formats Python files with `ruff format`, then applies
  docformatter's docstring changes only where a second ruff pass leaves them unchanged.
  docformatter can disagree with ruff about the blank lines after an attribute docstring
  that precedes a decorated definition; for such a file ruff's output is kept, so the two
  tools never oscillate.
- `krrood agents-md [--rule-sets SET ...] [--project-rules PATH] [--check]` keeps the
  block of rules in the repository's `AGENTS.md` equal to the rules of the chosen rule
  sets and the repository's own rules (see [Project rules](#project-rules)). It rewrites
  only what lies between the block's two marker lines and keeps the repository's own
  text around it. An `AGENTS.md` without the marker lines gets the block above its
  text, and without an `AGENTS.md` it writes one holding just the block. With
  `--check` it writes nothing and exits non-zero when the block differs; run that in CI.

Both commands exit with 1 when they modified a file, following pre-commit's convention
for formatting hooks.

## Rule sets

The rules are code: each rule is an `AgentRule` naming its section, its statement and
any details that spell it out. The rules are grouped into rule sets, and `--rule-sets`
chooses which ones the block contains (all of them by default):

- `python`: rules for any Python repository, the `PythonRule` members of `PythonRules`.
- `krrood`: conventions for a repository built on krrood, naming the krrood API each one
  uses (`DataclassException`, `classproperty`, `PathEnumeration`, the JSON serializer,
  `SubClassSafeGeneric`), the `KrroodRule` members of `KrroodRules`.

Each catalogue is an enum with one named member per rule, so the rules can be queried
from code, for example `PythonRules.rules_in(RuleSection.NAMING)`.

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
        name: Update the rules in AGENTS.md
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

## Project rules

A repository's own rules are code too. Declare them in `agent_rules.py` at the
repository root (`--project-rules PATH` names another module, relative to the root);
`krrood agents-md` reads every `RuleCatalogue` defined there and merges its rules into
the block:

```python
from krrood.development_tools.agent_rule import (
    ProjectRule,
    RuleCatalogue,
    RuleSection,
    SectionHeading,
    SectionHeadings,
)


class OwnSection(SectionHeadings):
    PROJECT_RULES = SectionHeading("Project Rules", 1)
    DEPLOYMENT = SectionHeading("Deployment", 2)


class OwnRules(RuleCatalogue):
    PIN_TEST_DEPENDENCIES = ProjectRule(
        RuleSection.RUNNING_TESTS, "Run tests against the pinned dependencies"
    )
    DEPLOY_FROM_TAGS = ProjectRule(OwnSection.DEPLOYMENT, "Deploy only tagged commits")
```

A project rule in a shared section, such as `RuleSection.RUNNING_TESTS`, is listed after
the shared rules of that section. Sections of the repository's own follow the shared
sections, in the order their `SectionHeadings` enum declares them. The module is
imported when the command runs, so it imports only krrood and the standard library.

## Changing a rule

Never edit a rule inside the block: the comment above each group of rules names the
catalogue and module it comes from. Find the member by the rule's text and change it
there.

- A repository's own rule is a `ProjectRule` in its `agent_rules.py`.
- A shared rule lives under `krrood/development_tools/rules/` (in `krrood/src` of
  cognitive_robot_abstract_machine). A rule that names krrood's API is a `KrroodRule`
  in `KrroodRules`; every other rule is a `PythonRule` in `PythonRules`. A new shared
  section is a new member of `RuleSection` in
  `krrood/src/krrood/development_tools/agent_rule.py`, which sets the order the sections
  appear in.

After changing a rule, run `krrood agents-md` (the pre-commit hook does this) and commit
the regenerated `AGENTS.md` with the change; CI fails when the block is stale or was
edited by hand. A shared rule reaches other repositories with the next krrood release.

Text that is not a rule, such as an introduction, may be written by hand in `AGENTS.md`
outside the block.

To adopt the block in an existing `AGENTS.md`, run `krrood agents-md`: it puts the block
above the file's text. Then move the rules of your own into `agent_rules.py` as
`ProjectRule` members and delete them from the text.
