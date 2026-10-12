"""
Tests for :mod:`cramcorder.lettering`: the fonts a typeface sets each face in.
"""

from __future__ import annotations

from cramcorder.lettering import Face, FontName, FontStyle, Typeface

FONT_SIZE = 20


def test_a_typeface_sets_each_face_in_its_own_font() -> None:
    typeface = Typeface()
    assert typeface.font(Face.REGULAR, FONT_SIZE).getname() == (
        FontName.SANS,
        FontStyle.BOOK,
    )
    assert typeface.font(Face.BOLD, FONT_SIZE).getname() == (
        FontName.SANS,
        FontStyle.BOLD,
    )
    assert typeface.font(Face.MONO, FONT_SIZE).getname() == (
        FontName.SANS_MONO,
        FontStyle.BOOK,
    )


def test_a_face_is_set_at_the_size_asked_for() -> None:
    size = 31
    assert Typeface().font(Face.REGULAR, size).size == size
