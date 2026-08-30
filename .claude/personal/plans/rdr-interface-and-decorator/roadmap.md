# The interactive expert interface and the @rdr decorator — Roadmap

Narrative half of `rdr-interface-and-decorator`. One of seven plans the
oversized `rdr-refactor` was split into on 2026-08-30; the predecessor's full
3,259-line roadmap remains in the personal-notes branch's history immediately
before that split commit.

## What is being built

The parts a user of the engine touches, in two stacked chains on top of the
core engine's tip:

- **`D-ui-rendering` (#79) → `D-ui` (#76)** — case-table rendering and
  serialization coverage, then the interactive layer itself: the IPython shell,
  its magics, the conftest fixture and the user guides.
- **`D-store` (#80) → `D-deco` (#77)** — `RDRFileStore`, which has no decorator
  dependency and is self-tested, then the `@rdr` decorator, its template and its
  documentation.

`D-ui-splice-fix` (#78) is here as the closed predecessor of the first chain,
kept because its branch is what let the other two be rebuilt.

## Why this is separate from the core engine

The `rdr/` package delivery stack is one linear chain of fourteen slices, which
is over the size budget on its own. The seam is the one the programme's own
tracks already drew: the engine core is a library, and these five slices are the
shell, the magics, the decorator and the file store a person interacts with. The
cost is stated rather than hidden — `D-ui-rendering` and `D-ui-splice-fix` stack
directly on `d-core-backend` (#210) in `rdr-core-engine`, and `depends_on`
cannot name an item in another plan, so those two edges are recorded as
`blockers` and carry no dependency chip or automatic readiness.

## Decisions that still bind

**1. Restack these branches by reset, never by merge.** Both #79 and #76 sat on
a base that led nowhere and still carried #78's `cfe32ad0`, which reintroduces
`SymbolicExpression._last_parent_of_type_` — a symbol main deleted, and a
structural-accessor read `dag-facade-hardening`'s guard test forbids. A merge
keeps an addition the other side never deleted, so the rejected fix would have
ridden into review. Both were rebuilt as the new base plus the slice's own
files; pre-rebuild tips are recorded on each item.

**2. The interactive layer absorbs the `ExpertInterface` segregation.** The
engine keeps `NullProgressReporter`, which is the only default correct for a
caller that knows nothing about its context; the interactive default belongs
here, in the layer that knows there is a shell to draw on. So attaching an RDR
to an `IPythonInterface` installs `IPythonProgressBar` on it unless the caller
chose a reporter of their own, and `%save` persists through `rdr.model_saver`
rather than `interface.on_save`. An unused `progress_reporter()` method was the
first shape tried and was the same mistake the segregation diagnosed: a member
that exists so something *could* ask, on a class nothing asks. The wiring
belongs where the two objects meet.

**3. Conformance is done at rebuild time, not at review time.** #79 converted
its dividers when rebuilt and then spent a whole review round on docstrings;
#76 did both in one pass and cost one round instead of two. These files are new
in their pull requests rather than pre-existing, so they are held to the current
`AGENTS.md` rules — `# %%` headers naming the behaviour, a docstring on every
function, method and field, no abbreviations.

**4. A fix scoped to what a thread asked, and no wider.** An abbreviation fix
cascades to every use site of *that* function's own local names, because leaving
three of seven abbreviated names in one function reads as arbitrary — but it is
not extended to identifiers elsewhere that no thread named. What is knowingly
left behind is recorded rather than silently skipped.

## The lesson this plan is the case study for

**Six weeks on a dead base costs three moved interfaces, and none of it is
visible while the branch cannot be built.** When #79 was finally rebuilt, the
suite showed 28 failures across two modules, every one the stack having moved
under a branch that could not follow: a spy holding tuples where the stack now
has dataclasses, a renamed keyword argument, the `...` sentinel, and — the one
that was not a port — two test classes pinning a contract that had been
*deliberately reversed*, asserting that a fit saves once per rule when it now
saves once on its way out. Their replacement already existed on the base, so
they were dropped rather than rewritten.

Two defects the interface change had left behind were each invisible to a
passing suite:

- The `%conclusion`/`%conditions` magics had stopped rejecting invalid answers.
  `validate()` returns a list of exceptions now; the magic still asked
  `if target_name in errors`, always false on a list, so an invalid answer
  exited the shell instead of re-prompting. Its four tests passed throughout,
  because their `validate` double still returned the old mapping — a double
  that had drifted from the contract it stands in for can only confirm the
  drift. Bringing it onto the real contract is what produced the failing test.
- The shipped user guide failed when CI executed it. `test_eql_documentation.sh`
  runs every guide as a notebook, so a guide is a CI job rather than prose, and
  it still called an argument the API had renamed. Found by running the script,
  not by reading the file.

## Open

- **`D-store` and `D-deco` have not been touched since the rebuilds.** Both sit
  on `D-ui`'s pre-rebuild history and need the same reset treatment, dropping
  `cfe32ad0` rather than merging over it.
- **`D-ui-splice-fix`'s regression test can be re-added.**
  `TestAttributeReusedInEarlierSiblingBranch` needs no production change to pass
  against the fixed API once `test_eql_rdr/` lands; it asserts through the RDR
  layer, which is why #118 could only cover the same defect DSL-only.
- **Known conformance debt left alone deliberately** on #79: `av`, `sp`, `d` and
  `test_progress_bar.py`'s own box-drawing dividers are real instances of rules
  this pull request's other fixes enforced elsewhere, but no thread named them.
  Also on #79, `TestIPythonProgressBar`'s later methods annotate
  `mock_tqdm: pytest.MagicMock`, which does not exist — harmless only because
  `from __future__ import annotations` keeps the annotation a string.

## Standing conventions

- Follow `.claude/personal/cram-notes.md` and this repository's `AGENTS.md`.
- SOLID is a review gate: a new capability enters as an abstraction plus small
  dataclass implementations, and strategies stay substitutable without touching
  the engine.
- TDD: failing test first, and no test is modified to make something pass.
- `krrood` stays self-contained; world-like scenarios are mimicked in
  `test/krrood_test/dataset`.
- The programme's working method — run the probe rather than reasoning, compare
  sorted collected test ids rather than counts, stage by explicit path — is
  recorded in `rdr-core-engine`'s roadmap and applies here unchanged.
