"""
A video mixing a frame built slide, an animated scene and a still, made end to end in
the dark theme with boxed captions and a progress bar over it.

Rendering needs Manim, so the module is skipped where it cannot be imported.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from experiments.video.animation import AnimatedScene
from experiments.video.cache import SceneCache
from experiments.video.canvas import DARK_THEME, VIDEO_RESOLUTION
from experiments.video.encoding import VideoFile
from experiments.video.narration import (
    BoxedCaption,
    Line,
    NarratedScene,
    Storyboard,
)
from experiments.video.overlays import ProgressBar
from experiments.video.production import EncoderPreset, VideoProduction
from experiments.video.slides import TextCard
from experiments.video.timeline import Still

from .drawn import drawing_kept_out_of_the_checkout  # noqa: F401  autouse
from .voices import EvenlyPacedVoice

pytest.importorskip("manim", reason="Manim needs cairo and pango")

from experiments.video.drawing import (  # noqa: E402  imported after the skip
    AnimationPalette,
    ManimRenderer,
    RenderQuality,
)
from experiments.video.scenes import TitleCard  # noqa: E402

RESOLUTION = VIDEO_RESOLUTION
"""
The size the slides draw at, which every scene of one video must share.
"""

FRAMES_PER_SECOND = 10
"""
A rate low enough to keep the rendering quick.
"""

VOICE = EvenlyPacedVoice(seconds_per_word=0.25, rate=16_000, level=0.1)
"""
A voice at a rate an audio encoder takes, quiet enough not to clip.
"""


def gradient() -> np.ndarray:
    """
    A picture that changes across the frame, so there is something to encode.
    """
    picture = RESOLUTION.blank(0)
    picture[..., 0] = np.linspace(0, 255, RESOLUTION.width, dtype=np.uint8)
    return picture


def animated(cache_root: Path) -> AnimatedScene:
    """
    :param cache_root: Where the drawn frames are kept.
    :return: A two beat animated title, drawn small and quickly.
    """
    return AnimatedScene(
        renderer=ManimRenderer(
            painting=TitleCard(heading="Animated", standfirst="in a mixed video"),
            palette=AnimationPalette.of(DARK_THEME),
            cache=SceneCache(name="test_mixed_video", root=cache_root),
            quality=RenderQuality.LOW,
        ),
        lines=(Line("An animated scene."), Line("Paced by this line.")),
        voice=VOICE,
        pause=0.2,
        resolution=RESOLUTION,
        frames_per_second=FRAMES_PER_SECOND,
    )


def mixed_storyboard(cache_root: Path) -> Storyboard:
    """
    :param cache_root: Where the animated scene keeps its frames.
    :return: A title card, an animated scene and a still, in the dark theme.
    """
    return Storyboard(
        [
            NarratedScene(
                TextCard(
                    "A mixed video",
                    "two ways to draw",
                    held_for=1.0,
                    theme=DARK_THEME,
                ),
                (Line("This video draws its scenes two ways."),),
            ),
            NarratedScene(animated(cache_root), ()),
            NarratedScene(Still(gradient(), held_for=1.0)),
        ]
    )


@pytest.fixture(scope="module")
def mixed(tmp_path_factory: pytest.TempPathFactory) -> VideoFile:
    """
    The mixed video, made once.
    """
    root = tmp_path_factory.mktemp("mixed")
    production = VideoProduction(
        mixed_storyboard(root),
        voice=VOICE,
        frames_per_second=FRAMES_PER_SECOND,
        dissolve=0.2,
        captions=BoxedCaption(),
        overlays=[ProgressBar(theme=DARK_THEME)],
        preset=EncoderPreset.FAST,
    )
    return production.written_to(root / "mixed.mp4")


# %% the video that comes out


def test_the_mixed_video_plays_at_the_size_and_rate_it_was_given(
    mixed: VideoFile,
) -> None:
    assert mixed.resolution == RESOLUTION
    assert mixed.frames_per_second == pytest.approx(FRAMES_PER_SECOND)


def test_the_mixed_video_lasts_as_long_as_its_scenes(
    mixed: VideoFile, tmp_path_factory: pytest.TempPathFactory
) -> None:
    timeline, _ = VideoProduction(
        mixed_storyboard(tmp_path_factory.mktemp("again")),
        voice=VOICE,
        frames_per_second=FRAMES_PER_SECOND,
        dissolve=0.2,
    ).narrated_timeline()

    assert mixed.duration == pytest.approx(
        timeline.duration, abs=1.5 / FRAMES_PER_SECOND
    )


def test_the_mixed_video_carries_its_narration(mixed: VideoFile) -> None:
    assert mixed.size > 0


def test_the_progress_bar_runs_over_every_scene(mixed: VideoFile) -> None:
    bar = ProgressBar(theme=DARK_THEME)
    early = mixed.frame_at(0.1)[: bar.thickness]
    late = mixed.frame_at(mixed.duration * 0.9)[: bar.thickness]

    assert (early != late).any()
