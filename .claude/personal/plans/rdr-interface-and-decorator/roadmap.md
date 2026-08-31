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

**3. Conformance at rebuild time buys less than it looked like.** These files
are new in their pull requests rather than pre-existing, so they are held to the
current `AGENTS.md` rules — `# %%` headers naming the behaviour, a docstring on
every function, method and field, no abbreviations — and doing that during the
rebuild is still right. What is *not* true is the claim this entry used to make,
that #76 therefore cost one review round instead of #79's two: #76 drew a
**fifty-thread** round twenty-five minutes after its rebuild landed. The rules a
rebuild can satisfy mechanically are the cheap half. The expensive half is the
design the reviewer reads for — primitives that should be classes, strings that
should be enum members, a 1,456-line test file — and no amount of pre-formatting
anticipates that.

**4. A fix scoped to what a thread asked, and no wider.** An abbreviation fix
cascades to every use site of *that* function's own local names, because leaving
three of seven abbreviated names in one function reads as arbitrary — but it is
not extended to identifiers elsewhere that no thread named. What is knowingly
left behind is recorded rather than silently skipped.

**5. A fix belongs in the slice that owns the name, even when the thread is
raised here.** Four of the review round's asks named identifiers this pull
request does not define: `case_table.py`'s `new_label` / `corner_label`
defaults and `rule_tree_view.py`'s `elision` vocabulary (#79 and #67
respectively), plus the generated-model header, which comes from
`templates/rdr_module.py.jinja` on the base. The available answer inside #76
was a second enum holding the same strings — a duplicate source of truth, which
is the very thing the asks exist to remove. So they were answered with where
the change belongs and left open, rather than satisfied locally. Hand-editing
one of three generated files was tried and reverted for the same reason: it
would have desynchronised that copy from its template and its two siblings.

**6. A session that reports itself finished is when to look again, not when to
stop.** #76's fifty-thread round opened at 14:34Z; the session that rebuilt the
branch had posted its completion note at 14:09Z and was gone. The item then
read healthy for the rest of the day while nothing on it was true. This is the
sixth instance of that class on this plan.

**7. A review round ends when the reviewer says so, not when the replies are
posted.** The 2026-08-30 round on #76 was recorded here as "five threads answered
and left open". The reviewer then read those five: three he resolved, accepting the
answers as given, and two he answered with instructions - the generated-model header
goes in the pull request that owns the template, and the side-by-side labels go in
#79. Both arrived at 21:55Z and 21:56Z, half an hour after the session that posted
the replies had stopped. Answering a thread is a turn in a conversation, and the
turn after it is the one that says what happens.

**8. A thread is resolved against the file, not against the intention.** #76's
`rdr/__init__.py` thread was resolved on the claim that the pull request no longer
touches the file. It still did: `format_docstrings.py` had reflowed the base's
one-line module docstring into three, so the file stayed in the diff doing exactly
what the reviewer asked it not to. The re-exports the thread was about were indeed
gone, which is what made the claim feel true.

**9. A formatter sweep puts untouched files back into the diff.** #76's
`rdr/__init__.py` was restored to the base and then reflowed by the PR-wide
`scripts/format_docstrings.py` pass, because docformatter expands the base's
one-line module docstring into three every time it runs over that file. The
sweep is what AGENTS.md asks for on modified files, so the rule is narrower
than it reads: it applies to the files a pull request actually changes, and a
file restored to the base is not one of them.

**10. A cross-plan ask is the developer's call, not the session's.** The
generated-model header belonged to #66, five branches down and in
`rdr-core-engine`. The resolve did the work it owned, replied with where the
rest belonged and what it would cost, and asked; the answer was to push it and
regenerate #76's copies. Asking cost one turn. Pushing to another plan's
in-flight pull request unasked would have cost that plan's manifest its record
of why its own diff had grown.

**11. The first slice to exercise a path is where the path's defects surface.**
`D-store` is the first code anywhere to write a generated `FunctionCase` to a
real file and import it back, and doing so turned up two defects that had
nothing to do with it. `function_case.py.jinja` opened an `if TYPE_CHECKING:`
block unconditionally and looped over `type_imports` inside it, so a function
annotated only with builtins produced a block with no body and a module that
would not parse. And `save_rdr_with_case` generated the case class against
`code_generation.function_case.FunctionCase` while the rdr layer checks
against its own duplicate, so a loaded case type was one the layer no longer
recognised, and saving it again dropped the class header. Neither was covered:
the generator's twenty-four tests all assert substrings of the source and none
of them ever parsed it.

**12. Decision 5 decides where a fix goes; it does not decide that the fix
waits.** The template belongs to `main`, so it is #226, a `bug` pull request of
its own with a test that compiles the generated source - and the same one-line
change is carried on `D-store` so the branch is verifiable now rather than
after a five-branch stack lands. It no-ops the moment #226 reaches the base.
The `base_class` line belongs to #66, which owns `serialization.py` and is open
and unmerged; the developer chose to fix it here and flag the ownership, since
the slice that first exercises the round trip is the one that can prove it. The
`FunctionCase` duplication underneath it - one class on `main`, a near-identical
one added by an unlanded rdr slice - is left alone, being neither slice's to
collapse.

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

- **`D-deco` has not been touched since the rebuilds.** It sits on `D-store`'s
  pre-rebuild history and needs the same reset treatment, dropping `cfe32ad0`
  rather than merging over it. `D-store` was reset on 2026-08-31 and is done.
- **`code_generation.imports.validate_annotations` raises on Python 3.10 and
  3.11.** `parameter_name in PythonBuiltinParameterNames` is a `StrEnum`
  value-containment check, which only works from 3.12; `krrood`'s
  `requires-python` says `>=3.10`. CI runs 3.12, so it is invisible there.
  Found while verifying `D-store`, recorded rather than fixed - it is `main`'s,
  and #226 is deliberately one root cause.
- **`D-ui-splice-fix`'s regression test can be re-added.**
  `TestAttributeReusedInEarlierSiblingBranch` needs no production change to pass
  against the fixed API once `test_eql_rdr/` lands; it asserts through the RDR
  layer, which is why #118 could only cover the same defect DSL-only.
- **Known conformance debt left alone deliberately** on #76: the
  `try`/`except`-around-attribute-access in `prompt_examples.pick_case_attribute`,
  and `namespace["quit"]` in `interactive.py`, which has no `NamespaceName`
  member the way `EXIT` does. Both are real rule instances that no thread named
  and that the PR-wide sweep thread's own categories (abbreviations, docstrings,
  formatting) do not cover.
- **#76 has no open review threads left.** `CaseColumnLabel` landed in #79 and
  both readers use it; the generated-model header changed in #66, the pull request
  that owns the template, with #76 bringing its three `fitted_models/` copies onto
  the new wording. The other three of the five left open the developer resolved
  himself, taking the answers as given.
- **The generated header is inconsistent on every branch between #66 and #76**
  until the stack restacks: those branches carry the template with the old line and,
  on #76, three generated modules with the new one. Regenerating a model there
  before #66 arrives puts the old header back.
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
