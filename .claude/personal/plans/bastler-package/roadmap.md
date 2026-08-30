# bastler-package — Roadmap

Narrative companion to `plan.yaml`. Kept short on purpose: the size budget this split was made
under counts these lines.

## Where this plan came from

Split out of `workflow-unification` on 2026-08-30, under `plan-size-limits`'
`split-workflow-unification`. That plan had reached 59 items and 16,917 lines across its manifest
and roadmap, well past the 15-item / 2,000-line budget, and became seven plans seamed on subject.

This plan is the `bastler` track, carried across unchanged. Every item keeps its branch, pull
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

**13. The package is named `bastler`, and the migration goes first.** From the first letters of the
user's surname and the German word for a tinkerer; it supersedes `development_tooling`, and keeps
that name's abbreviation-free property. Decision 8 had sequenced the migration *last*, to avoid
moving files under in-flight pull requests; it moves to the front because the duplication carriers
accumulated faster than the review queue drained. The cost was measured rather than guessed - every
open tooling pull request but one touches Python this moves - and accepted: each merges main across
the move and re-applies its delta in the package.

**14. Derive rather than declare, and depend on krrood eventually.** What the package knows about
itself is computed from the directory and the modules rather than written down. And bastler is to
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
  `bastler-github-api-unification`, whose two remaining carriers live on other plans' branches.

## Process notes worth keeping

- **A green run after a deletion says nothing about what the deletion took with it.** Deleting a
  block by slicing from one anchor to the next also deleted a test sitting between them, and the
  suite stayed green. The check is the mutation that used to fail, or the test count. Seen twice in
  two days.
- **Grep for the claim, not for its expected callers.** Three module docstrings kept a justification
  a review round had already shown false, because nothing looked for the sentence.

## Open

- Whether the package is ever published, and whether agent-provider plugins ship with it. Left to
  their own item; the "never published" claim is deleted from the metadata rather than replaced.
- Two review threads on the extraction stay open on purpose, each answered differently from what it
  asked. Both are the user's to close.
