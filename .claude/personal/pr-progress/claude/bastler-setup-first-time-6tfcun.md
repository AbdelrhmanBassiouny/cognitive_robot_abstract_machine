
# First-time setup for the Bastler system (PR #203)

Plan item: workflow-unification / bastler-first-time-setup.

## Plan

Give a newcomer one short page and one command, and put the three steps no
script can perform - fork labels, Claude's access to the fork, the
CLAUDE_PERSONAL_NOTES_* variables - where they are read rather than in prose.

## Done

- .claude/SETUP.md (41 lines): /setup-personal-notes, setup_steps.py,
  check-setup.sh.
- .claude/hooks/setup_steps.py: SetupChecklist.for_clone prints the three steps
  filled in from the resolved notes remote; repository-specific steps dropped
  when no GitHub remote resolves; only non-default settings listed as variables.
- 20 tests, each mutation-checked. .claude suite 551, was 531.
- Both READMEs point at SETUP.md; hooks/README.md keeps the reference role.
- Committed, pushed, draft PR #203 opened off main. Manifest and roadmap
  (decision 14) saved to the notes branch.

## Review round 2026-08-28 (four threads, 3cc3a417)

- PersonalNotesSetting is an Enum mixing a frozen specification; needs both
  __new__ and __init__, unlike PullRequestField on main, whose defaulted
  fields hide the hazard. RepositoryLabel merges LabelPurpose + the dataclass
  + REQUIRED_LABELS into one StrEnum whose members line up with
  PullRequestLabel's, so the contract test holds names as well as values.
  git_value is one seam for the two subprocess calls. The labels step leads
  with the by-hand page and marks the gh commands conditional.
- GitCommandRunner declined with the measurement (a production sys.path
  insert #185 is deleting; no config/remote method); thread left open.
- 553 tests, from 551; six mutations checked. Manifest, roadmap and dashboard
  all updated in the same turn.

## Checked against the services, not the script (7114b3b4)

- Running the script and its tests only proves the script does what it says.
  Following the printed steps found: the docs URL named the cloud-sessions
  overview rather than cloud-environments#set-environment-variables, which is
  the page with the variable list; that list is .env format, where an unquoted
  value is read only as far as the first # (quoted_if_needed now quotes those);
  and the connector URL was the list rather than the GitHub authorization flow.
- Confirmed rather than corrected: merged/in-review/bug all exist on the fork
  under these names (checked through the API, not just PullRequestLabel), and
  gh is genuinely absent from a session container.
- 555 tests, from 553.

## Next

- Nothing outstanding in this session.
- After #107 lands: wire setup_steps.py into setup-personal-notes/SKILL.md's
  steps 4 and 8, which this PR left untouched to avoid conflicting with that
  rewrite.
- CI on #203 not read this session; the .claude/-only diff is covered by
  test_claude_dev_tooling, which passes locally at 553.

