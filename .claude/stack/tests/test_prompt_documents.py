"""
Contract tests for the prompt documents the live cloud Routine runs on.

``ROUTINE.md`` is read from git and executed at the start of every run; ``POINTER.md``
is the prompt registered with the Routine that resolves it. Three things are pinned.
First, the base-change rule: a pull request's base branch can only be changed through
the GitHub MCP server, since the same request issued through the session git proxy is
refused. Second, each document's shape, because the Routine locates what to execute by
the fenced block rather than by reading the whole file. Third, that the rules duplicated
into the pointer stay identical to the routine document's.

All three are prose rather than code, so nothing else would catch an edit that undid
them. The text being asserted on is declared in ``prompt_model.py`` rather than here, so
that renaming a section is one edit rather than one per assertion.
"""

from __future__ import annotations

from prompt_model import (
    POINTER_DOCUMENT,
    ROUTINE_DOCUMENT,
    GitHubMcpTool,
    PointerPlaceholder,
    PromptDirective,
    PromptDocument,
    PromptLandmark,
    PromptRule,
)
from stack import BOARDLESS_COMMANDS, load_configuration

# %% the shape the Routine's prompt depends on


def test_routine_has_exactly_one_executable_prompt_block():
    """
    The Routine is told to execute the fenced block, so a second one would make that
    instruction ambiguous and none would leave it with nothing to run.
    """
    routine = PromptDocument.load(ROUTINE_DOCUMENT)

    assert routine.occurrences(PromptLandmark.EXECUTABLE_PROMPT_FENCE) == 1
    assert routine.executable_prompt()


def test_hard_rules_stay_inside_the_executable_block():
    """
    Commentary outside the fence is not executed, so moving the hard rules out would
    silently drop them from what the Routine actually runs.
    """
    prompt = PromptDocument.load(ROUTINE_DOCUMENT).executable_prompt()

    assert PromptDirective.HARD_RULES in prompt
    assert (
        f"{PromptDirective.NEVER} call "
        f"`{GitHubMcpTool.SUBSCRIBE_PULL_REQUEST_ACTIVITY}`" in prompt
    )


def test_setup_obtains_the_tooling_rather_than_assuming_it():
    """
    Setup must make ``stack.py`` present rather than assert that it is.

    Every later phase shells out to it, so a false assumption strands the Routine
    mid-run - and a Phase 2 failure lands after Phase 1 has already mutated pull
    requests.
    """
    routine = PromptDocument.load(ROUTINE_DOCUMENT)

    step_zero = routine.section(PromptLandmark.SETUP, PromptLandmark.FORK_MAIN_UPDATE)

    assert "fetch" in step_zero
    assert ".claude/stack/" in step_zero


# %% the fork-specific parts stay in the pointer


def test_setup_takes_the_tooling_ref_from_the_pointer():
    """
    Naming the branch here would bake one fork's in-flight branch into the shared
    routine document.

    The pointer already had to name a ref to resolve this document at all, so deferring
    to it keeps that name in one place and leaves it usable by any fork unchanged.
    """
    routine = PromptDocument.load(ROUTINE_DOCUMENT)

    step_zero = routine.section(PromptLandmark.SETUP, PromptLandmark.FORK_MAIN_UPDATE)

    assert "pointer" in step_zero


def test_routine_carries_no_placeholder_a_run_would_have_to_resolve():
    """
    The routine document is executed verbatim, so an unsubstituted placeholder would
    reach the Routine as an instruction it cannot follow.

    Everything fork-specific belongs in the pointer, which is substituted by hand at
    registration time.
    """
    routine = PromptDocument.load(ROUTINE_DOCUMENT)

    unresolved = [
        placeholder
        for placeholder in PointerPlaceholder
        if placeholder.value in routine.text
    ]

    assert unresolved == []


def test_setup_asks_the_tool_which_remote_is_which():
    """
    A checkout may call the fork anything, so names decide nothing.

    The document asks the tooling rather than writing remote names into git commands,
    which is what keeps a run from pointing pushes at the review repository.
    """
    routine = PromptDocument.load(ROUTINE_DOCUMENT)

    step_zero = routine.section(PromptLandmark.SETUP, PromptLandmark.FORK_MAIN_UPDATE)
    configuration = load_configuration()

    assert all(command in step_zero for command in BOARDLESS_COMMANDS)
    assert f"{configuration.fork_remote}/" not in routine.text
    assert f"{configuration.upstream_remote}/" not in routine.text


