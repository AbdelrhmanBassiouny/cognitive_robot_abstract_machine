"""
Tests for the ConclusionAid base: both optional hooks default to a no-op (return ``None``),
and subclasses may override either or both.
"""

from __future__ import annotations

from krrood.entity_query_language.rdr.aid import ConclusionAid


def test_base_hooks_return_none():
    aid = ConclusionAid()
    assert aid.present(context=None) is None
    assert aid.suggest(context=None) is None


def test_present_only_subclass():
    class InfoAid(ConclusionAid):
        def present(self, context):
            return "see the picture"

    aid = InfoAid()
    assert aid.present(context=None) == "see the picture"
    assert aid.suggest(context=None) is None


def test_suggest_only_subclass():
    class Suggester(ConclusionAid):
        def suggest(self, context):
            return "guess"

    aid = Suggester()
    assert aid.present(context=None) is None
    assert aid.suggest(context=None) == "guess"
