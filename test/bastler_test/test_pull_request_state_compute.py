"""
Tests for the compute half of :mod:`bastler.pull_request_state`.

Reducing a check rollup to one conclusion, finding the session link a description
carries, and classifying a change's size. Pure functions of their inputs - no git, no
network.
"""

from __future__ import annotations

from typing import Any

import pytest

from bastler.pull_request_state import (
    ChangeSize,
    CheckConclusion,
    CheckRollup,
    CheckRunField,
    CheckState,
    ClaudeSessionLink,
)

# %% check rollup reduction


def rollup_of(*checks: dict[str, Any]) -> CheckRollup:
    """
    :param checks: One mapping per check, in either response dialect.
    :return: The rollup over them.
    """
    return CheckRollup.from_response({CheckRunField.CHECK_RUNS: list(checks)})


def test_no_checks_reduce_to_no_conclusion():
    assert rollup_of().conclusion is None


def test_all_successful_checks_reduce_to_success():
    rollup = rollup_of(
        {CheckRunField.CONCLUSION: CheckConclusion.SUCCESS.value},
        {CheckRunField.CONCLUSION: CheckConclusion.SUCCESS.value},
    )
    assert rollup.conclusion is CheckConclusion.SUCCESS


@pytest.mark.parametrize("failure_state", sorted(CheckRollup.FAILURE_STATES))
def test_one_failed_check_reduces_the_rollup_to_failure(failure_state: CheckState):
    rollup = rollup_of(
        {CheckRunField.CONCLUSION: CheckConclusion.SUCCESS.value},
        {CheckRunField.CONCLUSION: failure_state.lower()},
    )
    assert rollup.conclusion is CheckConclusion.FAILURE


@pytest.mark.parametrize("pending_state", sorted(CheckRollup.PENDING_STATES))
def test_an_unfinished_check_reduces_a_failure_free_rollup_to_pending(
    pending_state: CheckState,
):
    rollup = rollup_of(
        {CheckRunField.CONCLUSION: CheckConclusion.SUCCESS.value},
        {CheckRunField.CONCLUSION: None, CheckRunField.STATUS: pending_state.lower()},
    )
    assert rollup.conclusion is CheckConclusion.PENDING


def test_a_failure_outranks_a_pending_check():
    rollup = rollup_of(
        {
            CheckRunField.CONCLUSION: None,
            CheckRunField.STATUS: CheckState.QUEUED.lower(),
        },
        {CheckRunField.CONCLUSION: CheckState.FAILURE.lower()},
    )
    assert rollup.conclusion is CheckConclusion.FAILURE


def test_the_graphql_dialect_state_key_is_read_too():
    rollup = rollup_of({CheckRunField.STATE: CheckState.ERROR})
    assert rollup.conclusion is CheckConclusion.FAILURE


# %% session link

SESSION = ClaudeSessionLink("01AbCdEf")
"""
The session a description is written to reference.
"""

LATER_SESSION = ClaudeSessionLink("second")
"""
A second session mentioned after the first.
"""


def test_the_session_link_is_found_in_a_description():
    body = f"Some description.\n\nSession: {SESSION.url}\n"
    assert ClaudeSessionLink.first_in(body) == SESSION


def test_a_description_without_a_session_link_parses_to_none():
    assert ClaudeSessionLink.first_in("No links here.") is None


def test_the_first_of_several_session_links_wins():
    body = f"{SESSION.url} and later {LATER_SESSION.url}"
    assert ClaudeSessionLink.first_in(body) == SESSION


def test_a_link_round_trips_through_its_url():
    assert ClaudeSessionLink.first_in(SESSION.url).url == SESSION.url


# %% change size


def test_a_change_under_the_threshold_is_short():
    assert ChangeSize(ChangeSize.SHORT_CHANGE_THRESHOLD - 1, 0).is_short is True


def test_a_change_at_the_threshold_is_short():
    assert ChangeSize(ChangeSize.SHORT_CHANGE_THRESHOLD, 0).is_short is True


def test_a_change_over_the_threshold_is_not_short():
    assert ChangeSize(ChangeSize.SHORT_CHANGE_THRESHOLD, 1).is_short is False


def test_lines_changed_counts_both_kinds():
    assert ChangeSize(3, 4).lines_changed == 7
