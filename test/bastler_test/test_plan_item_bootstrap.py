"""
Tests for bastler.plan_item_bootstrap.py's two operations, recording an item and opening
its work.

Run against the local scratch repository fixture rather than a real remote, and against
a recording pull request opener rather than GitHub, so nothing here needs network access
or credentials.

Every manifest line asserted on is rendered by the :class:`ManifestKey` that owns it,
and every path by the :class:`PlanDocument` that lives at it, so a test cannot pin a
second, independently-drifting copy of the manifest's own vocabulary.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

import pytest
import yaml

import bastler.plan_item_bootstrap
from bastler.plan_item_bootstrap import (
    BLOCK_STYLED_KEYS,
    ITEM_FIELD_INDENT,
    MANIFEST_LINE_WIDTH,
    PLANS_DIRECTORY,
    SEQUENCE_ENTRY_INDENT,
    CreatedPullRequest,
    ExitCode,
    HookScript,
    ItemRecordRequest,
    ItemStatus,
    ItemUpdateRequest,
    KeySpecification,
    ManifestKey,
    PlanDocument,
    PullRequestRequest,
    Subcommand,
    UnknownItemError,
    UnknownPlanError,
    ValueStyle,
    WorkOpenRequest,
    block_branch,
    check_item,
    open_work,
    record_item,
    repair_text,
    resolve_branch,
    unblock_branch,
    update_item,
)
from .scratch_repository import ScratchRepository
from .constants import DATASET_DIRECTORY, WORK_BRANCH

from .script_runner import PythonModuleRunner

BOOTSTRAP_MODULE = bastler.plan_item_bootstrap.__name__
"""
The import path the scratch layout's copy of the module under test is run by.

