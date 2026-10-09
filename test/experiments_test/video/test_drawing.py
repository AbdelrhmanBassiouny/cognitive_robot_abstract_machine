"""
Tests for :mod:`experiments.video.drawing`: a theme read as Manim colours, the drawing
builders, and a small animated scene rendered at low quality.

Everything here needs Manim, which needs cairo and pango on the machine, so the whole
module is skipped where it cannot be imported.
"""

from __future__ import annotations

import pytest
from typing_extensions import Tuple

from experiments.video.animation import (
    AnimatedScene,
    AnimationStep,
    BeatMiscount,
    SceneEntry,
)
from experiments.video.cache import SceneCache
from experiments.video.canvas import DARK_THEME, VideoTheme
from experiments.video.narration import Line
from experiments.video.timeline import Resolution

from .drawn import drawing_kept_out_of_the_checkout  # noqa: F401  autouse
from .voices import EvenlyPacedVoice

manim = pytest.importorskip("manim", reason="Manim needs cairo and pango")

from experiments.video.drawing import (  # noqa: E402  imported after the skip
    AnimationPalette,
    BarChart,
    BoxNode,
    Chip,
    CrossMark,
    Headline,
    HorizontalBarChart,
    ManimRenderer,
    TickMark,
)
from experiments.video.scenes import NumberedCards, TitleCard  # noqa: E402

SMALL = Resolution(width=320, height=180)
"""
A frame small enough that a test renders in seconds.
"""


@pytest.fixture
def palette() -> AnimationPalette:
    """
    The dark theme read as Manim colours.
    """
    return AnimationPalette.of(DARK_THEME)


@pytest.fixture
def lines() -> Tuple[Line, ...]:
    """
    Two short lines, so a rendered scene plays two beats.
    """
    return (Line("First beat."), Line("Second beat."))


@pytest.fixture
def voice() -> EvenlyPacedVoice:
    """
    A voice short enough to keep a rendering quick.
    """
    return EvenlyPacedVoice(seconds_per_word=0.2)


# %% a theme read as Manim colours


def test_a_palette_carries_every_colour_of_its_theme(
    palette: AnimationPalette,
) -> None:
    assert palette.page == AnimationPalette.hex_of(DARK_THEME.page)
    assert palette.text == AnimationPalette.hex_of(DARK_THEME.text)
    assert palette.accent == AnimationPalette.hex_of(DARK_THEME.accent)


def test_a_colour_is_read_as_the_hexadecimal_manim_takes() -> None:
    assert AnimationPalette.hex_of((0x0D, 0x11, 0x17)) == "#0D1117"


def test_a_palette_of_another_theme_differs_from_the_dark_one(
    palette: AnimationPalette,
) -> None:
    neutral = AnimationPalette.of(
        VideoTheme(
            page=(255, 255, 255),
            text=(0, 0, 0),
            muted=(0x55, 0x55, 0x55),
            hairline=(0x99, 0x99, 0x99),
            panel=(0xEE, 0xEE, 0xEE),
            marker=(0xFF, 0xF3, 0xB0),
            accent=(0x12, 0x5E, 0xA6),
            syntax=DARK_THEME.syntax,
        )
    )

    assert neutral.page != palette.page


# %% the drawing builders


def test_a_headline_is_drawn_at_the_size_it_was_asked_for(
    palette: AnimationPalette,
) -> None:
    drawn = Headline("A heading", size=28, palette=palette).built()

    assert drawn.height > 0
    assert drawn.width > 0


def test_a_chip_wraps_its_label(palette: AnimationPalette) -> None:
    chip = Chip("ready", colour=palette.accent, palette=palette).built()

    box, label = chip
    assert box.width > label.width
    assert box.height > label.height


def test_a_box_node_given_a_width_takes_it(palette: AnimationPalette) -> None:
    node = BoxNode("step", colour=palette.accent, palette=palette, width=4.0).built()

    assert node[0].width == pytest.approx(4.0)


def test_a_tick_and_a_cross_are_drawn_at_the_size_asked_for(
    palette: AnimationPalette,
) -> None:
    tick = TickMark(colour=palette.accent, size=0.4).built()
    cross = CrossMark(colour=palette.accent, size=0.4).built()

    assert tick.width > 0 and cross.width > 0


# %% a scene rendered at low quality


