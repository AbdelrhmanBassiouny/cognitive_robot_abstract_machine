# basstler-package — Roadmap

Narrative companion to `plan.yaml`. Kept short on purpose: the size budget this split was made
under counts these lines.

## Where this plan came from

Split out of `workflow-unification` on 2026-08-30, under `plan-size-limits`'
`split-workflow-unification`. That plan had reached 59 items and 16,917 lines across its manifest
and roadmap, well past the 15-item / 2,000-line budget, and became seven plans seamed on subject.

This plan is the `basstler` track, carried across unchanged. Every item keeps its branch, pull
request number, status and session verbatim. **The full predecessor roadmap remains in the
personal-notes branch's history**; what is kept here is what binds future work.

## Why this work exists

Three directories under `.claude/` - `hooks/`, `stack/` and `skills/plan-dashboard/` - are separate
`sys.path` roots, so nothing in one can import another. The consequence is not stylistic: the same
code was written out repeatedly because there was no shared home to put it in, and each duplication
was recorded on the item that found it rather than fixed.

The carriers on record when the migration was moved to the front:

- A `run_git`-style subprocess seam three times, plus `stack.py`'s deliberately-opposite `_git`.
- The frozen-dataclass command-class base twice, where making them identical would have meant
  copying a fifth file in answer to a complaint about duplication.
- `ItemStatus`, and the personal-notes precedence rules' second Python copy.
- The gh-CLI-else-token GitHub backend rule three times, which keeps its own item.

## Decisions this plan inherits

Numbering is the predecessor's, kept so cross-references in item notes still resolve.

**8. A proper package, with boundaries.** All Python under `.claude/` moves into one package with
its tests under the standard `test/` directory. What stays in `.claude/`: `SKILL.md` files,
`settings.json` and the bash entry points, since Claude Code discovers them by path - they become
thin wrappers invoking `python -m`. Zero-install must survive: the package is a plain top-level
directory importable from the repository root, with a `pyproject` for *optional* installation. It
stays visibly dev-tooling - its own directory, not published, not in the default install.

**12. The bash layer retires into the package.** About 1,300 lines across nine hook scripts and the
dashboard refresh move in. The permanent bash remainder is roughly eight three-line shims at the
existing paths, a slimmed configuration file, and the environment-configuration script unchanged,
since it is pasted by reference into cloud environment setup fields this repository cannot update.
`settings.json` stays byte-identical. The Python floor is 3.11.

**13. The package is named `basstler`, and the migration goes first.** From the first letters of the
user's surname and the German word for a tinkerer; it supersedes `development_tooling`, and keeps
that name's abbreviation-free property. Decision 8 had sequenced the migration *last*, to avoid
moving files under in-flight pull requests; it moves to the front because the duplication carriers
accumulated faster than the review queue drained. The cost was measured rather than guessed - every
open tooling pull request but one touches Python this moves - and accepted: each merges main across
the move and re-applies its delta in the package.

**14. Derive rather than declare, and depend on krrood eventually.** What the package knows about
itself is computed from the directory and the modules rather than written down. And basstler is to
depend on `krrood`, to cut duplication rather than mirror its idioms - which makes decision 12's
version-1 independence a stage rather than a permanent state.

## The dependency-tier reversal, which later items should not re-derive

Three successive shapes existed to protect callers that run before anything is installed: a declared
tier table, a set of modules that may need the requirements, and an import closure derived from the
callers themselves. All three are gone. The user's answer is that **nothing should run before an
install**: the session-start hook installs whatever declared dependency is missing on every start,
gated on the notes-branch fetch the hook already exits on, reporting a failure on its own summary
line and finishing the run regardless; Actions runners install the package themselves.

The two installers diverge on purpose, and the zero-install contract is why: a session installs the
missing *specifiers*, because installing the package would leave a second copy of these modules
beside the clone's own and the clone's copy is what a caller imports; a runner has no such contract.
Dependencies are declared statically in `pyproject`, matching what main did for every other
workspace member, and the package stays out of the workspace members list, since membership would
put it in the default sync.

## Landing hazards

- **Whichever lands second rebases.** The migration moves files nearly every open tooling pull
  request touches. A pull request already through review may instead land just before the
  migration's final merge, which folds it in on the migration side - cheaper, and the user decides
  per pull request at merge time.