Read off the module rather than spelled out, so a rename cannot leave the tests running
something else - and ``-m`` rather than a file path, since a module run by path would put
the package's own directory on ``sys.path`` in place of the project root.
"""

PLAN_IDENTIFIER = "test-plan"

PLAN_MANIFEST = (DATASET_DIRECTORY / "bootstrap-plan.yaml").read_text()
"""
The manifest every test starts from.
"""

PLAN_ROADMAP = (DATASET_DIRECTORY / "bootstrap-roadmap.md").read_text()
"""
The roadmap every test starts from.
"""

EXISTING_ITEM = "an-existing-item"
"""
The fixture item the plan already tracks, with no branch of its own yet.
"""

NEW_ITEM = "a-brand-new-item"
"""
An item the fixture plan does not track, for the entry-creating path.
"""

SECOND_ITEM = "a-second-item"
"""
The fixture item that follows the one under test, for asserting a write left the items
after it untouched.
"""

WORK_REMOTE = "origin"
"""
The remote :meth:`ScratchRepository.add_work_remote` registers, and the one the module's
own operations default to.
"""

NEW_BRANCH = "claude/a-new-branch"
"""
The branch opening the work publishes.
"""

SESSION_URL = "https://example.invalid/session_first"
"""
The session recorded on an item whose work was opened.
"""

SECOND_ITEM_BRANCH = next(
    item[ManifestKey.BRANCH.key]
    for item in yaml.safe_load(PLAN_MANIFEST)[ManifestKey.ITEMS.key]
    if item[ManifestKey.IDENTIFIER.key] == SECOND_ITEM
)
"""
The branch the fixture's underway item rides on, read from the fixture rather than
restated beside it.
"""

OWNER = "a-maintenance-pass"
"""
The automated caller whose blockers are its own to write and to clear.
"""

CONFLICT_REASON = "conflicts with its base in a_file.py"
"""
Why that caller blocked the item.
"""

HAND_WRITTEN_BLOCKER = "waiting on a decision nobody automated"
"""
A blocker no automated caller owns, which none of them may touch.
"""


def manifest_line(manifest_key: ManifestKey, value: str) -> str:
    """
    One manifest line as the key that owns it writes it.

    :param manifest_key: The key the line sets.
    :param value: The value it carries.
    :return: The rendered line.
    """
    return manifest_key.render(value)


# %% fixtures


@dataclass
class RecordingPullRequestOpener:
    """
    Stands in for the GitHub pull request endpoint, recording what it was asked to
    create instead of calling it.
    """

    number: int = 99
    """
    The pull request number handed back to the caller.
    """

    requests: list[PullRequestRequest] = field(default_factory=list)
    """
    Every request this opener was given, in call order.
    """

    def open_pull_request(self, request: PullRequestRequest) -> CreatedPullRequest:
        """
        Record *request* and hand back a pull request as GitHub would.

        :param request: The pull request to create.
        :return: The created pull request.
        """
        self.requests.append(request)
        return CreatedPullRequest(
            number=self.number,
            html_url=f"https://example.invalid/pull/{self.number}",
        )


@dataclass
class RefusingPullRequestOpener:
    """
    Stands in for a GitHub endpoint that refuses the creation.
    """

    def open_pull_request(self, request: PullRequestRequest) -> CreatedPullRequest:
        """
        Refuse the creation the way the real opener does on a non-success response.

        :param request: The pull request that will not be created.
        :raises PullRequestRefusedError: Always.
        """
        raise bastler.plan_item_bootstrap.PullRequestRefusedError(detail="422 refused")


@pytest.fixture
def bootstrap_repository(scratch_repository: ScratchRepository) -> ScratchRepository:
    """
    A scratch repository carrying the hook scripts this module drives, with a plan
    already published on its notes branch.

    :param scratch_repository: The initialized scratch repository and notes remote.
    :return: The same repository, ready to bootstrap an item in.
    """
    scratch_repository.install_hook_scripts(
        HookScript.CONFIGURATION.value,
        HookScript.SAVE_PLAN.value,
    )
    scratch_repository.install_package()
    scratch_repository.write("README.md", "scratch repo\n")
    scratch_repository.commit_everything("initial commit")
    scratch_repository.publish_notes_branch(
        {
            PlanDocument.MANIFEST.path_within_notes_branch(PLAN_IDENTIFIER): (
                PLAN_MANIFEST
            ),
            PlanDocument.ROADMAP.path_within_notes_branch(PLAN_IDENTIFIER): (
                PLAN_ROADMAP
            ),
        }
    )
    scratch_repository.resolve_notes_remote_to()
    scratch_repository.add_work_remote()
    return scratch_repository


def published_plan(repository: ScratchRepository) -> dict[PlanDocument, str]:
    """
    Read the plan's documents as they actually are on the notes branch, rather than what
    a run reported.

    Asks each document where it lives, so this never states a plan's layout
    independently of the code that owns it.

    :param repository: The scratch repository whose notes remote to read.
    :return: Each document's content.
    """
    checkout = repository.project_root.parent / "published-plan-checkout"
    shutil.rmtree(checkout, ignore_errors=True)
    repository.clone_notes_branch(checkout)
    return {
        document: (
            checkout / document.path_within_notes_branch(PLAN_IDENTIFIER)
        ).read_text()
        for document in PlanDocument
    }


def roadmap_section(repository: ScratchRepository, content: str) -> Path:
    """
    Write a roadmap section to a scratch file, the way a caller hands one over.

    The file is named after its content so that a test overriding the default section
    cannot have its file overwritten by the default one being built alongside it.

    :param repository: The scratch repository to write within.
    :param content: The section's markdown.
    :return: The path written to.
    """
    digest = hashlib.sha256(content.encode()).hexdigest()[:12]
    return repository.write(f"sections/{digest}.md", content)


def record_request(repository: ScratchRepository, **overrides: object):
    """
    Build a record request, overriding only what a test cares about.

    :param repository: The scratch repository the roadmap section is written in.
    :param overrides: Fields to replace on the default request.
    :return: The request.
    """
    defaults = dict(
        plan_identifier=PLAN_IDENTIFIER,
        item_identifier=EXISTING_ITEM,
        status=ItemStatus.IN_PROGRESS,
        roadmap_section_path=roadmap_section(repository, "## A new section\n"),
    )
    defaults.update(overrides)
    return ItemRecordRequest(**defaults)


def update_request(**overrides: object) -> ItemUpdateRequest:
    """
    Build an update request, overriding only what a test cares about.

    :param overrides: Fields to replace on the default request.
    :return: The request.
    """
    defaults = dict(
        plan_identifier=PLAN_IDENTIFIER,
        item_identifier=EXISTING_ITEM,
        values_by_key={},
    )
    defaults.update(overrides)
    return ItemUpdateRequest(**defaults)


def published_item(repository: ScratchRepository) -> dict[str, object]:
    """
    The item under test as YAML actually parses it off the notes branch.

    Parsing rather than matching text is what catches a write that leaves the manifest
    valid but means something other than it says.

    :param repository: The scratch repository whose notes remote to read.
    :return: The item's parsed mapping.
    """
    manifest = yaml.safe_load(
        published_plan(repository)[PlanDocument.MANIFEST],
    )
    return next(
        item
        for item in manifest[ManifestKey.ITEMS.key]
        if item[ManifestKey.IDENTIFIER.key] == EXISTING_ITEM
    )


def entry_wrapping_across(unbreakable: str) -> str:
    """
    A blocker long enough that wrapping has to break somewhere inside *unbreakable*.

    Positioned from the writer's own wrap column rather than from a hand-tuned literal,
    so this keeps reproducing the hazard if that column ever moves.

    :param unbreakable: The token that has to survive the wrap intact.
    :return: The blocker's text.
    """
    body_width = MANIFEST_LINE_WIDTH - len(SEQUENCE_ENTRY_INDENT + ITEM_FIELD_INDENT)
    lead = "word "
    return (
        lead * ((body_width - len(unbreakable) // 2) // len(lead))
        + unbreakable
        + " and there is more text after it."
    )


def published_items(repository: ScratchRepository) -> dict[str, dict[str, object]]:
    """
    Every item as YAML actually parses it off the notes branch, keyed by id.

    :param repository: The scratch repository whose notes remote to read.
    :return: Each item's parsed mapping.
    """
    manifest = yaml.safe_load(published_plan(repository)[PlanDocument.MANIFEST])
    return {
        item[ManifestKey.IDENTIFIER.key]: item
        for item in manifest[ManifestKey.ITEMS.key]
    }


def publish_the_branch_index(repository: ScratchRepository) -> None:
    """
    Make the generated branch index exist, by running the save path that writes it.

    Only ``save-plan.sh`` writes that index, so a test needing one asks for a real save
    rather than assembling a second copy of its format beside it.

    :param repository: The scratch repository to save within.
    """
    update_item(update_request(), project_root=repository.project_root)


def put_both_items_on_one_branch(repository: ScratchRepository) -> None:
    """
    Move the fixture's unstarted item onto the branch its underway one already rides on.

    Two items on one branch is ordinary - a plan can split what one branch does into
    more than one tracked item - so every operation keyed on a branch has to answer for
    all of them.

    :param repository: The scratch repository to save within.
    """
    update_item(
        update_request(values_by_key={ManifestKey.BRANCH: SECOND_ITEM_BRANCH}),
        project_root=repository.project_root,
    )


def open_request(**overrides: object) -> WorkOpenRequest:
    """
    Build a work-open request, overriding only what a test cares about.

    :param overrides: Fields to replace on the default request.
    :return: The request.
    """
    defaults = dict(
        plan_identifier=PLAN_IDENTIFIER,
        item_identifier=EXISTING_ITEM,
        branch=NEW_BRANCH,
        base_branch=WORK_BRANCH,
        session_url=SESSION_URL,
        pull_request_title="An item that has not been started",
        pull_request_body="What it does.",
    )
    defaults.update(overrides)
    return WorkOpenRequest(**defaults)


# %% recording an item


def test_recording_an_existing_item_sets_its_status(
    bootstrap_repository: ScratchRepository,
):
    result = record_item(
        record_request(bootstrap_repository),
        project_root=bootstrap_repository.project_root,
    )

    assert result.exit_code is ExitCode.SUCCESS
    published = published_plan(bootstrap_repository)
    assert (
        manifest_line(ManifestKey.STATUS, ItemStatus.IN_PROGRESS.value)
        in published[PlanDocument.MANIFEST]
    )


def test_recording_leaves_every_other_manifest_line_byte_identical(
    bootstrap_repository: ScratchRepository,
):
    record_item(
        record_request(bootstrap_repository),
        project_root=bootstrap_repository.project_root,
    )

    expected = PLAN_MANIFEST.replace(
        manifest_line(ManifestKey.STATUS, ItemStatus.NOT_STARTED.value),
        manifest_line(ManifestKey.STATUS, ItemStatus.IN_PROGRESS.value),
        1,
    )
    assert published_plan(bootstrap_repository)[PlanDocument.MANIFEST] == expected


def test_recording_appends_the_roadmap_section_without_rewriting_the_roadmap(
    bootstrap_repository: ScratchRepository,
):
    section = "## An appended section\n\nIts body.\n"
    record_item(
        record_request(
            bootstrap_repository,
            roadmap_section_path=roadmap_section(bootstrap_repository, section),
        ),
        project_root=bootstrap_repository.project_root,
    )

    roadmap = published_plan(bootstrap_repository)[PlanDocument.ROADMAP]
    assert roadmap.startswith(PLAN_ROADMAP)
    assert roadmap.endswith(section)


def test_recording_a_new_item_appends_it_to_the_manifest(
    bootstrap_repository: ScratchRepository,
):
    record_item(
        record_request(
            bootstrap_repository,
            item_identifier=NEW_ITEM,
            title="A brand new item",
            track="a-track",
            status=ItemStatus.NOT_STARTED,
        ),
        project_root=bootstrap_repository.project_root,
    )

    manifest = published_plan(bootstrap_repository)[PlanDocument.MANIFEST]
    assert manifest.startswith(PLAN_MANIFEST)
    assert manifest.endswith(
        ManifestKey.IDENTIFIER.render(NEW_ITEM, opening_the_item=True)
        + manifest_line(ManifestKey.TITLE, "A brand new item")
        + manifest_line(ManifestKey.BRANCH, "null")
        + manifest_line(ManifestKey.TRACK, "a-track")
        + manifest_line(ManifestKey.DEPENDS_ON, "[]")
        + manifest_line(ManifestKey.STATUS, ItemStatus.NOT_STARTED.value)
    )


def test_recording_a_new_item_without_a_title_names_the_key_it_needs(
    bootstrap_repository: ScratchRepository,
):
    with pytest.raises(bastler.plan_item_bootstrap.IncompleteNewItemError) as refusal:
        record_item(
            record_request(
                bootstrap_repository,
                item_identifier=NEW_ITEM,
                track="a-track",
                status=ItemStatus.NOT_STARTED,
            ),
            project_root=bootstrap_repository.project_root,
        )

    assert refusal.value.missing_keys == (ManifestKey.TITLE,)


def test_recording_against_an_unknown_plan_is_refused(
    bootstrap_repository: ScratchRepository,
):
    with pytest.raises(UnknownPlanError) as refusal:
        record_item(
            record_request(bootstrap_repository, plan_identifier="no-such-plan"),
            project_root=bootstrap_repository.project_root,
        )

    assert refusal.value.plan_identifier == "no-such-plan"


# %% opening the work


def test_opening_writes_the_branch_pull_request_and_session_onto_the_item(
    bootstrap_repository: ScratchRepository,
):
    opener = RecordingPullRequestOpener(number=143)

    result = open_work(
        open_request(),
        project_root=bootstrap_repository.project_root,
        pull_request_opener=opener,
    )

    assert result.exit_code is ExitCode.SUCCESS
    assert result.pull_request_number == 143
    manifest = published_plan(bootstrap_repository)[PlanDocument.MANIFEST]
    for written_key, value in (
        (ManifestKey.BRANCH, NEW_BRANCH),
        (ManifestKey.PULL_REQUEST_NUMBER, "143"),
        (ManifestKey.SESSION, SESSION_URL),
        (ManifestKey.STATUS, ItemStatus.IN_PROGRESS.value),
    ):
        assert manifest_line(written_key, value) in manifest


def test_opening_asks_for_a_draft_pull_request_against_the_plans_repository(
    bootstrap_repository: ScratchRepository,
):
    opener = RecordingPullRequestOpener()

    open_work(
        open_request(),
        project_root=bootstrap_repository.project_root,
        pull_request_opener=opener,
    )

    assert len(opener.requests) == 1
    request = opener.requests[0]
    assert request.draft is True
    assert request.repository == "an-owner/a-repository"
    assert request.head == NEW_BRANCH
    assert request.base == WORK_BRANCH


def test_opening_publishes_the_branch_to_the_repositorys_own_remote(
    bootstrap_repository: ScratchRepository,
):
    open_work(
        open_request(),
        project_root=bootstrap_repository.project_root,
        pull_request_opener=RecordingPullRequestOpener(),
    )

    published = bootstrap_repository.run_git(
        "ls-remote",
        "--heads",
        str(bootstrap_repository.work_remote_path),
        NEW_BRANCH,
    )
    assert NEW_BRANCH in published.stdout


def test_opening_an_already_published_branch_is_refused(
    bootstrap_repository: ScratchRepository,
):
    opener = RecordingPullRequestOpener()
    open_work(
        open_request(),
        project_root=bootstrap_repository.project_root,
        pull_request_opener=opener,
    )

    with pytest.raises(
        bastler.plan_item_bootstrap.BranchAlreadyPublishedError
    ) as refusal:
        open_work(
            open_request(),
            project_root=bootstrap_repository.project_root,
            pull_request_opener=opener,
        )
    assert refusal.value.branch == NEW_BRANCH
    assert len(opener.requests) == 1


def test_opening_an_unknown_item_is_refused_before_anything_is_created(
    bootstrap_repository: ScratchRepository,
):
    opener = RecordingPullRequestOpener()

    with pytest.raises(UnknownItemError):
        open_work(
            open_request(item_identifier="no-such-item"),
            project_root=bootstrap_repository.project_root,
            pull_request_opener=opener,
        )

    assert opener.requests == []
    published = bootstrap_repository.run_git(
        "ls-remote", "--heads", str(bootstrap_repository.work_remote_path)
    )
    assert NEW_BRANCH not in published.stdout


def test_a_refused_pull_request_leaves_the_manifest_untouched(
    bootstrap_repository: ScratchRepository,
):
    with pytest.raises(bastler.plan_item_bootstrap.PullRequestRefusedError):
        open_work(
            open_request(),
            project_root=bootstrap_repository.project_root,
            pull_request_opener=RefusingPullRequestOpener(),
        )

    assert published_plan(bootstrap_repository)[PlanDocument.MANIFEST] == PLAN_MANIFEST


def test_a_refused_pull_request_leaves_the_branch_it_already_published(
    bootstrap_repository: ScratchRepository,
):
    with pytest.raises(bastler.plan_item_bootstrap.PullRequestRefusedError):
        open_work(
            open_request(),
            project_root=bootstrap_repository.project_root,
            pull_request_opener=RefusingPullRequestOpener(),
        )

    published = bootstrap_repository.run_git(
        "ls-remote",
        "--heads",
        str(bootstrap_repository.work_remote_path),
        NEW_BRANCH,
    )
    assert NEW_BRANCH in published.stdout


def test_a_supplied_pull_request_number_is_recorded_without_creating_one(
    bootstrap_repository: ScratchRepository,
):
    opener = RecordingPullRequestOpener()

    result = open_work(
        open_request(pull_request_number=57),
        project_root=bootstrap_repository.project_root,
        pull_request_opener=opener,
    )

    assert opener.requests == []
    assert result.pull_request_number == 57
    assert (
        manifest_line(ManifestKey.PULL_REQUEST_NUMBER, "57")
        in published_plan(bootstrap_repository)[PlanDocument.MANIFEST]
    )


def test_creating_a_pull_request_without_a_title_or_body_is_refused_before_publishing(
    bootstrap_repository: ScratchRepository,
):
    with pytest.raises(bastler.plan_item_bootstrap.PullRequestDetailsMissingError):
        open_work(
            open_request(pull_request_title=None, pull_request_body=None),
            project_root=bootstrap_repository.project_root,
            pull_request_opener=RecordingPullRequestOpener(),
        )

    published = bootstrap_repository.run_git(
        "ls-remote", "--heads", str(bootstrap_repository.work_remote_path)
    )
    assert NEW_BRANCH not in published.stdout


def test_a_supplied_pull_request_number_adopts_the_branch_its_caller_published(
    bootstrap_repository: ScratchRepository,
):
    open_work(
        open_request(),
        project_root=bootstrap_repository.project_root,
        pull_request_opener=RecordingPullRequestOpener(number=99),
    )

    result = open_work(
        open_request(pull_request_number=57),
        project_root=bootstrap_repository.project_root,
        pull_request_opener=RecordingPullRequestOpener(),
    )

    assert result.pull_request_number == 57


# %% updating an item's recorded fields


def test_writing_a_note_replaces_the_folded_block_rather_than_its_first_line(
    bootstrap_repository: ScratchRepository,
):
    update_item(
        update_request(values_by_key={ManifestKey.NOTES: "What this run found."}),
        project_root=bootstrap_repository.project_root,
    )

    assert published_item(bootstrap_repository)[ManifestKey.NOTES.key] == (
        "What this run found.\n"
    )


def test_appending_to_a_note_keeps_the_recorded_paragraphs_apart(
    bootstrap_repository: ScratchRepository,
):
    """
    The recorded note comes back with one newline between paragraphs where the file a
    caller writes uses a blank line, so appending must restore the blank lines or the
    whole note collapses into a single paragraph.
    """
    update_item(
        update_request(values_by_key={ManifestKey.NOTES: "The first.\n\nThe second."}),
        project_root=bootstrap_repository.project_root,
    )

    update_item(
        update_request(notes_to_append="The third.\n"),
        project_root=bootstrap_repository.project_root,
    )

    assert published_item(bootstrap_repository)[ManifestKey.NOTES.key] == (
        "The first.\nThe second.\nThe third.\n"
    )


def test_appending_to_an_item_carrying_no_note_records_only_the_addition(
    bootstrap_repository: ScratchRepository,
):
    update_item(
        update_request(
            item_identifier=SECOND_ITEM, notes_to_append="The only paragraph.\n"
        ),
        project_root=bootstrap_repository.project_root,
    )

    published = yaml.safe_load(
        published_plan(bootstrap_repository)[PlanDocument.MANIFEST]
    )
    written = next(
        item
        for item in published[ManifestKey.ITEMS.key]
        if item[ManifestKey.IDENTIFIER.key] == SECOND_ITEM
    )
    assert written[ManifestKey.NOTES.key] == "The only paragraph.\n"


def test_replacing_a_note_and_extending_it_cannot_be_asked_for_at_once(
    bootstrap_repository: ScratchRepository,
):
    note = bootstrap_repository.write("note.md", "Replaces it.\n")
    addition = bootstrap_repository.write("addition.md", "Extends it.\n")

    result = run_bootstrap(
        bootstrap_repository,
        "update",
        "--plan",
        PLAN_IDENTIFIER,
        "--item",
        EXISTING_ITEM,
        "--notes",
        str(note),
        "--append-notes",
        str(addition),
    )

    assert result.returncode != 0
    assert "--append-notes" in result.stderr


def test_writing_a_note_leaves_the_other_items_byte_identical(
    bootstrap_repository: ScratchRepository,
):
    update_item(
        update_request(values_by_key={ManifestKey.NOTES: "What this run found."}),
        project_root=bootstrap_repository.project_root,
    )

    published = published_plan(bootstrap_repository)[PlanDocument.MANIFEST]
    second_item_start = published.index(
        f"- {ManifestKey.IDENTIFIER.key}: {SECOND_ITEM}"
    )
    original_start = PLAN_MANIFEST.index(
        f"- {ManifestKey.IDENTIFIER.key}: {SECOND_ITEM}"
    )
    assert published[second_item_start:] == PLAN_MANIFEST[original_start:]


def test_writing_blockers_renders_them_as_a_sequence(
    bootstrap_repository: ScratchRepository,
):
    blockers = [
        "A short one.",
        "A blocker long enough that it has to fold over more than a single line of "
        "the manifest, which is what the sequence rendering has to get right.",
    ]
    update_item(
        update_request(values_by_key={ManifestKey.BLOCKERS: blockers}),
        project_root=bootstrap_repository.project_root,
    )

    assert published_item(bootstrap_repository)[ManifestKey.BLOCKERS.key] == blockers


@pytest.mark.parametrize(
    "unbreakable",
    [
        "claude/workflow-unification-setup-jgvs53",
        "https://example.invalid/a/single/path/segment/long/enough/that/it/cannot/fit/"
        "on/one/body/line/of/the/manifest/at/all",
    ],
    ids=["hyphenated-branch", "url-longer-than-a-line"],
)
def test_a_folded_entry_parses_back_as_the_text_it_was_given(
    bootstrap_repository: ScratchRepository, unbreakable: str
):
    """
    A line break inside a folded scalar comes back as a space, so wrapping is only
    lossless while it happens between words - a branch name or a URL broken across two
    lines returns with a space inside it, still valid and no longer the same string.
    """
    blocker = entry_wrapping_across(unbreakable)

    update_item(
        update_request(values_by_key={ManifestKey.BLOCKERS: [blocker]}),
        project_root=bootstrap_repository.project_root,
    )

    assert published_item(bootstrap_repository)[ManifestKey.BLOCKERS.key] == [blocker]


def test_an_emptied_sequence_is_written_as_a_list_rather_than_as_nothing(
    bootstrap_repository: ScratchRepository,
):
    """
    A bare ``blockers:`` parses as null, not as an empty list, so clearing the last
    entry would leave the item carrying a value its own schema rejects.
    """
    update_item(
        update_request(values_by_key={ManifestKey.BLOCKERS: ["Something."]}),
        project_root=bootstrap_repository.project_root,
    )

    update_item(
        update_request(values_by_key={ManifestKey.BLOCKERS: []}),
        project_root=bootstrap_repository.project_root,
    )

    assert published_item(bootstrap_repository)[ManifestKey.BLOCKERS.key] == []


def test_updating_sets_every_plain_field_it_is_given(
    bootstrap_repository: ScratchRepository,
):
    update_item(
        update_request(
            values_by_key={
                ManifestKey.STATUS: ItemStatus.BLOCKED,
                ManifestKey.BRANCH: NEW_BRANCH,
                ManifestKey.PULL_REQUEST_NUMBER: 57,
                ManifestKey.SESSION: SESSION_URL,
            }
        ),
        project_root=bootstrap_repository.project_root,
    )

    item = published_item(bootstrap_repository)
    assert item[ManifestKey.STATUS.key] == ItemStatus.BLOCKED.value
    assert item[ManifestKey.BRANCH.key] == NEW_BRANCH
    assert item[ManifestKey.PULL_REQUEST_NUMBER.key] == 57
    assert item[ManifestKey.SESSION.key] == SESSION_URL


def test_updating_needs_no_roadmap_section(bootstrap_repository: ScratchRepository):
    update_item(
        update_request(values_by_key={ManifestKey.STATUS: ItemStatus.BLOCKED}),
        project_root=bootstrap_repository.project_root,
    )

    published = published_plan(bootstrap_repository)
    assert published[PlanDocument.ROADMAP] == PLAN_ROADMAP


def test_updating_an_unknown_item_is_refused(bootstrap_repository: ScratchRepository):
    with pytest.raises(UnknownItemError) as refusal:
        update_item(
            update_request(
                item_identifier=NEW_ITEM,
                values_by_key={ManifestKey.STATUS: ItemStatus.BLOCKED},
            ),
            project_root=bootstrap_repository.project_root,
        )

    assert refusal.value.exit_code is ExitCode.UNKNOWN_ITEM
    assert published_plan(bootstrap_repository)[PlanDocument.MANIFEST] == PLAN_MANIFEST


def test_updating_hands_the_dashboard_republish_back(
    bootstrap_repository: ScratchRepository,
):
    report = update_item(
        update_request(values_by_key={ManifestKey.STATUS: ItemStatus.BLOCKED}),
        project_root=bootstrap_repository.project_root,
    )

    assert report.dashboard_command == f"/plan-dashboard {PLAN_IDENTIFIER}"


# %% checking what the manifest claims against local git


def test_a_recorded_branch_that_was_never_published_is_reported_stale(
    bootstrap_repository: ScratchRepository,
):
    update_item(
        update_request(values_by_key={ManifestKey.BRANCH: NEW_BRANCH}),
        project_root=bootstrap_repository.project_root,
    )

    report = check_item(
        PLAN_IDENTIFIER, EXISTING_ITEM, project_root=bootstrap_repository.project_root
    )

    assert [finding.manifest_key for finding in report.findings] == [ManifestKey.BRANCH]
    assert report.findings[0].recorded == NEW_BRANCH
    assert report.exit_code is ExitCode.MANIFEST_IS_STALE


def test_an_item_recording_a_published_branch_reports_nothing_stale(
    bootstrap_repository: ScratchRepository,
):
    bootstrap_repository.run_git("checkout", "-b", NEW_BRANCH)
    bootstrap_repository.run_git("push", "--quiet", WORK_REMOTE, NEW_BRANCH)
    update_item(
        update_request(
            values_by_key={
                ManifestKey.BRANCH: NEW_BRANCH,
                ManifestKey.STATUS: ItemStatus.IN_PROGRESS,
                ManifestKey.SESSION: SESSION_URL,
                ManifestKey.PULL_REQUEST_NUMBER: 57,
            }
        ),
        project_root=bootstrap_repository.project_root,
    )

    report = check_item(
        PLAN_IDENTIFIER, EXISTING_ITEM, project_root=bootstrap_repository.project_root
    )

    assert report.findings == []
    assert report.exit_code is ExitCode.SUCCESS


def test_a_published_branch_with_no_session_recorded_is_reported_stale(
    bootstrap_repository: ScratchRepository,
):
    bootstrap_repository.run_git("checkout", "-b", NEW_BRANCH)
    bootstrap_repository.run_git("push", "--quiet", WORK_REMOTE, NEW_BRANCH)
    update_item(
        update_request(
            values_by_key={
                ManifestKey.BRANCH: NEW_BRANCH,
                ManifestKey.STATUS: ItemStatus.IN_PROGRESS,
            }
        ),
        project_root=bootstrap_repository.project_root,
    )

    report = check_item(
        PLAN_IDENTIFIER, EXISTING_ITEM, project_root=bootstrap_repository.project_root
    )

    assert ManifestKey.SESSION in [finding.manifest_key for finding in report.findings]


def test_a_branch_exists_while_the_item_is_still_not_started(
    bootstrap_repository: ScratchRepository,
):
    bootstrap_repository.run_git("checkout", "-b", NEW_BRANCH)
    bootstrap_repository.run_git("push", "--quiet", WORK_REMOTE, NEW_BRANCH)
    update_item(
        update_request(values_by_key={ManifestKey.BRANCH: NEW_BRANCH}),
        project_root=bootstrap_repository.project_root,
    )

    report = check_item(
        PLAN_IDENTIFIER, EXISTING_ITEM, project_root=bootstrap_repository.project_root
    )

    status_finding = next(
        finding
        for finding in report.findings
        if finding.manifest_key is ManifestKey.STATUS
    )
    assert status_finding.recorded == ItemStatus.NOT_STARTED.value


def test_checking_an_unknown_item_is_refused(bootstrap_repository: ScratchRepository):
    with pytest.raises(UnknownItemError) as refusal:
        check_item(
            PLAN_IDENTIFIER, NEW_ITEM, project_root=bootstrap_repository.project_root
        )

    assert refusal.value.exit_code is ExitCode.UNKNOWN_ITEM


# %% resolving a branch to the items it carries


def test_resolving_a_branch_names_the_plan_that_tracks_it(
    bootstrap_repository: ScratchRepository,
):
    publish_the_branch_index(bootstrap_repository)

    resolution = resolve_branch(
        SECOND_ITEM_BRANCH, project_root=bootstrap_repository.project_root
    )

    assert resolution.plan_identifier == PLAN_IDENTIFIER
    assert [item.item_identifier for item in resolution.items] == [SECOND_ITEM]


def test_resolving_reports_the_status_and_blockers_each_item_records(
    bootstrap_repository: ScratchRepository,
):
    publish_the_branch_index(bootstrap_repository)

    resolution = resolve_branch(
        SECOND_ITEM_BRANCH, project_root=bootstrap_repository.project_root
    )

    assert resolution.items[0].status is ItemStatus.IN_PROGRESS
    assert resolution.items[0].blockers == []


def test_resolving_a_branch_two_items_ride_on_answers_with_both(
    bootstrap_repository: ScratchRepository,
):
    put_both_items_on_one_branch(bootstrap_repository)

    resolution = resolve_branch(
        SECOND_ITEM_BRANCH, project_root=bootstrap_repository.project_root
    )

    assert sorted(item.item_identifier for item in resolution.items) == sorted(
        [EXISTING_ITEM, SECOND_ITEM]
    )


def test_a_branch_no_plan_claims_is_reported_rather_than_refused(
    bootstrap_repository: ScratchRepository,
):
    publish_the_branch_index(bootstrap_repository)

    resolution = resolve_branch(
        "claude/belongs-to-nothing", project_root=bootstrap_repository.project_root
    )

    assert resolution.plan_identifier is None
    assert resolution.items == []
    assert resolution.exit_code is ExitCode.BRANCH_TRACKS_NO_ITEM


# %% owning a blocker on every item a branch carries


def test_blocking_a_branch_blocks_every_item_it_carries(
    bootstrap_repository: ScratchRepository,
):
    put_both_items_on_one_branch(bootstrap_repository)

    block_branch(
        SECOND_ITEM_BRANCH,
        owner=OWNER,
        reason=CONFLICT_REASON,
        project_root=bootstrap_repository.project_root,
    )

    for item in published_items(bootstrap_repository).values():
        assert item[ManifestKey.STATUS.key] == ItemStatus.BLOCKED.value
        assert item[ManifestKey.BLOCKERS.key] == [f"{OWNER}: {CONFLICT_REASON}"]


def test_blocking_keeps_a_blocker_somebody_else_wrote(
    bootstrap_repository: ScratchRepository,
):
    publish_the_branch_index(bootstrap_repository)
    update_item(
        update_request(
            item_identifier=SECOND_ITEM,
            values_by_key={ManifestKey.BLOCKERS: [HAND_WRITTEN_BLOCKER]},
        ),
        project_root=bootstrap_repository.project_root,
    )

    block_branch(
        SECOND_ITEM_BRANCH,
        owner=OWNER,
        reason=CONFLICT_REASON,
        project_root=bootstrap_repository.project_root,
    )

    assert published_items(bootstrap_repository)[SECOND_ITEM][
        ManifestKey.BLOCKERS.key
    ] == [HAND_WRITTEN_BLOCKER, f"{OWNER}: {CONFLICT_REASON}"]


def test_blocking_a_second_time_replaces_its_own_blocker_rather_than_repeating_it(
    bootstrap_repository: ScratchRepository,
):
    publish_the_branch_index(bootstrap_repository)
    block_branch(
        SECOND_ITEM_BRANCH,
        owner=OWNER,
        reason=CONFLICT_REASON,
        project_root=bootstrap_repository.project_root,
    )

    block_branch(
        SECOND_ITEM_BRANCH,
        owner=OWNER,
        reason="a different file conflicts now",
        project_root=bootstrap_repository.project_root,
    )

    assert published_items(bootstrap_repository)[SECOND_ITEM][
        ManifestKey.BLOCKERS.key
    ] == [f"{OWNER}: a different file conflicts now"]


def test_unblocking_removes_only_the_blocker_it_owns(
    bootstrap_repository: ScratchRepository,
):
    publish_the_branch_index(bootstrap_repository)
    update_item(
        update_request(
            item_identifier=SECOND_ITEM,
            values_by_key={ManifestKey.BLOCKERS: [HAND_WRITTEN_BLOCKER]},
        ),
        project_root=bootstrap_repository.project_root,
    )
    block_branch(
        SECOND_ITEM_BRANCH,
        owner=OWNER,
        reason=CONFLICT_REASON,
        project_root=bootstrap_repository.project_root,
    )

    unblock_branch(
        SECOND_ITEM_BRANCH,
        owner=OWNER,
        project_root=bootstrap_repository.project_root,
    )

    assert published_items(bootstrap_repository)[SECOND_ITEM][
        ManifestKey.BLOCKERS.key
    ] == [HAND_WRITTEN_BLOCKER]


def test_an_item_still_carrying_somebody_elses_blocker_stays_blocked(
    bootstrap_repository: ScratchRepository,
):
    publish_the_branch_index(bootstrap_repository)
    update_item(
        update_request(
            item_identifier=SECOND_ITEM,
            values_by_key={ManifestKey.BLOCKERS: [HAND_WRITTEN_BLOCKER]},
        ),
        project_root=bootstrap_repository.project_root,
    )
    block_branch(
        SECOND_ITEM_BRANCH,
        owner=OWNER,
        reason=CONFLICT_REASON,
        project_root=bootstrap_repository.project_root,
    )

    unblock_branch(
        SECOND_ITEM_BRANCH,
        owner=OWNER,
        project_root=bootstrap_repository.project_root,
    )

    assert (
        published_items(bootstrap_repository)[SECOND_ITEM][ManifestKey.STATUS.key]
        == ItemStatus.BLOCKED.value
    )


def test_clearing_the_last_blocker_returns_the_item_to_in_progress(
    bootstrap_repository: ScratchRepository,
):
    publish_the_branch_index(bootstrap_repository)
    block_branch(
        SECOND_ITEM_BRANCH,
        owner=OWNER,
        reason=CONFLICT_REASON,
        project_root=bootstrap_repository.project_root,
    )

    unblock_branch(
        SECOND_ITEM_BRANCH,
        owner=OWNER,
        project_root=bootstrap_repository.project_root,
    )

    item = published_items(bootstrap_repository)[SECOND_ITEM]
    assert item[ManifestKey.STATUS.key] == ItemStatus.IN_PROGRESS.value
    assert item[ManifestKey.BLOCKERS.key] == []


def test_withdrawing_a_blocker_an_item_never_carried_leaves_it_alone(
    bootstrap_repository: ScratchRepository,
):
    """
    A pass withdraws its blocker from every branch it finds clean, most of which it
    never blocked - writing each of those an empty list would spread noise across the
    whole manifest one run at a time.
    """
    publish_the_branch_index(bootstrap_repository)
    before = published_plan(bootstrap_repository)[PlanDocument.MANIFEST]

    report = unblock_branch(
        SECOND_ITEM_BRANCH,
        owner=OWNER,
        project_root=bootstrap_repository.project_root,
    )

    assert [item.item_identifier for item in report.items] == [SECOND_ITEM]
    assert published_plan(bootstrap_repository)[PlanDocument.MANIFEST] == before


def test_unblocking_a_branch_no_plan_claims_writes_nothing(
    bootstrap_repository: ScratchRepository,
):
    publish_the_branch_index(bootstrap_repository)
    before = published_plan(bootstrap_repository)[PlanDocument.MANIFEST]

    report = unblock_branch(
        "claude/belongs-to-nothing",
        owner=OWNER,
        project_root=bootstrap_repository.project_root,
    )

    assert report.exit_code is ExitCode.BRANCH_TRACKS_NO_ITEM
    assert published_plan(bootstrap_repository)[PlanDocument.MANIFEST] == before


# %% the vocabulary the manifest is written in


def test_a_rendered_field_line_matches_how_a_real_manifest_writes_it():
    """
    The renderer's indentation and spacing have to match a manifest written by hand,
    since every other test compares the two.
    """
    assert (
        manifest_line(ManifestKey.STATUS, ItemStatus.NOT_STARTED.value) in PLAN_MANIFEST
    )
    assert manifest_line(ManifestKey.TRACK, "a-track") in PLAN_MANIFEST


def test_a_key_quotes_its_own_value_when_its_style_says_to():
    """
    Quoting is the key's to decide, so no caller has to know that a title is prose and a
    track is a bare identifier.
    """
    assert ManifestKey.TITLE.render("A brand new item").endswith(
        ': "A brand new item"\n'
    )
    assert ManifestKey.TRACK.render("a-track").endswith(": a-track\n")
    assert ManifestKey.TITLE.style is ValueStyle.DOUBLE_QUOTED
    assert ManifestKey.TRACK.style is ValueStyle.PLAIN


def test_every_key_is_a_specification_in_its_own_right():
    """
    Mixing the specification into the enum is what lets a key carry its style without a
    lookup beside it, so the relationship is asserted rather than assumed.
    """
    assert issubclass(ManifestKey, KeySpecification)
    assert all(
        isinstance(manifest_key, KeySpecification) for manifest_key in ManifestKey
    )


def test_every_key_was_declared_as_specification_arguments():
    """
    A member declared as a built ``KeySpecification`` rather than as its argument tuple
    is accepted silently by the enum machinery and lands the whole instance in ``key``.

    This is what catches that.
    """
    assert all(isinstance(manifest_key.key, str) for manifest_key in ManifestKey)
    assert all(
        isinstance(manifest_key.style, ValueStyle) for manifest_key in ManifestKey
    )


def test_a_key_indexes_a_parsed_manifest_by_the_string_it_names():
    """
    A key reads parsed YAML through its own ``key``, which is the manifest's own
    spelling of it.
    """
    item = yaml.safe_load(PLAN_MANIFEST)[ManifestKey.ITEMS.key][0]
    assert item[ManifestKey.IDENTIFIER.key] == EXISTING_ITEM
    assert item[ManifestKey.STATUS.key] == ItemStatus.NOT_STARTED


def test_the_plans_directory_matches_the_shell_configuration_that_owns_it(
    bootstrap_repository: ScratchRepository,
):
    """
    ``PLANS_DIRECTORY`` mirrors ``PLANS_DIR`` in the shell configuration; this is what
    stops the mirror drifting, since the two are edited in different files.
    """
    resolved = subprocess.run(
        [
            "bash",
            "-c",
            f'source "{HookScript.CONFIGURATION.path}" && '
            'printf "%s\\n%s\\n" "${PLANS_DIR}" "$(plan_manifest_path "$1")"',
            "test",
            PLAN_IDENTIFIER,
        ],
        cwd=bootstrap_repository.project_root,
        capture_output=True,
        text=True,
        check=True,
    )
    plans_directory, manifest_path = resolved.stdout.strip().split("\n")
    assert plans_directory == PLANS_DIRECTORY
    assert manifest_path == PlanDocument.MANIFEST.path_within_notes_branch(
        PLAN_IDENTIFIER
    )


def test_only_the_keys_whose_values_run_over_lines_are_block_styled():
    assert BLOCK_STYLED_KEYS == {ManifestKey.NOTES, ManifestKey.BLOCKERS}


# %% exit statuses


def test_every_exit_code_names_itself_from_its_own_member():
    for exit_code in ExitCode:
        assert exit_code.name_for_a_caller == exit_code.name.lower()


def test_each_refusal_carries_its_own_exit_code():
    codes = {
        UnknownPlanError: ExitCode.UNKNOWN_PLAN,
        UnknownItemError: ExitCode.UNKNOWN_ITEM,
        bastler.plan_item_bootstrap.IncompleteNewItemError: ExitCode.INCOMPLETE_NEW_ITEM,
        bastler.plan_item_bootstrap.BranchAlreadyPublishedError: (
            ExitCode.BRANCH_ALREADY_PUBLISHED
        ),
        bastler.plan_item_bootstrap.PullRequestDetailsMissingError: (
            ExitCode.PULL_REQUEST_DETAILS_MISSING
        ),
        bastler.plan_item_bootstrap.PullRequestRefusedError: ExitCode.PULL_REQUEST_REFUSED,
    }
    assert {error: error.exit_code for error in codes} == codes


def test_a_refusal_composes_its_message_from_its_own_fields():
    refusal = UnknownItemError(
        plan_identifier=PLAN_IDENTIFIER, item_identifier="no-such-item"
    )
    assert refusal.error_message() in str(refusal)
    assert refusal.suggest_correction() in str(refusal)


# %% the command line


def run_bootstrap(
    repository: ScratchRepository, *arguments: str
) -> subprocess.CompletedProcess[str]:
    """
    Run the scratch layout's copy of this module with *arguments*.

    :param repository: A fixture-built scratch repository.
    :param arguments: CLI arguments to pass.
    :return: The finished subprocess.
    """
    return PythonModuleRunner(
        project_root=repository.project_root, module_name=BOOTSTRAP_MODULE
    ).run(*arguments)


def record_arguments(section: Path, plan: str = PLAN_IDENTIFIER) -> list[str]:
    """
    The command line for recording the existing item.

    :param section: The roadmap section to append.
    :param plan: The plan to record against.
    :return: The arguments.
    """
    return [
        "record",
        "--plan",
        plan,
        "--item",
        EXISTING_ITEM,
        "--status",
        ItemStatus.IN_PROGRESS.value,
        "--roadmap-section",
        str(section),
    ]


def test_the_record_subcommand_reports_status_and_exit_code_first(
    bootstrap_repository: ScratchRepository,
):
    section = roadmap_section(bootstrap_repository, "## From the command line\n")

    result = run_bootstrap(bootstrap_repository, *record_arguments(section))

    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    assert list(report)[:2] == ["status", "exit_code"]
    assert report["status"] == ExitCode.SUCCESS.name_for_a_caller
    assert report["exit_code"] == 0


def test_the_update_subcommand_writes_a_note_from_a_file(
    bootstrap_repository: ScratchRepository,
):
    note = bootstrap_repository.write("note.md", "What the run found.\n")

    result = run_bootstrap(
        bootstrap_repository,
        "update",
        "--plan",
        PLAN_IDENTIFIER,
        "--item",
        EXISTING_ITEM,
        "--status",
        ItemStatus.BLOCKED.value,
        "--notes",
        str(note),
    )

    assert result.returncode == 0, result.stderr
    item = published_item(bootstrap_repository)
    assert item[ManifestKey.NOTES.key] == "What the run found.\n"
    assert item[ManifestKey.STATUS.key] == ItemStatus.BLOCKED.value


def test_the_check_subcommand_exits_stale_and_names_the_field(
    bootstrap_repository: ScratchRepository,
):
    update_item(
        update_request(values_by_key={ManifestKey.BRANCH: NEW_BRANCH}),
        project_root=bootstrap_repository.project_root,
    )

    result = run_bootstrap(
        bootstrap_repository,
        "check",
        "--plan",
        PLAN_IDENTIFIER,
        "--item",
        EXISTING_ITEM,
    )

    assert result.returncode == ExitCode.MANIFEST_IS_STALE
    report = json.loads(result.stdout)
    assert list(report)[:2] == ["status", "exit_code"]
    assert report["status"] == ExitCode.MANIFEST_IS_STALE.name_for_a_caller
    assert [finding["field"] for finding in report["findings"]] == [
        ManifestKey.BRANCH.key
    ]


def test_the_command_line_names_the_status_it_failed_with(
    bootstrap_repository: ScratchRepository,
):
    section = roadmap_section(bootstrap_repository, "## Section\n")

    result = run_bootstrap(
        bootstrap_repository, *record_arguments(section, plan="no-such-plan")
    )

    assert result.returncode == ExitCode.UNKNOWN_PLAN
    assert ExitCode.UNKNOWN_PLAN.name_for_a_caller in result.stderr


def test_the_dashboard_republish_is_handed_back_rather_than_attempted(
    bootstrap_repository: ScratchRepository,
):
    section = roadmap_section(bootstrap_repository, "## Section\n")

    result = run_bootstrap(bootstrap_repository, *record_arguments(section))

    report = json.loads(result.stdout)
    assert report["dashboard_command"] == f"/plan-dashboard {PLAN_IDENTIFIER}"


def test_the_resolve_subcommand_names_the_plan_and_items_a_branch_carries(
    bootstrap_repository: ScratchRepository,
):
    publish_the_branch_index(bootstrap_repository)

    result = run_bootstrap(
        bootstrap_repository, "resolve", "--branch", SECOND_ITEM_BRANCH
    )

    assert result.returncode == ExitCode.SUCCESS
    report = json.loads(result.stdout)
    assert list(report)[:2] == ["status", "exit_code"]
    assert report["plan"] == PLAN_IDENTIFIER
    assert [item["item"] for item in report["items"]] == [SECOND_ITEM]


def test_the_block_subcommand_exits_on_a_branch_that_belongs_to_no_plan(
    bootstrap_repository: ScratchRepository,
):
    publish_the_branch_index(bootstrap_repository)
    reason = bootstrap_repository.write("reasons/conflict.md", CONFLICT_REASON)

    result = run_bootstrap(
        bootstrap_repository,
        "block",
        "--branch",
        "claude/belongs-to-nothing",
        "--owner",
        OWNER,
        "--reason",
        str(reason),
    )

    assert result.returncode == ExitCode.BRANCH_TRACKS_NO_ITEM
    assert json.loads(result.stdout)["plan"] is None


# %% the operations the command line offers


def test_every_operation_is_reachable_by_the_word_it_names():
    """
    A command is registered under its own :attr:`Subcommand.invoked_as`, so the parser
    cannot offer a word that reaches a different operation.
    """
    assert {
        word: type(subcommand).__name__
        for word, subcommand in plan_item_bootstrap.SUBCOMMANDS.items()
    } == {
        "record": "RecordSubcommand",
        "update": "UpdateSubcommand",
        "resolve": "ResolveSubcommand",
        "block": "BlockSubcommand",
        "unblock": "UnblockSubcommand",
        "check": "CheckSubcommand",
        "open": "OpenSubcommand",
        "repair": "RepairSubcommand",
    }


def test_a_command_that_names_no_word_of_its_own_cannot_be_built():
    """
    The name and description are abstract, so a subclass that supplies neither is
    refused when :data:`SUBCOMMANDS` instantiates it - as the module is imported, rather
    than when someone tries to invoke it.
    """

    class NamelessSubcommand(Subcommand):
        def add_arguments(self, parser):
            """
            Take no flags.

            :param parser: The subparser that would declare them.
            """

        def run(self, arguments, project_root):
            """
            Do nothing.

            :param arguments: The parsed command line.
            :param project_root: The repository to run within.
            """

    with pytest.raises(TypeError) as refusal:
        NamelessSubcommand()

    assert "invoked_as" in str(refusal.value)


def test_the_parser_takes_each_registered_word(
    bootstrap_repository: ScratchRepository,
):
    """
    The parser is built from the commands themselves, so a word the registry answers for
    is a word the command line accepts - one list rather than two that can disagree.
    """
    refusals = {
        word: run_bootstrap(bootstrap_repository, word, "--help").returncode
        for word in plan_item_bootstrap.SUBCOMMANDS
    }

    assert refusals == {word: 0 for word in plan_item_bootstrap.SUBCOMMANDS}


# %% seeing what a written note actually became


def test_a_written_note_reports_how_many_paragraphs_it_became(
    bootstrap_repository: ScratchRepository,
):
    """
    A file's paragraphs are whatever its blank lines say they are, so a caller who meant
    several and wrote none can only find out from the report.
    """
    report = update_item(
        update_request(values_by_key={ManifestKey.NOTES: "One.\n\nTwo.\n\nThree."}),
        project_root=bootstrap_repository.project_root,
    )

    assert report.note_paragraphs == 3


def test_an_addition_wrapped_without_blank_lines_counts_as_the_one_paragraph_it_is(
    bootstrap_repository: ScratchRepository,
):
    """
    The case that caught this session: continuously wrapped prose is one paragraph
    however many lines it occupies, and the report is the only place that says so
    before the dashboard shows it. The fixture item already carries a note, so an
    addition meant as two paragraphs and written as one leaves two, not three.
    """
    report = update_item(
        update_request(
            notes_to_append="Meant as two paragraphs\nbut wrapped without a blank line."
        ),
        project_root=bootstrap_repository.project_root,
    )

    assert report.note_paragraphs == 2


def test_a_write_that_sets_no_note_reports_no_paragraph_count(
    bootstrap_repository: ScratchRepository,
):
    report = update_item(
        update_request(values_by_key={ManifestKey.STATUS: ItemStatus.BLOCKED}),
        project_root=bootstrap_repository.project_root,
    )

    assert report.note_paragraphs is None


# %% repairing words an earlier wrap broke


EVIDENCED_COMPOUND = "the plan-item-kickoff skill"
"""
Text proving ``plan-item`` is a word somebody wrote, which is what makes rejoining a
break in it safe.
"""


def test_a_break_in_a_word_written_elsewhere_is_rejoined():
    repaired, candidates = repair_text(
        "the plan- item guard", corpus=EVIDENCED_COMPOUND
    )

    assert repaired == "the plan-item guard"
    assert [(word.broken, word.rejoined, word.repaired) for word in candidates] == [
        ("plan- item", "plan-item", True)
    ]


def test_a_suspended_hyphen_is_reported_rather_than_rejoined():
    """
    ``network- and credential-free`` is correct English, and shares its shape with a
    broken word - so the rule has to leave it alone rather than edit somebody's prose.
    """
    repaired, candidates = repair_text(
        "all network- and credential-free", corpus=EVIDENCED_COMPOUND
    )

    assert repaired == "all network- and credential-free"
    assert [(word.rejoined, word.repaired) for word in candidates] == [
        ("network-and", False)
    ]


def test_repairing_a_plan_rejoins_the_evidenced_break_and_leaves_the_other(
    bootstrap_repository: ScratchRepository,
):
    update_item(
        update_request(
            values_by_key={
                ManifestKey.NOTES: (
                    f"{EVIDENCED_COMPOUND} broke as plan- item here, "
                    "and all network- and credential-free stayed as written."
                )
            }
        ),
        project_root=bootstrap_repository.project_root,
    )

    report = plan_item_bootstrap.repair_plan(
        PLAN_IDENTIFIER, project_root=bootstrap_repository.project_root
    )

    note = published_item(bootstrap_repository)[ManifestKey.NOTES.key]
    assert "plan-item here" in note
    assert "network- and credential-free" in note
    assert [word.rejoined for word in report.left_for_a_person] == ["network-and"]


def test_a_plan_whose_notes_are_whole_repairs_nothing_and_exits_clean(
    bootstrap_repository: ScratchRepository,
):
    report = plan_item_bootstrap.repair_plan(
        PLAN_IDENTIFIER, project_root=bootstrap_repository.project_root
    )

    assert report.words_by_item == {}
    assert report.exit_code == ExitCode.SUCCESS


def test_a_break_left_for_a_person_is_its_own_exit_status(
    bootstrap_repository: ScratchRepository,
):
    """
    A partial repair must not read as a clean one to a caller acting on the status.
    """
    update_item(
        update_request(
            values_by_key={ManifestKey.NOTES: "all network- and credential-free"}
        ),
        project_root=bootstrap_repository.project_root,
    )

    report = plan_item_bootstrap.repair_plan(
        PLAN_IDENTIFIER, project_root=bootstrap_repository.project_root
    )

    assert report.exit_code == ExitCode.TEXT_NEEDS_REPAIR