@pytest.fixture(scope="module")
def rendered(
    tmp_path_factory: pytest.TempPathFactory,
) -> AnimatedScene:
    """
    A two beat title card rendered once, small and at a low rate.
    """
    scene = AnimatedScene(
        renderer=ManimRenderer(
            painting=TitleCard(
                heading="A rendered title", standfirst="drawn by a test"
            ),
            palette=AnimationPalette.of(DARK_THEME),
            cache=SceneCache(
                name="test_title_card", root=tmp_path_factory.mktemp("animation")
            ),
        ),
        lines=(Line("First beat."), Line("Second beat.")),
        voice=EvenlyPacedVoice(seconds_per_word=0.2),
        pause=0.2,
        resolution=SMALL,
        frames_per_second=10,
    )
    scene.frames
    return scene


def test_a_rendered_scene_lasts_at_least_as_long_as_its_beats(
    rendered: AnimatedScene,
) -> None:
    """
    Manim draws every step and wait in whole frames, rounding each up, so a rendering
    runs a little over its beats. It must never run under them, or the narration would
    be cut off.
    """
    assert rendered.duration >= rendered.schedule.duration


def test_a_rendered_scene_draws_frames_of_the_size_it_was_given(
    rendered: AnimatedScene,
) -> None:
    assert Resolution.of(rendered.picture_at(0.0)) == SMALL


def test_a_rendered_scene_changes_over_time(rendered: AnimatedScene) -> None:
    first = rendered.picture_at(0.0)
    later = rendered.picture_at(rendered.duration * 0.75)

    assert (first != later).any()


def test_a_rendered_scene_is_read_back_from_the_cache(
    rendered: AnimatedScene,
) -> None:
    kept = list(rendered.renderer.cache.directory.iterdir())

    assert kept


def test_a_scene_can_cut_in_instead_of_dissolving(
    palette: AnimationPalette, lines: Tuple[Line, ...], voice: EvenlyPacedVoice
) -> None:
    scene = AnimatedScene(
        renderer=ManimRenderer(
            painting=TitleCard(heading="Cut", standfirst="in"), palette=palette
        ),
        lines=lines,
        voice=voice,
        pause=0.2,
        entry=SceneEntry.CUT,
    )

    assert not scene.dissolves_in


# %% a scene that plays the wrong number of beats


def test_a_painting_that_plays_too_few_beats_is_refused(
    palette: AnimationPalette, voice: EvenlyPacedVoice
) -> None:
    scene = AnimatedScene(
        renderer=ManimRenderer(
            painting=NumberedCards(
                heading="Three cards",
                cards=(("01", "One"), ("02", "Two"), ("03", "Three")),
            ),
            palette=palette,
            cache=None,
        ),
        lines=(Line("Only one line."),),
        voice=voice,
        pause=0.2,
        resolution=SMALL,
        frames_per_second=10,
    )

    with pytest.raises(BeatMiscount):
        scene.frames


# %% the steps a painting asks for


def test_a_step_carries_what_it_draws(palette: AnimationPalette) -> None:
    drawn = Headline("Step", palette=palette).built()
    step = AnimationStep(weight=0.5, drawn=(manim.FadeIn(drawn),))

    assert step.weight == 0.5
    assert len(step.drawn) == 1


# %% charts draw once, so a caller grows the bars it shows


def test_a_bar_chart_grows_the_bars_it_drew(palette: AnimationPalette) -> None:
    chart = BarChart(
        values=(0.4, 0.8),
        labels=("first", "second"),
        colours=(palette.accent, palette.muted),
        origin=(0.0, 0.0),
        palette=palette,
    )

    drawn = chart.drawn()

    assert len(drawn.bars) == len(chart.values)
    assert all(bar in drawn.whole.submobjects for bar in [drawn.bars])


def test_a_horizontal_bar_chart_places_its_names_against_its_own_bars(
    palette: AnimationPalette,
) -> None:
    chart = HorizontalBarChart(
        values=(1.0, 2.0),
        labels=("first", "second"),
        colours=(palette.accent, palette.muted),
        origin=(0.0, 0.0),
        scale=1.0,
        palette=palette,
    )

    drawn = chart.drawn()

    for bar, name in zip(drawn.bars, drawn.names):
        assert name.get_right()[0] <= bar.get_left()[0] + 1e-6