- **The conversion items must follow the in-flight bash-touching pull requests**, not lead them: a
  wholesale body rewrite cannot be merged by the whichever-lands-second convention.
- **Two carriers are unreachable from the migration branch** and stay with
  `basstler-github-api-unification`, whose two remaining carriers live on other plans' branches.

## Process notes worth keeping

- **A green run after a deletion says nothing about what the deletion took with it.** Deleting a
  block by slicing from one anchor to the next also deleted a test sitting between them, and the
  suite stayed green. The check is the mutation that used to fail, or the test count. Seen twice in
  two days.
- **Grep for the claim, not for its expected callers.** Three module docstrings kept a justification
  a review round had already shown false, because nothing looked for the sentence.

## What actually stalled the extraction, found 2026-09-03

The manifest called `basstler-package` in progress and still a draft. Both were wrong, and the second
one is what hid the first: **#185 has been out of draft since 2026-08-23**, which in this workflow is
the promotion approval rather than a loose end, and it has carried `needs-resolution` since
2026-08-22, which withholds a branch from promotion. So the work was finished and approved, and held
at the last step for twelve days by a conflict nothing in the plan recorded.

The conflict is one file and one kind: `.claude/hooks/tests/test_setup_steps.py` was added on `main`
inside a directory this branch renamed, so git reports `CONFLICT (file location)` and declines to
place it. Its silent half is the one this plan's own process note already warns about twice:
`.claude/hooks/setup_steps.py` merges with **no conflict at all**, because this branch moved
`.claude/hooks/*.py` file by file rather than renaming that directory - and left where it lands it
breaks the branch's own "no `.py` remains under `.claude/`" contract. Third occurrence. The check is
still `git ls-tree -r origin/main --name-only .claude/ | grep '\.py$'` against the merged tree, and
nothing runs it automatically.

Both were resolved the same day at `674f1507f`. The named conflict took the new suite at its renamed
location; the unnamed one took `setup_steps.py` into the package, where its hand-counted `.parent`
chain became `package_layout.REPOSITORY_ROOT` and its suite lost all three shapes this package exists
to end at once - a bare module import, a bare sibling import, and a `sys.path.insert` reaching the
plan-dashboard directory for `build_dashboard.PullRequestLabel`. 664 tests pass, against 632.

`basstler-first-time-setup` landing is what produced both files: upstream #577, merged into `main` at
`017be2aa2` on 2026-09-01, while the manifest carried it as `in_progress`. This is the
whichever-lands-second convention working exactly as the landing hazards section says it does.

Two tooling defects turned up alongside, and neither belongs to this plan:

- The maintenance routine's own comment promises that "later passes skip it rather than re-reporting
  the same conflict". It re-reported 20 times between 2026-08-31 and 2026-09-03, roughly every two
  hours. The label suppresses promotion but evidently not the report.
- `plan-item-resolve/SKILL.md` instructs a session to record its findings with
  `plan_item_bootstrap update` and to follow `${MANIFEST_STALENESS_DOCUMENT}`. Neither exists - the
  script has only `record` and `open`, and no `manifest-staleness.md` is on any branch. The findings
  here were written by editing `plan.yaml` directly instead.

## Open

- Whether the package is ever published, and whether agent-provider plugins ship with it. Left to
  their own item; the "never published" claim is deleted from the metadata rather than replaced.
- Two review threads on the extraction stay open on purpose, each answered differently from what it
  asked. Both are the user's to close.

## What stalled it again, found 2026-09-30

`integration-conflict` has withheld #185 since 2026-09-19. Its two comments blame `D-store`, then
`D-ui`. Both are krrood branches that share no file with this one, and neither is the cause.

**#185 is red on its own under the suite the published pipeline runs.** `integration-refresh.yml`
runs from the `integration` branch and reads `integration_test_command` from that branch's own
`.claude/stack/stack.toml`. That command still names `.claude/skills/plan-dashboard/tests`,
`.claude/hooks/tests` and `.claude/stack/tests`, and this branch moves all three to
`test/basstler_test/`. Run on #185's head, pytest exits 4 with `file or directory not found`. The
branch's own suite passes 665/665.

