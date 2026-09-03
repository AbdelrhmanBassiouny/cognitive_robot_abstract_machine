"""
Tests for the board-semantics chips on dashboard items: the CI, change-size and conflict
chips derived from the extended ``pr_data.json`` fields, the session-link fallback
parsed from the pull request body, and backward compatibility with pull request data
that predates those fields.
"""

from __future__ import annotations

from typing import Any

from bastler.build_dashboard import (
    BoardChip,
    ChipTone,
    DashboardRenderer,
    Item,
    ItemStatus,
    Plan,
    PullRequestLabel,
    PullRequestRecord,
    PullRequestsByRepository,
    Track,
    Wave,
)
from bastler.pull_request_state import (
    ChangeSize,
    CheckConclusion,
    ClaudeSessionLink,
    PullRequestDataKey,
    PullRequestState,
)

REPOSITORY = "owner/repo"
"""
The plan's default repository.
"""

PULL_REQUEST_NUMBER = 1
"""
The one item's pull request.
"""

PARSED_SESSION = ClaudeSessionLink("01AbCdEf")
"""
The session the pull request body names.
"""

MANIFEST_SESSION = ClaudeSessionLink("manifest")
"""
The session the manifest names, when it names one.
"""


def make_renderer(
    items: list[Item],
    pull_requests_by_repository: PullRequestsByRepository | None = None,
) -> DashboardRenderer:
    plan = Plan(
        id="test-plan",
        title="Test Plan",
        description="desc",
        default_repository=REPOSITORY,
        waves=[Wave(id="wave-1", name="Wave One")],
        tracks=[Track(id="track-1", name="Track One", wave="wave-1")],
        items=items,
    )
    return DashboardRenderer(
        plan=plan,
        roadmap_text="",
        pull_requests_by_repository=pull_requests_by_repository or {},
        tracking_url=None,
    )


def make_item(session: ClaudeSessionLink | None = None) -> Item:
    return Item(
        title="an item",
        branch="a-branch",
        track="track-1",
        status=ItemStatus.IN_PROGRESS,
        id="an-item",
        pull_request_number=PULL_REQUEST_NUMBER,
        session=session.url if session else None,
    )


def make_record(**overrides: Any) -> PullRequestRecord:
    fields: dict[str, Any] = {
        "state": PullRequestState.OPEN,
        "draft": True,
        "continuous_integration": CheckConclusion.SUCCESS,
        "additions": 100,
        "deletions": 20,
        "mergeable": True,
        "session_url": PARSED_SESSION.url,
    }
    fields.update(overrides)
    return PullRequestRecord(**fields)


def render_with_record(
    record: PullRequestRecord, item: Item | None = None
) -> tuple[Item, str]:
    item = item or make_item()
    renderer = make_renderer([item], {REPOSITORY: {str(PULL_REQUEST_NUMBER): record}})
    output, _ = renderer.render()
    return item, output


# %% chip derivation


def test_a_healthy_pull_request_gets_all_three_chips():
    item, _ = render_with_record(make_record())
    assert item.board_chips == [
        BoardChip.for_check_conclusion(CheckConclusion.SUCCESS),
        BoardChip.for_change_size(ChangeSize(100, 20)),
        BoardChip.for_mergeable(True),
    ]
    assert {chip.tone for chip in item.board_chips} == {ChipTone.POSITIVE}


def test_failing_checks_make_a_negative_check_chip():
    item, _ = render_with_record(
        make_record(continuous_integration=CheckConclusion.FAILURE)
    )
    assert item.board_chips[0] == BoardChip.for_check_conclusion(
        CheckConclusion.FAILURE
    )
    assert item.board_chips[0].tone is ChipTone.NEGATIVE


def test_running_checks_make_a_pending_check_chip():
    item, _ = render_with_record(
        make_record(continuous_integration=CheckConclusion.PENDING)
    )
    assert item.board_chips[0] == BoardChip.for_check_conclusion(
        CheckConclusion.PENDING
    )
    assert item.board_chips[0].tone is ChipTone.PENDING


