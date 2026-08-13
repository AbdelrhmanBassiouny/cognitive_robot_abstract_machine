"""
Tests for the domain-agnostic EQL query runner and its row rendering.
"""

import pytest

krrood = pytest.importorskip("krrood", reason="EQL requires krrood")

from semantic_digital_twin.spatial_types import Point3, Pose  # noqa: E402

from cramera.body_geometry import pose_label  # noqa: E402
from cramera.knowledge.query_domain import QueryDomain  # noqa: E402
from cramera.knowledge.query_runner import EqlQueryRunner, RowRenderer  # noqa: E402

from .dataset.queryable_records import (  # noqa: E402
    NamedRecord,
    PosedRecord,
    UnnamedRecord,
)


def make_records() -> list:
    """
    Three records spanning two categories, so grouping and filtering have work to do.
    """
    return [
        NamedRecord("first", "alpha", 1.0, Point3(0.0, 0.0, 0.0)),
        NamedRecord("second", "alpha", 2.0, Point3(1.0, 0.0, 0.0)),
        NamedRecord("third", "beta", 3.0, Point3(0.0, 1.0, 0.0)),
    ]


def make_runner(records=None) -> EqlQueryRunner:
    """
    A runner over one ``record`` domain of :class:`NamedRecord`.

    :param records: Records the domain ranges over, or None for :func:`make_records`.
    """
    return EqlQueryRunner(
        domains=[
            QueryDomain(
                name="record",
                entity_type=NamedRecord,
                objects=make_records() if records is None else records,
            )
        ]
    )


# %% domains become query variables
class TestDomainsBecomeVariables:
    """
    A declared domain is all a caller needs to write a query against it.
    """

    def test_a_domain_is_in_scope_under_its_own_name(self):
        result = make_runner().run("an(entity(record))")

        assert result.ok
        assert [row["__entity__"] for row in result.rows] == [
            "first",
            "second",
            "third",
        ]

    def test_the_entity_type_is_in_scope_under_its_class_name(self):
        """
        A query may name the type itself, so a source needs no extra names to be
        queryable.
        """
        result = make_runner().run("an(entity(variable(NamedRecord, [])))")

        assert result.ok
        assert result.count == 0

    def test_extra_names_are_in_scope(self):
        runner = EqlQueryRunner(domains=[], extra_names={"threshold": 2.0})

        assert runner.namespace()["threshold"] == 2.0

    def test_a_domain_variable_is_not_shared_between_runs(self):
        """
        Each run builds its own variables; a reused one would range over the accumulated
        domain and answer a second identical query differently.
        """
        runner = make_runner()

        first = runner.run("an(entity(record))")
        second = runner.run("an(entity(record))")

        assert first.count == second.count == 3

    def test_a_domain_reflects_records_added_after_the_runner_was_built(self):
        """
        A live source keeps appending to its own list, so the domain must be read at
        query time rather than copied when the runner is constructed.
        """
        records = []
        runner = make_runner(records)
        records.append(NamedRecord("late", "alpha", 4.0, Point3(0.0, 0.0, 0.0)))

        assert runner.run("an(entity(record))").count == 1


# %% rendering answer rows
class TestRowRendering:
    """
    What the panel is handed for each kind of query result.
    """

    def test_a_named_dataclass_is_rendered_as_an_entity(self):
        result = make_runner().run("the(entity(record).where(record.name == 'third'))")

        assert result.rows == [
            {
                "__entity__": "third",
                "__type__": "NamedRecord",
                "category": "beta",
                "score": 3.0,
                "position": "(0.00, 1.00, 0.00)",
            }
        ]
        assert result.highlight == ["third"]

    def test_a_set_of_query_is_rendered_as_value_rows(self):
        result = make_runner().run("set_of(record.name, record.category)")

        assert result.rows == [
            {"NamedRecord.name": "first", "NamedRecord.category": "alpha"},
            {"NamedRecord.name": "second", "NamedRecord.category": "alpha"},
            {"NamedRecord.name": "third", "NamedRecord.category": "beta"},
        ]

    def test_a_pose_is_rendered_readably(self):
        """
        A pose is a CasADi-symbolic type with no plain-value repr, so it needs the same
        treatment a position already gets.
        """
        target = Pose.from_xyz_rpy(1.0, 2.0, 3.0)
        runner = EqlQueryRunner(
            domains=[
                QueryDomain(
                    name="posed",
                    entity_type=PosedRecord,
                    objects=[PosedRecord("aimed", target)],
                )
            ]
        )

        result = runner.run("an(entity(posed))")

        assert result.rows[0]["target"] == pose_label(target)

    def test_only_a_declared_entity_type_is_titled_and_highlighted(self):
        """
        Carrying a ``name`` is not enough to be an entity — the renderer titles a row
        only for the types its query source declared, so an unrelated dataclass that
        happens to have a name is left as a plain value.
        """
        renderer = RowRenderer(entity_types=(NamedRecord,))

        named = NamedRecord("first", "alpha", 1.0, Point3(0.0, 0.0, 0.0))
        undeclared = PosedRecord("aimed", Pose.from_xyz_rpy(0.0, 0.0, 0.0))

        assert renderer._row_title(named) == "first"
        assert renderer._row_title(undeclared) is None
        assert renderer._row_title(UnnamedRecord("x")) is None

    def test_rows_stop_at_the_limit_and_say_so(self):
        result = make_runner().run("an(entity(record))", limit=2)

        assert result.count == 2
        assert result.more is True

    def test_an_unlimited_result_does_not_claim_to_be_truncated(self):
        assert make_runner().run("an(entity(record))").more is False


# %% failures reach the caller
class TestQueryFailures:
    """
    The runner does not swallow a bad query; the transport decides how to report it.
    """

    def test_an_unknown_name_raises(self):
        with pytest.raises(NameError):
            make_runner().run("no_such_variable")

    def test_a_syntactically_invalid_query_raises(self):
        with pytest.raises(SyntaxError):
            make_runner().run("definitely not python (((")

    def test_an_empty_query_raises(self):
        with pytest.raises(ValueError):
            make_runner().run("   ")
