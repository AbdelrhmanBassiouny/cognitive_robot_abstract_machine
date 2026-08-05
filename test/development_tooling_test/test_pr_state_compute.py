"""
Tests for the pure compute half of :mod:`development_tooling.pr_state`: reducing a check
rollup to one conclusion, parsing a session link from a pull request body, classifying a
change's size, and serializing one pull request's live state into the two consumer
document shapes (``board.json`` and ``pr_data.json``).
"""

from __future__ import annotations

from development_tooling.pr_state import (
    DEFAULT_SHORT_CHANGE_THRESHOLD,
    CheckConclusion,
    PullRequestLiveState,
    PullRequestState,
    board_document,
    check_conclusion,
    is_short_change,
    parse_session_url,
    pull_request_data_document,
)

# %% check rollup reduction


def test_empty_rollup_has_no_conclusion():
    assert check_conclusion([]) is None


def test_all_successful_checks_reduce_to_success():
    checks = [{"conclusion": "success"}, {"conclusion": "SUCCESS"}]
    assert check_conclusion(checks) == CheckConclusion.SUCCESS


def test_any_failed_check_reduces_to_failure():
    checks = [{"conclusion": "success"}, {"conclusion": "failure"}]
    assert check_conclusion(checks) == CheckConclusion.FAILURE


def test_failure_wins_over_pending():
    checks = [{"status": "in_progress"}, {"conclusion": "cancelled"}]
    assert check_conclusion(checks) == CheckConclusion.FAILURE


def test_running_checks_reduce_to_pending():
    checks = [{"conclusion": "success"}, {"status": "queued"}]
    assert check_conclusion(checks) == CheckConclusion.PENDING


def test_check_with_no_recorded_state_counts_as_pending():
    assert check_conclusion([{}]) == CheckConclusion.PENDING


def test_github_graphql_style_state_key_is_read_too():
    checks = [{"state": "ERROR"}]
    assert check_conclusion(checks) == CheckConclusion.FAILURE


# %% session-link parse


def test_session_url_is_extracted_from_body():
    body = "Some description.\n\nSession: https://claude.ai/code/session_01AbCdEf\n"
    assert parse_session_url(body) == "https://claude.ai/code/session_01AbCdEf"


def test_body_without_session_url_parses_to_none():
    assert parse_session_url("No links here.") is None


def test_first_of_multiple_session_urls_wins():
    body = (
        "https://claude.ai/code/session_first and later "
        "https://claude.ai/code/session_second"
    )
    assert parse_session_url(body) == "https://claude.ai/code/session_first"


# %% change-size classification


def test_change_under_threshold_is_short():
    assert is_short_change(DEFAULT_SHORT_CHANGE_THRESHOLD - 1) is True


def test_change_at_threshold_is_short():
    assert is_short_change(DEFAULT_SHORT_CHANGE_THRESHOLD) is True


def test_change_over_threshold_is_not_short():
    assert is_short_change(DEFAULT_SHORT_CHANGE_THRESHOLD + 1) is False


def test_explicit_threshold_overrides_default():
    assert is_short_change(10, threshold=9) is False


# %% live-state dataclass


def make_live_state() -> PullRequestLiveState:
    return PullRequestLiveState(
        number=7,
        head="feature-branch",
        base="main",
        state=PullRequestState.OPEN,
        draft=True,
        merged_at=None,
        labels=["bug"],
        ci=CheckConclusion.SUCCESS,
        additions=120,
        deletions=30,
        mergeable=True,
        session_url="https://claude.ai/code/session_01AbCdEf",
    )


def test_lines_changed_sums_additions_and_deletions():
    assert make_live_state().lines_changed == 150


def test_lines_changed_is_unknown_without_diff_counts():
    state = make_live_state()
    state.additions = None
    assert state.lines_changed is None


# %% board.json serialization


def test_board_entry_matches_the_stack_tool_contract():
    assert make_live_state().to_board_entry() == {
        "number": 7,
        "head": "feature-branch",
        "base": "main",
        "draft": True,
        "labels": ["bug"],
        "ci": "success",
        "session": "https://claude.ai/code/session_01AbCdEf",
    }


def test_board_document_wraps_all_entries():
    state = make_live_state()
    assert board_document([state]) == {"pull_requests": [state.to_board_entry()]}


# %% pr_data.json serialization


def test_pull_request_data_entry_carries_the_chip_fields():
    assert make_live_state().to_pull_request_data_entry() == {
        "state": "open",
        "draft": True,
        "merged_at": None,
        "labels": ["bug"],
        "ci": "success",
        "additions": 120,
        "deletions": 30,
        "mergeable": True,
        "session_url": "https://claude.ai/code/session_01AbCdEf",
    }


def test_pull_request_data_document_is_keyed_by_repository_then_number():
    state = make_live_state()
    document = pull_request_data_document([state], "owner/repository")
    assert document == {"owner/repository": {"7": state.to_pull_request_data_entry()}}