**Why an innocent tip was named.** The narrowing round pairs the suspect with each earlier tip, but
it never tries the suspect alone on the base. A tip that is red by itself fails every pairing, so
the most recent earlier tip gets the blame. The triage skill does say to confirm each branch passes
alone, but the automatic label and comment are written before anyone runs that check. This is a
`red-candidate-localisation` (#211) defect, not this plan's.

**It is a deadlock, not a collision.** The pipeline takes its suite from the last build it
published, and a build carrying #185 cannot publish while that suite names the pre-move paths.
#154 and #211 are stacked on #185 and already set
`python3 -m pytest test/basstler_test --confcutdir=test/basstler_test`, but they can only reach
`integration` behind #185. Removing the label on its own gets it re-applied by the next build. The
label also kept the branch out of the maintenance pass, including its `main` merges, so the branch
had fallen 113 commits behind. That merge was clean and 665 tests still pass.

Two ways out, and both belong to the pipeline: have `build` read the suite from the tree under test
rather than from the tooling running it, or dispatch one refresh on a reference that already carries
the new command. The second is what the workflow's own comment gives a dispatch for.

**A tooling defect met while recording this.** `plan_item_bootstrap update --append-notes` rewrote
this item's literal-block (`|-`) note as a folded scalar, with a blank line after every hard-wrapped
line, so one appended paragraph turned the note into 57. The manifest was repaired by hand and saved
with `save-plan.sh`.

**Resolution, same day.** `main` was merged at `0c7ff268f`. The user chose the personal override:
`.claude/personal/stack.toml` on the notes branch now sets `integration_test_command` to the
command #154 and #211 commit. Loaded through the published `.claude/stack/stack.py`, it resolves
to that value. `integration-conflict` was removed from #185. The override is temporary, so delete
it once a build carrying #154 or #211 has published. The localisation defect is not recorded on
`stack-maintenance`'s manifest yet.

**What the resolution missed at first: the upstream review.** `/upstream-reviews` was skipped
because #185 carries `cram2-link-sent`, not `in-review`. When it did run, it showed the real
stall behind the integration one: #185 is cram2#659, where LucaKro requested changes on
2026-09-21 and nine threads are still unresolved. They cover global constants in `dependencies.py`,
`plan_item_mode.py` and `package_layout.py`, moving helpers onto `Dependency`, a StrEnum in
`sync_version.py` and why basstler is not a proper package, a version check, and an `__init__`
comment. This is the case `always-read-upstream-reviews` records: the label does not tell you
whether an upstream pull request exists.

## The src-layout follow-up, decided 2026-09-30

cram2#659 asked why basstler is not a proper package like the others. The honest answer has
changed since decision 8. The session-start hook now installs on every start, and an editable
install leaves no second copy, so both premises that ruled out a `src` layout are gone. The user
chose to keep #185 flat and do the move as `basstler-src-layout` straight after it. Doing it inside
#185 would re-move about 40 files in a PR whose readability depends on its rename diff, would shift
the lines nine open upstream threads point at, and would make every stacked branch merge across a
second move. #154, #211 and #430 are deliberately *not* made to depend on it: the move is cheap to
redo, while crossing it is not. The one hazard worth a test is the silent case: a module added
directly under `basstler/` merges cleanly into the old location.

## 2026-10-01 - cram2#659 second round (tomsch420)

tomsch420 requested changes on the new head with eight threads, mostly "scattered constants".
The user had already agreed in replies to: path enums for `plan_item_mode.py`'s `Directory` and
`Location`, grouping the scattered path constants, discovering packages in `sync_version.py`
rather than listing them, and removing the conftest's `sys.path` insert. They also suggested an
AGENTS.md rule for enum value types. All are in `1f6b3c585`.

- **`Directory(Path, Enum)` does not work, so the ask was answered differently.** Python 3.11
  cannot subclass `Path`; on 3.12+ every derived path (`member / "x"`) goes through the enum's
  member lookup and raises. `basstler/locations.py` therefore holds plain enums whose values are
  `Path`s, with `__fspath__`, `__str__` and `__truediv__`, so a member works wherever a path
  does. The AGENTS.md rule records the trap.
- **The dependency regexes went further than asked.** `importlib.metadata.distributions(name=)`
  already compares names per PEP 503, so the separator regex, `canonical_name` and the cached
  installed set are deleted. The cache was also a latent defect: anything installed after its
  first read stayed invisible to the process, which the new spelling test exposed. One regex
  (the PEP 508 name boundary) remains, because `packaging` cannot be imported by a module that
  runs before anything is installed.
- **`sync_version.py`** follows setuptools' own resolution (named `package-dir`, then the `""`
  mapping, then `packages.find.where`, then beside the `pyproject.toml`), applied to the module
  each version attribute names. That needs no special case for basstler and skips segmind, whose
  version is set in its `__init__`.
