"""
Naming things in a picture: a name is written where it is anchored, kept inside the
picture, moved up clear of a name below it, and drawn in its own colour with a line to
the thing it names.
"""

from __future__ import annotations

import numpy as np
import pytest

from experiments.paper.labels import (
    LABEL_COLOR,
    LABEL_HALO,
    LABELS_APART,
    Label,
    Labelling,
)
from experiments.paper.lettering import drawn

WIDTH = 320
"""
How wide the picture the names are written on is, in pixels.
"""

HEIGHT = 240
"""
How tall it is, in pixels.
"""


def blank_picture() -> np.ndarray:
    """
    A grey picture to write on, which holds neither the label colour nor its halo.
    """
    return np.full((HEIGHT, WIDTH, 3), 128, dtype=np.uint8)


def pixels_of(picture: np.ndarray, color) -> int:
    """
    How many pixels of the picture are exactly the given colour.

    :param picture: The picture to count in.
    :param color: The colour the twin states.
    """
    return int(np.all(picture == drawn(color), axis=-1).sum())


# %% where a name goes


def test_a_name_on_its_own_is_centred_over_its_anchor() -> None:
    [placed] = Labelling().lay_out(
        [Label(text="cube", anchor=(160.0, 100.0), thing=(160.0, 120.0))],
        width=WIDTH,
        height=HEIGHT,
    )
    assert placed.left + placed.width / 2 == pytest.approx(160.0, abs=1.0)
    assert placed.baseline == 100


def test_a_name_anchored_off_the_edge_is_moved_inside_the_picture() -> None:
    [placed] = Labelling().lay_out(
        [Label(text="cube", anchor=(WIDTH - 2.0, 3.0), thing=(WIDTH - 2.0, 20.0))],
        width=WIDTH,
        height=HEIGHT,
    )
    assert placed.right <= WIDTH
    assert placed.top >= 0


def test_two_names_anchored_at_one_place_are_written_apart() -> None:
    """
    The name anchored lower keeps its place and the other is moved up clear of it, so
    neither is written over the other.
    """
    lower = Label(text="cube", anchor=(160.0, 100.0), thing=(160.0, 120.0))
    upper = Label(text="cylinder", anchor=(160.0, 98.0), thing=(160.0, 118.0))

    placed = {
        one.label.text: one
        for one in Labelling().lay_out([upper, lower], width=WIDTH, height=HEIGHT)
    }

    assert placed["cube"].baseline == 100
    assert not placed["cube"].overlaps(placed["cylinder"])
    assert placed["cylinder"].bottom + LABELS_APART <= placed["cube"].top


def test_names_far_apart_stay_where_they_are_anchored() -> None:
    labels = [
        Label(text="cube", anchor=(60.0, 100.0), thing=(60.0, 120.0)),
        Label(text="cylinder", anchor=(240.0, 100.0), thing=(240.0, 120.0)),
    ]
    placed = Labelling().lay_out(labels, width=WIDTH, height=HEIGHT)
    assert [one.baseline for one in placed] == [100, 100]


# %% what is written


def test_a_written_name_is_in_the_label_colour_with_its_halo() -> None:
    picture = blank_picture()

    Labelling().write_on(
        picture, [Label(text="cube", anchor=(160.0, 100.0), thing=(160.0, 150.0))]
    )

    assert pixels_of(picture, LABEL_COLOR) > 0
    assert pixels_of(picture, LABEL_HALO) > 0


def test_a_written_name_is_joined_to_its_thing_by_a_line() -> None:
    """
    The line reaches the thing: the pixel the thing is at is drawn in the label colour
    even though the name itself is written well above it.
    """
    picture = blank_picture()
    thing = (160.0, 200.0)

    [placed] = Labelling().write_on(
        picture, [Label(text="cube", anchor=(160.0, 60.0), thing=thing)]
    )

    assert placed.bottom < thing[1]
    assert tuple(picture[round(thing[1]), round(thing[0])]) == drawn(LABEL_COLOR)
