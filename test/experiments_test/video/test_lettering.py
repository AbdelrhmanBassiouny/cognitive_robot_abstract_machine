"""
Tests for :mod:`experiments.video.lettering`: the fonts a typeface sets each face in.
"""

from __future__ import annotations

from experiments.video.lettering import Face, Typeface


def test_a_typeface_sets_each_face_in_its_own_font() -> None:
    typeface = Typeface()
    assert typeface.font(Face.REGULAR, 20).getname() == ("DejaVu Sans", "Book")
    assert typeface.font(Face.BOLD, 20).getname() == ("DejaVu Sans", "Bold")
    assert typeface.font(Face.MONO, 20).getname() == ("DejaVu Sans Mono", "Book")


def test_a_face_is_set_at_the_size_asked_for() -> None:
    assert Typeface().font(Face.REGULAR, 31).size == 31
