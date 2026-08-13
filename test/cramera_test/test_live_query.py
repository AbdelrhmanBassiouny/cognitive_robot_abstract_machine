"""
Tests for querying a running demo through the live bridge.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field

import pytest

krrood = pytest.importorskip("krrood", reason="EQL requires krrood")

from semantic_digital_twin.spatial_types import Point3  # noqa: E402
from typing_extensions import List  # noqa: E402

from cramera.knowledge.presets import Preset  # noqa: E402
from cramera.knowledge.query_domain import QueryDomain  # noqa: E402
from cramera.live.bridge import Bridge  # noqa: E402
from cramera.live.query import LiveQuerySource, NoQuerySourceRegistered  # noqa: E402

from .dataset.queryable_records import NamedRecord  # noqa: E402


@dataclass
class GrowingRecordSource(LiveQuerySource):
    """
    A source whose records keep arriving, the way a demo's results do while it runs.
    """

    records: List[NamedRecord] = field(default_factory=list)
    """
    What this source's one domain ranges over.
    """

    def title(self) -> str:
        """
        What the panel names this source.
        """
        return "record demo"

    def domains(self) -> List[QueryDomain]:
        """
        The one domain this source offers.
        """
        return [QueryDomain("record", NamedRecord, self.records)]

    def presets(self) -> List[Preset]:
        """
        The ready-made queries this source offers.
        """
        return [Preset("all records", "an(entity(record))")]


def make_record(name: str) -> NamedRecord:
    """
    One record to query, distinguished only by its name.

    :param name: The record's name.
    """
    return NamedRecord(name, "alpha", 1.0, Point3(0.0, 0.0, 0.0))


@pytest.fixture()
def source() -> GrowingRecordSource:
    return GrowingRecordSource(records=[make_record("first")])


@pytest.fixture()
def bridge(source) -> Bridge:
    live_bridge = Bridge()
    live_bridge.register_query_source(source)
    return live_bridge


# %% answering from the running process
class TestQueryingARegisteredSource:
    def test_a_query_is_answered_from_the_sources_domain(self, bridge):
        result = bridge.run_query("an(entity(record))")

        assert result.ok
        assert [row["__entity__"] for row in result.rows] == ["first"]

    def test_a_query_sees_records_recorded_after_registration(self, bridge, source):
        """
        The point of querying live: an answer reflects what the demo has done by the
        time the question is asked, not by the time the bridge was wired up.
        """
        source.records.append(make_record("second"))

        result = bridge.run_query("an(entity(record))")

        assert [row["__entity__"] for row in result.rows] == ["first", "second"]

    def test_the_presets_are_the_sources_own(self, bridge):
        assert bridge.query_presets() == [Preset("all records", "an(entity(record))")]

    def test_every_preset_of_a_source_runs(self, bridge):
        for preset in bridge.query_presets():
            assert bridge.run_query(preset.code).ok, preset.text

    def test_status_reports_that_querying_is_available(self, bridge):
        assert bridge.status()["query"] is True

    def test_the_source_titles_the_answers(self, bridge):
        assert bridge.query_title() == "record demo"


# %% no demo to ask
class TestQueryingWithoutASource:
    def test_running_a_query_raises(self):
        with pytest.raises(NoQuerySourceRegistered):
            Bridge().run_query("an(entity(record))")

    def test_asking_for_presets_raises(self):
        with pytest.raises(NoQuerySourceRegistered):
            Bridge().query_presets()

    def test_status_reports_that_querying_is_unavailable(self):
        assert Bridge().status()["query"] is False


# %% concurrent viewers
class TestConcurrentQueries:
    def test_queries_from_several_threads_all_answer_correctly(self, bridge, source):
        """
        Krrood's SymbolGraph singleton is not threadsafe and the bridge serves several
        viewers from its own thread pool, so overlapping queries must not corrupt one
        another's answers.
        """
        source.records.extend(make_record(name) for name in ("second", "third"))
        counts: List[int] = []
        lock = threading.Lock()

        def ask() -> None:
            count = bridge.run_query("an(entity(record))").count
            with lock:
                counts.append(count)

        askers = [threading.Thread(target=ask) for _ in range(8)]
        for asker in askers:
            asker.start()
        for asker in askers:
            asker.join(timeout=30)

        assert counts == [3] * 8
