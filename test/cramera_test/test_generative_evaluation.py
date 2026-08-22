"""
Tests for answering a question that leaves a field open.

Such a question names no objects to search: it names a pattern, and every value its open
fields could take is what the answer is built from.
"""

from __future__ import annotations

import pytest

krrood = pytest.importorskip("krrood", reason="EQL requires krrood")

from krrood.entity_query_language.exceptions import (  # noqa: E402
    UnderspecifiedStatementInfeasibleForEntityQueryLanguageGeneration,
)

from cramera.knowledge.generative_evaluation import GenerativeEvaluation  # noqa: E402
from cramera.knowledge.query_runner import EqlQueryRunner  # noqa: E402
from cramera.knowledge.queryable_knowledge import (  # noqa: E402
    QueryableKnowledge,
    QueryScope,
)

from .dataset.queryable_records import (  # noqa: E402
    Approach,
    Hand,
    RecordWithEnumFields,
)

EVERY_HAND = "an(RecordWithEnumFields)(hand=...)"
"""
The pattern leaving one enum field open.
"""

EVERY_HAND_AND_APPROACH = "an(RecordWithEnumFields)(hand=..., approach=...)"
"""
The pattern leaving two enum fields open.
"""


@pytest.fixture()
def runner():
    """
    A runner over a body of knowledge whose answers are built rather than looked up.

    It ranges over nothing: what a question of this kind names is the pattern to build,
    not a set of objects to search.
    """
    knowledge = QueryableKnowledge(
        scope=QueryScope.UNDERSPECIFIED,
        domains=[],
        evaluation=GenerativeEvaluation(),
        extra_names={"RecordWithEnumFields": RecordWithEnumFields, "Hand": Hand},
    )
    return EqlQueryRunner(
        domains=knowledge.domains,
        extra_names=knowledge.extra_names,
        evaluation=knowledge.evaluation,
    )


# %% building what a question leaves open
class TestBuildingWhatIsLeftOpen:
    def test_an_open_enum_field_is_answered_once_per_member(self, runner):
        result = runner.run(EVERY_HAND)

        assert [row["hand"] for row in result.rows] == [hand.name for hand in Hand]

    def test_two_open_enum_fields_are_answered_once_per_combination(self, runner):
        result = runner.run(EVERY_HAND_AND_APPROACH)

        assert result.count == len(Hand) * len(Approach)
        assert {(row["hand"], row["approach"]) for row in result.rows} == {
            (hand.name, approach.name) for hand in Hand for approach in Approach
        }

    def test_a_built_answer_is_titled_by_nothing_but_its_fields(self, runner):
        """
        A built instance names nothing of its own, so its row is its fields alone rather
        than one titled by the instance's ``repr``.
        """
        result = runner.run(EVERY_HAND)

        assert result.kind == "rows"
        assert "__entity__" not in result.rows[0]
        assert result.rows[0]["__type__"] == RecordWithEnumFields.__name__

    def test_a_field_the_question_fixes_is_kept(self, runner):
        result = runner.run("an(RecordWithEnumFields)(hand=..., label='asked for')")

        assert {row["label"] for row in result.rows} == {"asked for"}

    def test_a_condition_narrows_what_was_built(self, runner):
        result = runner.run(
            "pattern = %s\n"
            "pattern.where(pattern.variable.hand == Hand.LEFT)" % EVERY_HAND
        )

        assert [row["hand"] for row in result.rows] == [Hand.LEFT.name]

    def test_an_open_field_no_enum_bounds_is_refused(self, runner):
        """
        Enumerating a field's values needs the values to be enumerable; a bare ``str``
        field is not, and says so rather than answering with nothing.
        """
        with pytest.raises(
            UnderspecifiedStatementInfeasibleForEntityQueryLanguageGeneration
        ):
            runner.run("an(RecordWithEnumFields)(hand=..., label=...)")


# %% asking about what was built
class TestAskingAboutWhatWasBuilt:
    def test_the_values_filled_in_are_selectable(self, runner):
        result = runner.run(
            "built = generate(%s)\n"
            "set_of(built.hand, built.approach)" % EVERY_HAND_AND_APPROACH
        )

        assert {(row["hand"], row["approach"]) for row in result.rows} == {
            (hand.name, approach.name) for hand in Hand for approach in Approach
        }

    def test_what_was_built_can_be_counted(self, runner):
        result = runner.run(
            "built = generate(%s)\n"
            "set_of(built.hand, count(built)).grouped_by(built.hand)"
            % EVERY_HAND_AND_APPROACH
        )

        assert {row["hand"] for row in result.rows} == {hand.name for hand in Hand}
        assert [row["Count"] for row in result.rows] == [len(Approach)] * len(Hand)

    def test_the_name_it_is_asked_through_is_offered_to_the_query_box(self, runner):
        offered = [entry.name for entry in runner.vocabulary().entries()]

        assert "generate" in offered
