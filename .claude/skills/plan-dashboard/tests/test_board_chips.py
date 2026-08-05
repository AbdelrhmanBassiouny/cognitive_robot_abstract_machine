"""
Tests for the board-semantics chips on dashboard items: the CI, change-size, and
conflict chips derived from the extended ``pr_data.json`` fields, the session-link
fallback parsed from the pull request body, and backward compatibility with pull request
data that predates those fields.
"""

from __future__ import annotations

from build_dashboard import (
    BoardChip,
    ChipTone,
    DashboardRenderer,
    Item,
    ItemStatus,
    Plan,
    PullRequestRecord,
    PullRequestState,
    PullRequestsByRepository,
    Track,
    Wave,
)
from development_tooling.pr_state import (
    DEFAULT_SHORT_CHANGE_THRESHOLD,
    CheckConclusion,
)


def make_renderer(
    items: list[Item],
    pull_requests_by_repository: PullRequestsByRepository | None = None,
) -> DashboardRenderer:
    plan = Plan(
        id="test-plan",
        title="Test Plan",
        description="desc",
        default_repository="owner/repo",
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


def make_item(session: str | None = None) -> Item:
    return Item(
        title="an item",
        branch="a-branch",
        track="track-1",
        status=ItemStatus.IN_PROGRESS,
        id="an-item",
        pull_request_number=1,
        session=session,
    )


def make_record(**overrides) -> PullRequestRecord:
    fields = {
        "state": PullRequestState.OPEN,
        "draft": True,
        "ci": CheckConclusion.SUCCESS,
        "additions": 100,
        "deletions": 20,
        "mergeable": True,
        "session_url": "https://claude.ai/code/session_01AbCdEf",
    }
    fields.update(overrides)
    return PullRequestRecord(**fields)


def render_with_record(record: PullRequestRecord, item: Item | None = None):
    item = item or make_item()
    renderer = make_renderer([item], {"owner/repo": {"1": record}})
    output, _ = renderer.render()
    return item, output


# %% chip derivation


def test_healthy_pull_request_gets_all_three_chips():
    item, _ = render_with_record(make_record())
    assert item.board_chips == [
        BoardChip(
            label="ci passing",
            tone=ChipTone.POSITIVE,
            tooltip="Latest checks on the head commit: passing",
        ),
        BoardChip(
            label="+100 −20",
            tone=ChipTone.POSITIVE,
            tooltip=(
                "120 lines changed versus the base - within the short-change "
                f"threshold of {DEFAULT_SHORT_CHANGE_THRESHOLD}"
            ),
        ),
        BoardChip(
            label="mergeable",
            tone=ChipTone.POSITIVE,
            tooltip="GitHub reports this pull request merges cleanly onto its base",
        ),
    ]


def test_failing_checks_make_a_negative_ci_chip():
    item, _ = render_with_record(make_record(ci=CheckConclusion.FAILURE))
    assert item.board_chips[0] == BoardChip(
        label="ci failing",
        tone=ChipTone.NEGATIVE,
        tooltip="Latest checks on the head commit: failing",
    )


def test_running_checks_make_a_pending_ci_chip():
    item, _ = render_with_record(make_record(ci=CheckConclusion.PENDING))
    assert item.board_chips[0] == BoardChip(
        label="ci pending",
        tone=ChipTone.PENDING,
        tooltip="Latest checks on the head commit: pending",
    )


def test_change_over_the_threshold_makes_a_negative_size_chip():
    item, _ = render_with_record(make_record(additions=500, deletions=100))
    assert item.board_chips[1] == BoardChip(
        label="+500 −100",
        tone=ChipTone.NEGATIVE,
        tooltip=(
            "600 lines changed versus the base - over the short-change "
            f"threshold of {DEFAULT_SHORT_CHANGE_THRESHOLD}, consider splitting "
            "or restacking"
        ),
    )


def test_conflicting_pull_request_makes_a_negative_conflict_chip():
    item, _ = render_with_record(make_record(mergeable=False))
    assert item.board_chips[2] == BoardChip(
        label="conflicts",
        tone=ChipTone.NEGATIVE,
        tooltip=(
            "GitHub reports this pull request does not merge cleanly onto its base"
        ),
    )


def test_unknown_facts_produce_no_chips_at_all():
    item, _ = render_with_record(
        make_record(
            ci=None, additions=None, deletions=None, mergeable=None, session_url=None
        )
    )
    assert item.board_chips == []


def test_item_without_a_pull_request_has_no_chips():
    item = make_item()
    item.pull_request_number = None
    renderer = make_renderer([item])
    renderer.render()
    assert item.board_chips == []


# %% session-link fallback


def test_session_parsed_from_the_pull_request_body_fills_a_missing_item_session():
    item, _ = render_with_record(make_record())
    assert item.session == "https://claude.ai/code/session_01AbCdEf"


def test_the_manifest_session_wins_over_the_parsed_one():
    item, _ = render_with_record(
        make_record(),
        item=make_item(session="https://claude.ai/code/session_manifest"),
    )
    assert item.session == "https://claude.ai/code/session_manifest"


# %% backward compatibility with pre-chip pull request data


def test_pre_chip_pull_request_data_still_parses_and_renders_chipless():
    record = PullRequestRecord.from_mapping(
        {"state": "open", "draft": True, "merged_at": None, "labels": []}
    )
    item, output = render_with_record(record)
    assert item.board_chips == []
    assert 'class="badge board-chip' not in output


def test_extended_pull_request_data_parses_the_chip_fields():
    record = PullRequestRecord.from_mapping(
        {
            "state": "open",
            "draft": False,
            "merged_at": None,
            "labels": ["bug"],
            "ci": "failure",
            "additions": 12,
            "deletions": 3,
            "mergeable": False,
            "session_url": "https://claude.ai/code/session_01AbCdEf",
        }
    )
    assert record.ci is CheckConclusion.FAILURE
    assert record.additions == 12
    assert record.deletions == 3
    assert record.mergeable is False
    assert record.session_url == "https://claude.ai/code/session_01AbCdEf"


def test_a_non_http_session_url_in_pull_request_data_is_dropped_at_parse_time():
    record = PullRequestRecord.from_mapping(
        {
            "state": "open",
            "session_url": "javascript:alert(1)",
        }
    )
    assert record.session_url is None


# %% rendered markup


def test_chips_render_into_the_item_badges_row():
    _, output = render_with_record(make_record())
    assert 'class="badge board-chip chip-positive"' in output
    assert "ci passing" in output
    assert "+100 −20" in output
    assert "mergeable" in output