def test_routine_names_no_fork_of_its_own():
    """
    The fork is configuration, so the routine document has to read it rather than spell
    it out.

    It is executed verbatim on whichever fork registered it, so an owner named here is
    an instruction to operate on somebody else's repository.
    """
    routine = PromptDocument.load(ROUTINE_DOCUMENT)

    fork = load_configuration().fork_repository

    assert fork.owner not in routine.text
    assert str(fork) not in routine.text


def test_pointer_marks_every_fork_specific_value_as_a_placeholder():
    """
    The pointer is the one document that must name a fork and a branch, so it is also
    the one that has to be templated for anyone else to register it.
    """
    pointer = PromptDocument.load(POINTER_DOCUMENT)

    prompt = pointer.executable_prompt()

    assert PointerPlaceholder.FORK_REPOSITORY in prompt
    assert PointerPlaceholder.TOOLING_BRANCH in prompt


def test_pointer_sends_the_routine_to_the_routine_document():
    """
    The pointer's whole purpose is to delegate, so it must name the file to resolve;
    carrying instructions of its own is how the two drift apart.
    """
    prompt = PromptDocument.load(POINTER_DOCUMENT).executable_prompt()

    assert str(ROUTINE_DOCUMENT.relative_to(ROUTINE_DOCUMENT.parents[2])) in prompt


def test_pointer_hard_rules_match_the_routine_document_exactly():
    """
    The rules must bind before any file is read, so the pointer carries its own copy - the one
    duplication in this workflow, and the only place drift can reappear.
    """
    routine = PromptDocument.load(ROUTINE_DOCUMENT)
    pointer = PromptDocument.load(POINTER_DOCUMENT)

    assert pointer.hard_rules() == routine.hard_rules()


# %% the base-change client


def test_routine_names_the_one_client_that_can_change_a_base():
    """
    The rule exists, is stated once, and names the tool that actually works.
    """
    routine = PromptDocument.load(ROUTINE_DOCUMENT)

    assert routine.occurrences(PromptRule.BASE_CHANGE) == 1
    assert GitHubMcpTool.UPDATE_PULL_REQUEST in routine.paragraph(
        PromptRule.BASE_CHANGE
    )


def test_routine_records_that_the_git_proxy_refuses_a_base_change():
    """
    The refusal is recorded with its status code and the client that earns it, so a
    session that hits it recognises the known, documented case rather than an
    unexplained failure to improvise around.
    """
    rule = PromptDocument.load(ROUTINE_DOCUMENT).paragraph(PromptRule.BASE_CHANGE)

    assert PromptRule.BASE_CHANGE.refusal_status_code in rule
    assert PromptRule.BASE_CHANGE.refused_client in rule


# %% the reparent sequences


def test_native_stack_reparent_changes_the_base_rather_than_replacing_the_pull_request():
    """
    Reparenting keeps the pull request, its number and its review thread.

    Closing the orphan and opening a replacement was considered while the base change
    was believed impossible from a session; it is not, so the sequence must not drift
    back to it.
    """
    phase_one = PromptDocument.load(ROUTINE_DOCUMENT).section(
        PromptLandmark.PHASE_ONE, PromptLandmark.PHASE_TWO
    )

    sequence = phase_one[phase_one.index(PromptLandmark.NATIVE_STACK_MEMBERS.text) :]

    assert GitHubMcpTool.UPDATE_PULL_REQUEST in sequence
    assert GitHubMcpTool.CREATE_PULL_REQUEST not in sequence


def test_every_reparent_instruction_points_at_the_base_change_rule():
    """
    Both reparent sites - the orphaned-child sweep and the per-merged-parent list - defer
    to the one rule, so neither can prescribe a client of its own.
    """
    phase_one = PromptDocument.load(ROUTINE_DOCUMENT).section(
        PromptLandmark.PHASE_ONE, PromptLandmark.PHASE_TWO
    )

    orphan_sweep = phase_one[
        phase_one.index(PromptLandmark.ORPHANED_CHILD_SWEEP.text) : phase_one.index(
            PromptLandmark.NATIVE_STACK_MEMBERS.text
        )
    ]
    merged_parent_list = phase_one[
        phase_one.index(PromptLandmark.MERGED_PARENT_LIST.text) :
    ]

    assert GitHubMcpTool.UPDATE_PULL_REQUEST in orphan_sweep
    assert GitHubMcpTool.UPDATE_PULL_REQUEST in merged_parent_list
