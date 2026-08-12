"""
Unit tests for tracking which model sources a live world was built from.
"""

from __future__ import annotations

from cramera.live.model_source import LiveModelCatalog, TrackedSource


def fake_bundler():
    """
    A stand-in bundler, distinct per call site so tests can tell sources apart by it.
    """
    return lambda *args, **kwargs: None


class TestRemember:
    def test_a_source_is_remembered_once(self):
        catalog = LiveModelCatalog()
        bundler = fake_bundler()

        catalog.remember("/robots/pr2.urdf", bundler)
        catalog.remember("/robots/pr2.urdf", bundler)

        assert catalog.snapshot() == [
            TrackedSource(path="/robots/pr2.urdf", bundler=bundler)
        ]

    def test_sources_are_kept_in_load_order(self):
        catalog = LiveModelCatalog()
        environment_bundler, robot_bundler = fake_bundler(), fake_bundler()

        catalog.remember("/worlds/kitchen.urdf", environment_bundler)
        catalog.remember("/robots/pr2.urdf", robot_bundler)

        assert [tracked.path for tracked in catalog.snapshot()] == [
            "/worlds/kitchen.urdf",
            "/robots/pr2.urdf",
        ]

    def test_a_fresh_catalog_tracks_nothing(self):
        assert LiveModelCatalog().snapshot() == []

    def test_different_sources_with_the_same_bundler_are_both_kept(self):
        """
        Two URDF sources — a robot and an environment — share the same bundler function;
        deduplication is by path, not by bundler.
        """
        catalog = LiveModelCatalog()
        bundler = fake_bundler()

        catalog.remember("/robots/pr2.urdf", bundler)
        catalog.remember("/worlds/apartment.urdf", bundler)

        assert len(catalog.snapshot()) == 2
