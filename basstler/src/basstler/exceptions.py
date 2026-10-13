"""
Every refusal the package raises.

..note:: Imports nothing outside the standard library and :mod:`krrood_core`'s
    standard-library modules, since :mod:`basstler.dependencies` raises from here before
    anything is installed.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from krrood_core.class_property import classproperty
from krrood_core.exceptions import DataclassException

from basstler.exit_codes import PlanItemBootstrapExitCode, PlanItemModeExitCode
from basstler.locations import ProjectLocation
from basstler.plan_item_execution import ExecutionMode

if TYPE_CHECKING:
    from basstler.build_dashboard import ValidationProblem
    from basstler.maintenance_board import PullRequestField
    from basstler.plan_item_bootstrap import ManifestKey
    from basstler.plan_item_mode import ModeSetting, SettingsFile
    from basstler.repository import Repository
    from basstler.stack import Remote


# %% plan manifests


@dataclass
class PlanValidationError(DataclassException):
    """
    Raised when a plan.yaml fails schema validation - see plan-schema.md.
    """

    problems: list[ValidationProblem]
    """
    Every problem found, rather than only the first.
    """

    def error_message(self) -> str:
        return "; ".join(problem.error_message() for problem in self.problems)

    def suggest_correction(self) -> str:
        return ""


@dataclass
class YamlBooleanCoercionError(DataclassException, ValueError):
    """
    Raised when a plan.yaml field that must be a string was parsed as a ``bool``
    instead, as PyYAML's YAML 1.1 resolver does with bare tokens like ``no``, ``yes``,
    ``on`` and ``off``.
    """

    manifest_path: object
    """
    The manifest the field was read from.
    """

    field_name: str
    """
    The field that was coerced.
    """

    value: bool
    """
    The boolean the field's text was read as.
    """

    def error_message(self) -> str:
        return (
            f"{self.manifest_path}: field {self.field_name!r} was parsed as the boolean "
            f"{self.value!r} instead of a string"
        )

    def suggest_correction(self) -> str:
        return (
            f'Quote its value in plan.yaml (e.g. {self.field_name}: "no") to avoid '
            "PyYAML's YAML 1.1 bare-token coercion."
        )


@dataclass
class MissingStatusLineError(DataclassException, ValueError):
    """
    Raised when an item slated for correction has no ``status:`` line in its manifest
    block, so the manifest text and the parsed data have gone out of sync.
    """

    item_identifier: str
    """
    The item whose status could not be corrected.
    """

    def error_message(self) -> str:
        return f"item {self.item_identifier!r} has no status: line to correct"

    def suggest_correction(self) -> str:
        return ""


# %% pull request data


@dataclass
class MissingMergeTimestampError(DataclassException, ValueError):
    """
    Raised when a closed pull request's ``pr_data.json`` entry omits the ``merged_at``
    key altogether, which leaves no way to tell a merged pull request from one closed
    unmerged.
    """

    def error_message(self) -> str:
        return "a closed pull request entry must carry merged_at (null included)"

    def suggest_correction(self) -> str:
        return ""


@dataclass
class MalformedPullRequestDataError(DataclassException, ValueError):
    """
    Raised when one entry of ``pr_data.json`` cannot be parsed into a pull request
    record.
    """

    repository: str
    """
    The repository the entry is listed under.
    """

    pull_request_number: str
    """
    The pull request the entry describes, as ``pr_data.json`` keys it.
    """

    detail: str
    """
    What was wrong with the entry.
    """

    def error_message(self) -> str:
        return f"{self.repository}#{self.pull_request_number}: {self.detail}"

    def suggest_correction(self) -> str:
        return ""


@dataclass
class SummaryKeyCollisionError(DataclassException, ValueError):
    """
    Raised when the manifest sync's and the dashboard build's printed summaries share a
    key, so merging them would overwrite one with the other.
    """

    shared_keys: tuple[str, ...]
    """
    The keys both summaries carry.
    """

    def error_message(self) -> str:
        return (
            f"sync and build summaries share key(s): {', '.join(self.shared_keys)}"
        )

    def suggest_correction(self) -> str:
        return ""


# %% the package's own declaration


@dataclass
class UnreadableDependencyDeclarationError(DataclassException):
    """
    Raised when the declaration cannot be read, so nothing can be said about what is
    missing.

    Distinct from *nothing is missing*, which is what a caller would otherwise conclude
    from an empty answer and act on by installing nothing.
    """

    declaration: Path
    """
    The file that was to be read.
    """

    def error_message(self) -> str:
        return (
            f"{self.declaration} does not exist, so this package's dependencies cannot "
            f"be read"
        )

    def suggest_correction(self) -> str:
        return ""


# %% repositories and remotes


@dataclass
class MalformedRepositoryError(DataclassException, ValueError):
    """
    Raised when a repository reference is not in ``owner/name`` form.
    """

    text: str
    """
    The value that could not be parsed.
    """

    def error_message(self) -> str:
        return f"expected a repository as 'owner/name', got {self.text!r}"

    def suggest_correction(self) -> str:
        return ""


@dataclass
class ForkRemoteNotFoundError(DataclassException, LookupError):
    """
    Raised when no remote points at a repository other than the upstream.
    """

    upstream_repository: Repository
    """
    The upstream every candidate turned out to be.
    """

    def error_message(self) -> str:
        return (
            f"no remote points at a fork: every remote is {self.upstream_repository}."
        )

    def suggest_correction(self) -> str:
        return "Add a remote for your fork, or set fork_repository in stack.toml."


@dataclass
class AmbiguousForkRemoteError(DataclassException, LookupError):
    """
    Raised when several remotes could each be the fork.
    """

    candidates: tuple[Remote, ...]
    """
    The remotes that are not the upstream, in the order git reported them.
    """

    def error_message(self) -> str:
        listed = ", ".join(
            f"{remote.name} -> {remote.repository}" for remote in self.candidates
        )
        return f"several remotes could be the fork ({listed})."

    def suggest_correction(self) -> str:
        return "Set fork_repository in stack.toml to say which."


@dataclass
class UnknownBranchError(DataclassException, ValueError):
    """
    Raised when a requested base or candidate branch doesn't resolve in the repository.
    """

    git_command: str
    """
    The git command that failed.
    """

    result_stderr: str
    """
    The git error message.
    """

    def error_message(self) -> str:
        return f"git {self.git_command} failed: {self.result_stderr}"

    def suggest_correction(self) -> str:
        return ""


@dataclass
class MalformedCandidateError(DataclassException, ValueError):
    """
    Raised when a ``--candidate`` argument isn't in ``<label>=<branch>`` form.
    """

    expected_candidate: str
    """
    The expected format.
    """

    wrong_candidate: str
    """
    The argument that failed to parse.
    """

    def error_message(self) -> str:
        return f"expected {self.expected_candidate!r}, got {self.wrong_candidate!r}"

    def suggest_correction(self) -> str:
        return ""


# %% calls to git and GitHub


@dataclass
class ExternalCallFailed(DataclassException, RuntimeError, ABC):
    """
    Base for a call to git or GitHub that a pass depended on and did not get.

    Both carry the same three things under different names - what was called, the
    status it came back with, and what it said - and differ only in how they name the
    call.
    """

    status: int
    """
    The status the call came back with.
    """

    detail: str
    """
    What the far side said about it.
    """

    @property
    @abstractmethod
    def call(self) -> str:
        """
        :return: The call that failed, named the way its own caller named it.
        """

    def error_message(self) -> str:
        return f"{self.call} failed with {self.status}: {self.detail}"

    def suggest_correction(self) -> str:
        return ""


@dataclass
class GitCommandFailed(ExternalCallFailed):
    """
    Raised when a git command a pass depends on the result of fails.
    """

    arguments: tuple[str, ...] = ()
    """
    The git subcommand and its arguments, as invoked.
    """

    @property
    def call(self) -> str:
        return f"git {' '.join(self.arguments)}"


@dataclass
class GitHubRequestFailed(ExternalCallFailed):
    """
    Raised when the API refuses a call a pass depends on.
    """

    method: str = ""
    """
    The HTTP method used.
    """

    path: str = ""
    """
    The API path called, without the host.
    """

    @property
    def call(self) -> str:
        return f"{self.method} {self.path}"


@dataclass
class GitHubCredentialUnavailableError(DataclassException, RuntimeError):
    """
    Raised when no token is available to authenticate the API calls with.
    """

    variables: tuple[str, ...]
    """
    The environment variables that were consulted.
    """

    def error_message(self) -> str:
        return f"no GitHub token: none of {', '.join(self.variables)} is set"

    def suggest_correction(self) -> str:
        return "Set one of them, or run this with a caller that has one."


# %% the fork's board and stack


@dataclass
class BoardUnavailable(DataclassException, RuntimeError):
    """
    Raised when ``board.json`` is missing.
    """

    path: Path
    """
    Where the board was looked for.
    """

    def error_message(self) -> str:
        return f"{self.path.name} not found"

    def suggest_correction(self) -> str:
        return ""


@dataclass
class MissingPullRequestFieldError(DataclassException, ValueError):
    """
    Raised when a fetched pull request omits a field the board is derived from.

    A fetch that drops a field is not partially correct: absent and legitimately empty
    are different facts, and defaulting one to the other is what makes bad board data
    indistinguishable from good.
    """

    field_name: PullRequestField
    """
    The field that was absent.
    """

    pull_request_number: int | None
    """
    The pull request it was absent from, or ``None`` when the number itself is.
    """

    def error_message(self) -> str:
        subject = (
            f"pull request {self.pull_request_number}"
            if self.pull_request_number is not None
            else "a fetched pull request"
        )
        return (
            f"{subject} has no '{self.field_name}'; the board cannot be derived from a "
            f"fetch that omits it"
        )

    def suggest_correction(self) -> str:
        return ""


@dataclass
class ContradictoryLabelWriteError(DataclassException, ValueError):
    """
    Raised when one write is asked both to carry a label and to drop it.
    """

    labels: tuple[str, ...]
    """
    The labels asked for in both directions.
    """

    def error_message(self) -> str:
        return (
            f"cannot both add and remove {', '.join(self.labels)}: "
            f"either outcome would be a guess at what was meant"
        )

    def suggest_correction(self) -> str:
        return ""


@dataclass
class PromotionLinkTooLongError(DataclassException, ValueError):
    """
    Raised when a link cannot fit even with its whole description dropped.
    """

    branch: str
    """
    The branch whose link was being built.
    """

    length_without_a_description: int
    """
    How long the URL already is before any description is added.
    """

    url_character_limit: int
    """
    The longest URL the link may be.
    """

    def error_message(self) -> str:
        return (
            f"the compare link for {self.branch} is {self.length_without_a_description} "
            f"characters before its description, over the "
            f"{self.url_character_limit}-character limit"
        )

    def suggest_correction(self) -> str:
        return "Shorten the title."


@dataclass
class RestackConcludedNothingError(DataclassException, RuntimeError):
    """
    Raised when no step concluded a branch, which the last step always must.
    """

    branch: str
    """
    The branch left without an outcome.
    """

    def error_message(self) -> str:
        return f"no restack step concluded '{self.branch}'"

    def suggest_correction(self) -> str:
        return ""


# %% opening and recording plan items


@dataclass
class BootstrapError(DataclassException, ABC):
    """
    Base for every refusal :mod:`basstler.plan_item_bootstrap` reports, each carrying
    its own exit status.
    """

    @classproperty
    @abstractmethod
    def exit_code(cls) -> PlanItemBootstrapExitCode:
        """
        The process status this refusal exits with.
        """


@dataclass
class UnknownPlanError(BootstrapError):
    """
    Raised when the named plan has no manifest on the personal-notes branch.
    """

    plan_identifier: str
    """
    The plan that could not be found.
    """

    manifest_path: str
    """
    Where its manifest was looked for.
    """

    @classproperty
    def exit_code(cls) -> PlanItemBootstrapExitCode:
        return PlanItemBootstrapExitCode.UNKNOWN_PLAN

    def error_message(self) -> str:
        return (
            f"no plan {self.plan_identifier!r} on the personal-notes branch "
            f"({self.manifest_path} is not there)"
        )

    def suggest_correction(self) -> str:
        return "Run /plan-create to bootstrap it, or check the plan id for a typo."


@dataclass
class UnknownItemError(BootstrapError, LookupError):
    """
    Raised when the named item is absent from an otherwise resolvable plan.
    """

    plan_identifier: str
    """
    The plan that was searched.
    """

    item_identifier: str
    """
    The item that is not in it.
    """

    @classproperty
    def exit_code(cls) -> PlanItemBootstrapExitCode:
        return PlanItemBootstrapExitCode.UNKNOWN_ITEM

    def error_message(self) -> str:
        return f"no item {self.item_identifier!r} in plan {self.plan_identifier!r}"

    def suggest_correction(self) -> str:
        return (
            "Record the item first - /add-plan-item decides where new work belongs, and "
            "this tool's record operation writes the entry."
        )


@dataclass
class IncompleteNewItemError(BootstrapError):
    """
    Raised when an item that does not exist yet is recorded without the fields needed to
    write its entry.
    """

    item_identifier: str
    """
    The item that would have been created.
    """

    missing_keys: tuple[ManifestKey, ...]
    """
    The keys a new entry cannot omit that were not supplied.
    """

    @classproperty
    def exit_code(cls) -> PlanItemBootstrapExitCode:
        return PlanItemBootstrapExitCode.INCOMPLETE_NEW_ITEM

    def error_message(self) -> str:
        missing = ", ".join(manifest_key.key for manifest_key in self.missing_keys)
        return (
            f"item {self.item_identifier!r} is not in the plan yet, so recording it "
            f"needs {missing}"
        )

    def suggest_correction(self) -> str:
        return "Pass " + " and ".join(
            f"--{manifest_key.key.replace('_', '-')}"
            for manifest_key in self.missing_keys
        )


@dataclass
class BranchAlreadyPublishedError(BootstrapError):
    """
    Raised when the branch to open already exists on the remote, which means work is
    underway and overwriting it would discard someone's commits.
    """

    branch: str
    """
    The branch that is already published.
    """

    remote: str
    """
    The remote carrying it.
    """

    @classproperty
    def exit_code(cls) -> PlanItemBootstrapExitCode:
        return PlanItemBootstrapExitCode.BRANCH_ALREADY_PUBLISHED

    def error_message(self) -> str:
        return (
            f"branch {self.branch!r} already exists on {self.remote!r} - it is already "
            "being worked, and republishing it would discard those commits"
        )

    def suggest_correction(self) -> str:
        return (
            "Pass --pull-request-number if its pull request already exists, or choose a "
            "branch name that is not taken."
        )


@dataclass
class PullRequestDetailsMissingError(BootstrapError):
    """
    Raised when opening the work must create a pull request but was given nothing to
    create it from.
    """

    item_identifier: str
    """
    The item whose work was being opened.
    """

    @classproperty
    def exit_code(cls) -> PlanItemBootstrapExitCode:
        return PlanItemBootstrapExitCode.PULL_REQUEST_DETAILS_MISSING

    def error_message(self) -> str:
        return (
            f"opening {self.item_identifier!r} has to create a pull request, but was "
            "given neither a title nor a body to create one from"
        )

    def suggest_correction(self) -> str:
        return (
            "Pass --pull-request-number for one you already created - which keeps your "
            "identity on it - or --pull-request-title and --pull-request-body."
        )


@dataclass
class PullRequestRefusedError(BootstrapError):
    """
    Raised when the remote declines to create the pull request.
    """

    detail: str
    """
    What the remote said.
    """

    @classproperty
    def exit_code(cls) -> PlanItemBootstrapExitCode:
        return PlanItemBootstrapExitCode.PULL_REQUEST_REFUSED

    def error_message(self) -> str:
        return f"the remote refused to create the pull request: {self.detail}"

    def suggest_correction(self) -> str:
        return (
            "The branch is published, so create the pull request yourself and re-run "
            "with --pull-request-number."
        )


@dataclass
class NotesBranchUnavailableError(BootstrapError):
    """
    Raised when the personal-notes branch cannot be fetched, so there is no plan data to
    read or write.
    """

    detail: str
    """
    Why the fetch failed.
    """

    @classproperty
    def exit_code(cls) -> PlanItemBootstrapExitCode:
        return PlanItemBootstrapExitCode.UNKNOWN_PLAN

    def error_message(self) -> str:
        return f"could not fetch the personal-notes branch: {self.detail}"

    def suggest_correction(self) -> str:
        return f"Run {ProjectLocation.PERSONAL_NOTES_BRANCH_CREATION_SCRIPT} first."


# %% plan item execution modes


@dataclass
class ModeError(DataclassException, ABC):
    """
    Base for every refusal :mod:`basstler.plan_item_mode` reports, each carrying its own
    exit status.

    Where one of these translates a library exception - ``ValueError`` from an enum,
    ``TOMLDecodeError`` from a parse - the refusal is raised ``from None``: everything the
    original said is already folded into these fields.
    """

    @classproperty
    @abstractmethod
    def exit_code(cls) -> PlanItemModeExitCode:
        """
        The process status this refusal exits with.
        """


@dataclass
class UnknownModeError(ModeError):
    """
    Raised when a mode is named that :class:`~basstler.plan_item_execution.ExecutionMode`
    does not define.
    """

    setting: ModeSetting
    """
    The setting whose value names no mode.
    """

    @classproperty
    def exit_code(cls) -> PlanItemModeExitCode:
        return PlanItemModeExitCode.UNKNOWN_MODE

    def error_message(self) -> str:
        return f"{self.setting.key}: {self.setting.value!r} is not an execution mode."

    def suggest_correction(self) -> str:
        return f"Use one of: {', '.join(ExecutionMode)}."


@dataclass
class MalformedModeSettingsError(ModeError):
    """
    Raised when a settings file exists but cannot be read as the modes it should hold.
    """

    file: SettingsFile
    """
    The settings file that could not be read.
    """

    detail: str
    """
    What was wrong with it.
    """

    @classproperty
    def exit_code(cls) -> PlanItemModeExitCode:
        return PlanItemModeExitCode.MALFORMED_MODE_SETTINGS

    def error_message(self) -> str:
        return f"{self.file.origin} could not be read: {self.detail}"

    def suggest_correction(self) -> str:
        return (
            "Fix the file, or delete it to fall back to "
            f"{ProjectLocation.PLAN_ITEM_MODE_DEFAULTS}'s defaults."
        )


@dataclass
class SettingsWriteRefusedError(ModeError):
    """
    Raised when the personal settings file could not be pushed to the notes branch.
    """

    detail: str
    """
    What the notes writer reported.
    """

    @classproperty
    def exit_code(cls) -> PlanItemModeExitCode:
        return PlanItemModeExitCode.SETTINGS_WRITE_REFUSED

    def error_message(self) -> str:
        return (
            f"{ProjectLocation.PERSONAL_PLAN_ITEM_MODES} was not written: {self.detail}"
        )

    def suggest_correction(self) -> str:
        return "Check the personal-notes branch is set up: run /setup-personal-notes."


# %% recording a dashboard's URL


@dataclass
class DashboardUrlError(DataclassException, ABC):
    """
    Base class for every refusal to record a dashboard URL.
    """


@dataclass
class MalformedArtifactUrlError(DashboardUrlError):
    """
    Raised when a supplied URL is not shaped like a published Artifact URL.
    """

    supplied_url: str
    """
    The URL the caller passed.
    """

    def error_message(self) -> str:
        return f"{self.supplied_url!r} is not a published Artifact URL."

    def suggest_correction(self) -> str:
        return (
            "Pass a URL of the form https://claude.ai/code/artifact/<uuid>, copied from "
            "the Artifact tool's listing."
        )


@dataclass
class ArtifactNotPublishedError(DashboardUrlError):
    """
    Raised when no artifact in the listing carries the expected title.
    """

    expected_title: str
    """
    The title the dashboard was expected to be published under.
    """

    def error_message(self) -> str:
        return f"No artifact in the listing is titled {self.expected_title!r}."

    def suggest_correction(self) -> str:
        return (
            "Publish the dashboard before recording its URL, and check the title "
            "matches the plan's own title exactly."
        )


@dataclass
class UnlistedArtifactUrlError(DashboardUrlError):
    """
    Raised when a supplied URL is not among the artifacts carrying the expected title -
    either invented, or belonging to some other plan.
    """

    supplied_url: str
    """
    The URL the caller chose.
    """

    expected_title: str
    """
    The title whose artifacts were the only permitted choices.
    """

    candidate_urls: list[str]
    """
    Every artifact URL carrying that title.
    """

    def error_message(self) -> str:
        return (
            f"{self.supplied_url} is not among the artifacts titled "
            f"{self.expected_title!r}."
        )

    def suggest_correction(self) -> str:
        return f"Choose one of: {', '.join(self.candidate_urls)}."


# %% reading upstream reviews


@dataclass
class UpstreamReviewError(DataclassException, ABC):
    """
    Base class for every failure reading an upstream pull request's reviews raises.
    """


@dataclass
class GitHubCommandFailed(UpstreamReviewError):
    """
    Raised when the ``gh`` invocation itself exits non-zero.
    """

    executable: str
    """
    The command that was run.
    """

    exit_code: int
    """
    The status it exited with.
    """

    error_output: str
    """
    Whatever it wrote to standard error.
    """

    def error_message(self) -> str:
        return f"{self.executable} exited {self.exit_code}: {self.error_output}"

    def suggest_correction(self) -> str:
        return ""


@dataclass
class GraphQLErrorsReturned(UpstreamReviewError):
    """
    Raised when GitHub answers with an ``errors`` array instead of data.
    """

    messages: list[str]
    """
    Every message GitHub reported.
    """

    def error_message(self) -> str:
        return "; ".join(self.messages)

    def suggest_correction(self) -> str:
        return ""


@dataclass
class UpstreamPullRequestNotFound(UpstreamReviewError):
    """
    Raised when a branch has no pull request open on the upstream.
    """

    branch: str
    """
    The fork branch that was looked up.
    """

    upstream: Repository
    """
    The repository that was searched.
    """

    fork_owner: str
    """
    The owner whose head branches were being claimed.
    """

    def error_message(self) -> str:
        return (
            f"no pull request on {self.upstream} has head "
            f"'{self.fork_owner}:{self.branch}' - the branch has most likely not "
            "been promoted upstream yet"
        )

    def suggest_correction(self) -> str:
        return ""