def test_a_change_over_the_threshold_makes_a_negative_size_chip():
    additions, deletions = ChangeSize.SHORT_CHANGE_THRESHOLD, 1
    item, _ = render_with_record(make_record(additions=additions, deletions=deletions))
    chip = item.board_chips[1]
    assert chip == BoardChip.for_change_size(ChangeSize(additions, deletions))
    assert chip.tone is ChipTone.NEGATIVE
    assert str(additions) in chip.label
    assert str(deletions) in chip.label


def test_a_conflicting_pull_request_makes_a_negative_conflict_chip():
    item, _ = render_with_record(make_record(mergeable=False))
    assert item.board_chips[2] == BoardChip.for_mergeable(False)
    assert item.board_chips[2].tone is ChipTone.NEGATIVE


def test_unknown_facts_produce_no_chips_at_all():
    item, _ = render_with_record(
        make_record(
            continuous_integration=None,
            additions=None,
            deletions=None,
            mergeable=None,
            session_url=None,
        )
    )
    assert item.board_chips == []


def test_an_item_without_a_pull_request_has_no_chips():
    item = make_item()
    item.pull_request_number = None
    renderer = make_renderer([item])
    renderer.render()
    assert item.board_chips == []


# %% session-link fallback


def test_the_session_parsed_from_the_body_fills_a_missing_item_session():
    item, _ = render_with_record(make_record())
    assert item.session == PARSED_SESSION.url


def test_the_manifest_session_wins_over_the_parsed_one():
    item, _ = render_with_record(
        make_record(), item=make_item(session=MANIFEST_SESSION)
    )
    assert item.session == MANIFEST_SESSION.url


# %% backward compatibility with pre-chip pull request data


def test_pre_chip_pull_request_data_still_parses_and_renders_chipless():
    record = PullRequestRecord.from_mapping(
        {
            PullRequestDataKey.STATE: PullRequestState.OPEN,
            PullRequestDataKey.DRAFT: True,
            PullRequestDataKey.MERGED_AT: None,
            PullRequestDataKey.LABELS: [],
        }
    )
    item, output = render_with_record(record)
    assert item.board_chips == []
    assert f'class="badge {BoardChip.CSS_CLASS}' not in output


def test_extended_pull_request_data_parses_the_chip_fields():
    record = PullRequestRecord.from_mapping(
        {
            PullRequestDataKey.STATE: PullRequestState.OPEN,
            PullRequestDataKey.DRAFT: False,
            PullRequestDataKey.MERGED_AT: None,
            PullRequestDataKey.LABELS: [PullRequestLabel.BUG],
            PullRequestDataKey.CONTINUOUS_INTEGRATION: CheckConclusion.FAILURE,
            PullRequestDataKey.ADDITIONS: 12,
            PullRequestDataKey.DELETIONS: 3,
            PullRequestDataKey.MERGEABLE: False,
            PullRequestDataKey.SESSION_URL: PARSED_SESSION.url,
        }
    )
    assert record.continuous_integration is CheckConclusion.FAILURE
    assert record.change_size == ChangeSize(12, 3)
    assert record.mergeable is False
    assert record.session_url == PARSED_SESSION.url


def test_a_non_http_session_url_in_pull_request_data_is_dropped_at_parse_time():
    record = PullRequestRecord.from_mapping(
        {
            PullRequestDataKey.STATE: PullRequestState.OPEN,
            PullRequestDataKey.SESSION_URL: "javascript:alert(1)",
        }
    )
    assert record.session_url is None


# %% rendered markup


def test_chips_render_into_the_item_badges_row():
    item, output = render_with_record(make_record())
    assert f'class="badge {BoardChip.CSS_CLASS} chip-{ChipTone.POSITIVE}"' in output
    for chip in item.board_chips:
        assert chip.label in output