- **The `sys.path` insert was already redundant**: `test/` is a package, so pytest's default
  import mode puts the repository root on `sys.path` itself.
- Dropped along the way: the second `GITHUB_API_ROOT`, and `HookScript.PLAN_ITEM_BOOTSTRAP`,
  which named the pre-move `.claude/hooks/` path and had no reader.

## 2026-10-01 - fork review of the second round

The user reviewed `1f6b3c585` on #185 with three threads. `.claude` was spelled in every
`ProjectLocation` member, so it became one member, `CLAUDE_CODE_DIRECTORY`, and the test suites
build their `.claude` paths from it too (`a83cca79c`, `96146eb45`). The test `constants.py` lost
`__all__`, which nothing star-imported, and every loose constant: dataset paths, skill
directories, notes-branch paths, branches and environment prefixes are enums now, reusing
`ProjectLocation` and `PackageLocation` where the package already names the thing. The third
thread asked why `PathEnumeration` exists rather than `class X(Path, Enum)`. Tested again: the
mixin fails on 3.11, and on 3.12+ needs `with_segments`, `__hash__` and `ReprEnum` overrides and
still shadows the enum's `name`. It stays open for the user, and becomes a one-file change if
basstler moves to `>=3.12`.


## 2026-10-01 - the 3.12 bump goes to basstler-src-layout

The user asked to make basstler `>=3.12` so `PathEnumeration` could become `class
PathEnumeration(Path, ReprEnum)`, unless that hurt cloud sessions. It does: the cloud container's
`python3` is 3.11.15, the only interpreter with basstler's dependencies, and every module imports
`locations.py`, so a 3.12-only class would break every session start. The container's 3.12 is an
externally managed system interpreter with none of the dependencies. The user chose to fold the
bump into `basstler-src-layout`, whose editable install now also creates basstler's own 3.12+
environment for the hooks to run, with the mixin as a one-file follow-on.

## 2026-10-02 - cram2#659 third round (tomsch420)

The fork side looked finished, but `/upstream-reviews` showed two new threads from that morning.
Nothing on the fork recorded them.

- **`dependencies.py:83`, "why are these constants?" / "fields".** `Dependency.CONSTRAINT_START`
  became the field `constraint_start`, with no repr and no comparison.
- **`plan_model.py:56`, drop the `_` from the values so `display_label` is not needed.** The user
  had agreed on the thread. The values are also the stored `status:` spelling in every manifest (125
  entries on the notes branch), the `--status` argument and the card's CSS class. So this is a
  format migration, not a rename. Asked, the user chose to change the values and migrate. The
  underscore spelling is still read, through `_missing_` and `ItemStatus.accepted_spellings()`. The
  CSS class comes from the member name. `sync_manifest_status`'s one-word status-line pattern was
  widened, after a test with a spaced value showed it failing. All in `be0ed435f`.

**Landing hazard, recorded rather than avoided.** This branch writes `in progress` and `main`'s
tooling only reads `in_progress`. Until #185 lands, a manifest written by this branch's code, or by
the stacked #154, #211 and #430, fails a `main`-based dashboard build. After it lands, rewrite the
notes-branch manifests to the new spelling, then drop `_missing_` and `accepted_spellings`.

## 2026-10-02 - cram2#659 fourth round (LucaKro), and one Repository

LucaKro requested changes at 11:12, before `be0ed435f` was pushed, with three new threads and one
reply.

