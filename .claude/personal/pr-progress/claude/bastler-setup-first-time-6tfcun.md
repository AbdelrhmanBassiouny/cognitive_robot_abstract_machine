
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

## What step 2 grants, and who grants it (9bbaaf35)

- Asked whether any step gives Claude the right to manage pull requests, issues
  and pushes, the step could not answer: it said "give Claude access" and linked
  the flow, which is where a grant is made rather than what it covers. It names
  the three the grant carries now.
- The other half was wrong rather than thin: an organisation-owned fork is
  enabled by an organisation owner from the Claude admin settings, not by the
  personal connector flow every reader was being sent to.

## Fourth review round (240549f1)

- Two threads. Four https:// literals, three sharing claude.ai, so a host was
  spelled once per link. Host names each host once and composes its url;
  SetupLink composes the four destinations from it.
- The authorization line generalised from one case - what is per-account is the
  connector, and this fork is personal. It distinguishes the two paths by who
  owns the repository now. Thread left open with the trade stated: if the page
  is only ever for a Pro or Max account, the organisation line can go.
- 30 tests in test_setup_steps.py; 561 across the four CI directories, from 531
  before this branch. Three mutations checked.

## The artifact re-read cost, measured (recorded on plan-size-limits)

- Republishing a dashboard another session published requires reading the saved
  copy in full. workflow-unification's is 1.26 MB / 12,170 lines, so it is ~16
  chunked reads before a one-line change can land. 88% of the page is plan
  content - 62% the embedded roadmap, 26% item notes - so the cost is a function
  of plan size, and at plan-size-limits' 2,000-line budget the same page is ~163
  KB / ~1,579 lines, roughly 2 reads.
- No new PR and no new item: split-workflow-unification already fixes it. The
  republish cost is recorded there as a second argument for the budget.

## Next

- Nothing outstanding in this session. Description, manifest, roadmap and both
  dashboards (workflow-unification and plan-size-limits) are current.
- One thread open on purpose: the organisation-owned-fork line, waiting on
  whether this page is only ever for a Pro or Max account.
- After #107 lands: wire setup_steps.py into setup-personal-notes/SKILL.md's
  steps 4 and 8, which this PR left untouched to avoid conflicting with that
  rewrite.
- #203 is out of draft and stays that way while the user keeps directing work
  on it; mergeable_state unstable (mergeable, robotics CI still running).
  test_claude_dev_tooling's scope passes locally at 561.

