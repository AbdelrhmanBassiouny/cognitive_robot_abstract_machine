"""
A card's levels drawn one above another as a single picture.

Four separate figures float apart on a page and are read in whatever order the layout
puts them; one picture with the levels stacked is read straight down, which is the whole
point of showing an event over the plan that was running over what the camera saw. None
of this needs a renderer: the levels are already pictures by the time they get here.
"""

from __future__ import annotations

from pathlib import Path

import imageio.v2 as imageio
import numpy as np
import pytest
from typing_extensions import Tuple

from experiments.paper.layered import Layer, LayeredFigure
from semantic_digital_twin.world_description.geometry import Color

# %% the pictures these levels are drawn from

FIRST_COLOR = Color(1.0, 0.0, 0.0, 1.0)
"""
The colour of the level drawn at the top, which nothing else in the figure is drawn in.
"""

SECOND_COLOR = Color(0.0, 0.0, 1.0, 1.0)
"""
The colour of the level drawn under it.
"""

PICTURE_SIZE = (120, 200)
"""
Height and width of the pictures these levels are drawn from, in pixels.
"""


def picture_of(color: Color, path: Path, size: Tuple[int, int] = PICTURE_SIZE) -> Path:
    """
    Leave a picture of one flat colour where a drawn level would have left one.

    :param color: What the whole picture is drawn in.
    :param path: Where to leave it.
    :param size: Its height and width in pixels.
    """
    drawn = np.zeros((size[0], size[1], 3), dtype=np.uint8)
    drawn[:, :] = [round(channel * 255) for channel in color.to_rgb()]
    imageio.imwrite(str(path), drawn)
    return path


@pytest.fixture
def two_levels(tmp_path: Path) -> Tuple[Layer, Layer]:
    """
    Two levels, each drawn in a colour the other is not.
    """
    return (
        Layer(
            name="what was seen", picture=picture_of(FIRST_COLOR, tmp_path / "a.png")
        ),
        Layer(
            name="what was running",
            picture=picture_of(SECOND_COLOR, tmp_path / "b.png"),
        ),
    )


def rows_holding(figure: np.ndarray, color: Color) -> np.ndarray:
    """
    Which rows of pixels of a figure hold the given colour anywhere along them.

    :param figure: The drawn figure.
    :param color: The colour to look for.
    """
    drawn = np.array([round(channel * 255) for channel in color.to_rgb()])
    return np.flatnonzero(np.any(np.all(figure[:, :, :3] == drawn, axis=-1), axis=1))


# %% the levels stacked


def test_every_level_given_is_drawn_in_the_figure(
    two_levels: Tuple[Layer, Layer],
) -> None:
    """
    A layered figure is the levels themselves rather than a picture of the top one, so
    each of them is in it.
    """
    figure = LayeredFigure().of(two_levels)
    assert rows_holding(figure, FIRST_COLOR).size > 0
    assert rows_holding(figure, SECOND_COLOR).size > 0


def test_the_levels_are_drawn_in_the_order_they_are_given(
    two_levels: Tuple[Layer, Layer],
) -> None:
    """
    The levels are read straight down, so the first one given is the one at the top.
    """
    figure = LayeredFigure().of(two_levels)
    assert (
        rows_holding(figure, FIRST_COLOR).max()
        < rows_holding(figure, SECOND_COLOR).min()
    )


def test_every_level_is_drawn_as_wide_as_the_figure(
    two_levels: Tuple[Layer, Layer],
) -> None:
    """
    Levels drawn at whatever width they happened to be rendered at would not line up
    under each other, so each is scaled to the figure's own width.
    """
    figure = LayeredFigure(width=640).of(two_levels)
    assert figure.shape[1] == 640
    for color in (FIRST_COLOR, SECOND_COLOR):
        [row] = [rows_holding(figure, color)[0]]
        drawn = np.array([round(channel * 255) for channel in color.to_rgb()])
        assert np.all(figure[row, :, :3] == drawn)


def test_a_level_is_taller_than_the_picture_it_is_drawn_from(
    two_levels: Tuple[Layer, Layer],
) -> None:
    """
    Each level is written over with what it shows, so it takes the height of its picture
    and the band its name is written in.
    """
    figure = LayeredFigure(width=PICTURE_SIZE[1]).of(two_levels[:1])
    assert figure.shape[0] > PICTURE_SIZE[0]


# %% keeping one level from dwarfing the rest


def test_a_tall_level_is_kept_from_dwarfing_the_others(tmp_path: Path) -> None:
    """
    A level far taller than it is wide would push every other one off the page, so it is
    fitted to a height rather than stretched to the figure's width.
    """
    tall = picture_of(FIRST_COLOR, tmp_path / "tall.png", size=(2000, 200))

    figure = LayeredFigure(width=400, maximum_level_height=300).of(
        [Layer(name="the twin", picture=tall)]
    )

    assert rows_holding(figure, FIRST_COLOR).size <= 300
    assert figure.shape[1] == 400


def test_a_level_fitted_to_a_height_is_still_centred_in_the_figure(
    tmp_path: Path,
) -> None:
    """
    Fitted to a height, a level is narrower than the figure; drawn against one edge it
    would read as belonging to that side rather than to the card.
    """
    tall = picture_of(FIRST_COLOR, tmp_path / "tall.png", size=(2000, 200))

    figure = LayeredFigure(width=400, maximum_level_height=300).of(
        [Layer(name="the twin", picture=tall)]
    )

    [row] = [rows_holding(figure, FIRST_COLOR)[0]]
    holding = np.flatnonzero(
        np.all(
            figure[row, :, :3] == [round(c * 255) for c in FIRST_COLOR.to_rgb()],
            axis=-1,
        )
    )
    assert holding.min() == figure.shape[1] - holding.max() - 1


# %% a level the run left nothing to draw


def test_a_level_with_no_picture_is_still_named(tmp_path: Path) -> None:
    """
    A reader shown three levels cannot tell whether the fourth was left out or never
    existed, so a level the run recorded nothing for says so in its own place rather
    than vanishing.
    """
    nothing_to_draw = Layer(
        name="what the camera saw", note="this run recorded no camera"
    )
    figure = LayeredFigure().of([nothing_to_draw])
    assert figure.shape[0] > 0
    assert figure.shape[1] == LayeredFigure().width


def test_a_missing_level_keeps_its_place_among_the_others(
    two_levels: Tuple[Layer, Layer],
) -> None:
    """
    The levels mean something in their order, so one with nothing to draw holds its
    place rather than letting the ones under it move up.
    """
    first, second = two_levels
    between = Layer(name="what the camera saw", note="this run recorded no camera")

    figure = LayeredFigure().of([first, between, second])

    assert (
        rows_holding(figure, FIRST_COLOR).max()
        < rows_holding(figure, SECOND_COLOR).min()
    )
    assert figure.shape[0] > LayeredFigure().of(two_levels).shape[0]


# %% written out


def test_the_figure_is_written_where_it_is_asked_for(
    two_levels: Tuple[Layer, Layer], tmp_path: Path
) -> None:
    """
    A card names the file it wrote, so the figure leaves one where the card says.
    """
    written = LayeredFigure().write(two_levels, tmp_path / "deep" / "layered.png")
    assert written.is_file()
    assert imageio.imread(written).shape[1] == LayeredFigure().width