- **"Use logging"** (`dependencies.py:172`, `setup_steps.py:618`). Both lines are their command's
  stdout data. The user chose to route everything through logging anyway, so all 67 prints now go
  through module loggers under the `basstler` package logger. Its one handler,
  `basstler/standard_streams.py`'s `StandardStreamHandler`, writes bare messages to stdout at
  information level and to stderr from a warning up, so every output contract is byte for byte the
  same. Two things only showed up when running the code. The handler has to look the stream up when
  it writes, or captured streams miss the output. And a module run with `python -m` is named
  `__main__`, so its logger fell outside the package logger and 41 tests saw empty stdout until its
  import name was read from its spec. In `4cdd39318`.
- **"And no classvar"** on the fields thread was already met by `be0ed435f`.
- **"Dataclass exception gaming"** (`dependencies.py:54`). The repo-wide idiom is krrood's
  `DataclassException`, and basstler has 35 exception classes of its own. The user answered it
  upstream as "in the coming PRs, one step at a time" and resolved it, so it now belongs to
  `basstler-notes-core-python`'s `errors.py`. Decision 14 says basstler depends on krrood
  eventually, but no item schedules that, so whether `errors.py` mirrors the idiom or imports it is
  decided in that item.

**One `Repository`** (the user, same day, `c61a734d9`). `stack.py` and `setup_steps.py` each had one,
and they read remote URLs by different rules. `basstler/repository.py` keeps `stack.py`'s rule (any
host, last two segments, raises when no repository is named), since it is the one that reads a cloud
session's proxy remote. `setup_steps`'s "another host names no repository" rule moved into
`resolve_repository`, where it decides.


## 2026-10-02 - #420 and #424 join the plan, stacked on #185

The user asked how #420 fits with basstler and chose to track both it and #424 here. #185 moves
`.claude/upstream_reviews/` into `basstler/`, and #420 changes nothing outside that directory, its
query and its skill. So under "whichever lands second rebases" the work falls to #420, since #185
lands first.

The adaptation was done by stacking rather than waiting, the same way #154, #211 and #430 sit on
#185. #185's branch was merged into #420 at `2d53a88e7`, and #420's base moved to
`claude/plan-item-kickoff-workflow-cuare2`. Its diff against that base is still its own eight files.
The maintenance pass moves the base back to `main` once #185 lands. #420 must not be promoted before
then: its compare link names `main`, and on cram2 it would conflict with cram2#659.

The user had marked #420 ready, which normally ends a session's work on it. They allowed the push
explicitly, so #420 stays ready rather than going back to draft.

#424 is stacked on #420 and has not been updated. A trial merge gave seven conflicts, recorded on
its item. Most of them come from #185 having merged the two `gh` stubs into one, and having given
the module's suite its own CI job.

## 2026-10-02 evening - fork review of the logging round

The user asked on #185 for `StandardStreamHandler` to be a dataclass, and for the new tests to stop
repeating their strings. Both are in `105de6379`. The handler is `@dataclass(eq=False)`: with no
fields, a generated `__eq__` would make every instance equal and drop its hash, which `logging`
needs to tell handlers apart. The same "name it once" fix went into `test_repository.py`. A
second pass asked for no module-level constants in `standard_streams.py` (`37e8cf887`): the format is
a handler field, the package logger is named by `__package__`, and a module's import name is always
read from its spec, which makes the `__main__` comparison unnecessary. Upstream,
cram2#659 has one unresolved thread left, "fields / and no classvar", which `be0ed435f` meets.

## 2026-10-04 - #424 carried across, and #420 restacked

The user allowed the push to #424 as well. #185 had moved on to `37e8cf887` since #420 was stacked,
so #420 merged it first, cleanly, at `a6d7b29c1`. #424 then merged #420 at `2d4a15148`. All seven
conflicts were the ones the trial merge predicted.

One more file went silently, of the kind this plan's process notes warn about: #424 had added
`UPSTREAM_REVIEWS_*` path constants to `resolve-personal-notes-config.sh`. They merged without a
conflict, named the directory #185 deletes, and had nothing left reading them. A conflict report
does not find these. Grepping for the old path in the merged tree does.

Both branches stay ready, since the user had flipped them and then approved the pushes. Nothing is
left to do on either until #185 lands. Then the maintenance pass moves #420's base back to `main`,
and both get new promotion links.

## 2026-10-04 - #107 stacked on #185

The user restacked `setup-personal-notes-script` (#107, tracked in `stack-tooling-install`) onto
this branch, since #185 lands first and moves every Python file #107 touches. Merged at `6e712cec`.
Two of #185's test definitions changed in the process, which matters to anything else merging
across #185. `HookScript` moved from `plan_item_bootstrap.py` into `locations.py` and grew to
cover every shell entry point. `StackLabel` became `RepositoryLabel`, the same members plus
`MERGED` and `PROMOTION_LINK_SENT`. #107 also brings `github-api.sh`, one of the two carriers
`basstler-github-api-unification` unifies, so that carrier now arrives on a branch stacked on
the package.

## 2026-10-04 - #107 rebuilt on the package

#107 was rebuilt in basstler's shape on top of #185 (`57480ed4`). Three changes reach #185's own
modules. `maintenance_github.GitHubRepository` now holds a `GitHubConnection` instead of a bare
token. That connection resolves GH_TOKEN, then GITHUB_TOKEN, then `gh auth token`, and has
gained label and login calls. `RepositoryLabel` moved out of `setup_steps.py` into its own
module and grew to the six labels the tooling applies. `stack.py`'s label defaults and
`PROMOTION_LINK_LABEL` read it. `basstler-github-api-unification` therefore loses
`github-api.sh` as a carrier, and its backend question is answered for the package client.

## 2026-10-09 - basstler-src-layout kicked off (#501)

#185 merged into the fork's `main` on 2026-10-05, so this item is based on `main` rather than stacked. The manifest still had #185 as `in progress`, and the dashboard refresh's status sync corrects that. Kicked off in `auto` mode, which is the committed default.

The item's three open design points, decided here and flagged on #501 for review:

- **When the install fails.** `BASSTLER_PYTHON` falls back to `python3`, with `basstler/src` on `PYTHONPATH`. That works wherever `python3` is 3.12+ and has the dependencies, CI included. Elsewhere the `dependencies:` summary line has already reported the failure.
- **Bare `python -m basstler.*` commands in the docs.** Each one sources the configuration and calls `"${BASSTLER_PYTHON}"`.
- **Finding a 3.12+ interpreter.** `uv venv --python '>=3.12'` is preferred, since it can fetch an interpreter. Otherwise the first `python3.1x` found by name, so no shell carries embedded Python again.

The premise has moved since 2026-10-01: this container's `python3` is now 3.13.16, with 3.11, 3.12 and `uv` 0.11 also present. The environment is still needed, because a 3.11 default is common elsewhere.

The `PathEnumeration(Path, ReprEnum)` mixin was prototyped before the move. With the `with_segments` and `__hash__` overrides it works on 3.12 and 3.13, and fails on 3.11 with `AttributeError: _flavour`, as recorded.

## 2026-10-09 - basstler-src-layout implemented on #501

The work is done in four commits and waits on review. 745 tests pass on 3.12 and 3.13, against 710 on `main`. Live in a clone, the first session start created `basstler/.venv` with `uv` and installed the package into it; the second installed nothing.

Decisions made along the way that a later item should not re-derive:

- **The installer is `pip --python <environment> install --editable ./basstler`.** Environments are created without pip, either by `uv venv` or by `python3.1x -m venv --without-pip`. So one pip, the one on `PATH`, installs into any of them, and Debian's missing `ensurepip` does not matter.
- **`basstler.dependencies` counts the package itself as a requirement.** An environment whose install failed is reinstalled on the next start, rather than reading as complete because its dependencies happen to be there.
- **`PYTHONPATH=basstler/src` is exported by the configuration**, alongside the editable install. That keeps a worktree or a scratch clone on its own copy, and lets `python3` stand in until the environment exists.
- **`member.name` on a path enumeration is now the file name.** Use `_name_` for the member's name. AGENTS.md says so.

Two defects the tests turned up: `check-setup.sh` and `save-plan.sh` both read an unparseable `pyproject.toml` as "nothing missing". Both are fixed on #501.

Recorded rather than fixed: a `pytest -n` race on the real `board.json`, already on `main` and xdist-only, and `add-plan-item/SKILL.md`'s undefined `${PLAN_ITEM_BOOTSTRAP_SCRIPT}`.

Landing: #420, #424, #430, #437 and #107 each merge across this second move. The new contract test fails on any module left directly under `basstler/`.
