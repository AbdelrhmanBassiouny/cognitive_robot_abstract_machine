"""
Show the camera frames the perception node receives, so what the camera is sending can
be watched while the node runs.

This is a way to see the stream with your own eyes rather than a step the pipeline
needs: a window that stays empty says the frames are not arriving, which no amount of
reading the detections would tell you.
"""

from __future__ import annotations

import threading
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import StrEnum

import cv2
import numpy as np
from typing_extensions import Optional

# %% what gets drawn where


class CameraWindow(StrEnum):
    """
    The windows the frames are drawn in, one per stream so both can be watched at once.
    """

    COLOR = "montessori perception: colour"
    DEPTH = "montessori perception: depth"


BRIGHTEST_SHADE = 255
"""
Shade standing for the furthest distance a depth image measured.
"""


def colorize_depth(depth: np.ndarray) -> np.ndarray:
    """
    Turn a depth image in metres into one the eye can read.

    The colours span the distances this frame actually measured, so whatever the camera
    is pointed at fills the range rather than washing out at one end of a fixed scale.

    :param depth: Depth in metres, zero where the sensor returned no reading.
    :return: The image, shape ``(height, width, 3)`` of ``uint8``, black where nothing
        was measured.
    """
    measured = depth > 0.0
    if not measured.any():
        return np.zeros((*depth.shape, 3), dtype=np.uint8)
    distances = depth[measured]
    nearest = float(distances.min())
    span = float(distances.max()) - nearest
    shades = np.zeros(depth.shape, dtype=np.uint8)
    if span > 0.0:
        shades[measured] = (BRIGHTEST_SHADE * (distances - nearest) / span).astype(
            np.uint8
        )
    colored = cv2.applyColorMap(shades, cv2.COLORMAP_TURBO)
    colored[~measured] = 0
    return colored


def scale_to_fit(image: np.ndarray, maximum_width: int) -> np.ndarray:
    """
    Shrink an image too wide to sit on screen, keeping its proportions.

    :param image: The image to fit.
    :param maximum_width: Widest the result may be, in pixels.
    :return: The image itself where it already fits, or a smaller copy.
    """
    width = image.shape[1]
    if width <= maximum_width:
        return image
    height = round(image.shape[0] * maximum_width / width)
    return cv2.resize(image, (maximum_width, height))


# %% putting images on screen


class ImageDisplay(ABC):
    """
    Somewhere images can be put on screen.
    """

    @abstractmethod
    def draw(self, window_name: str, image: np.ndarray) -> None:
        """
        Put an image on screen, replacing whatever that window held.

        :param window_name: The window to draw in, opened if it is not open yet.
        :param image: The image to draw.
        """

    @abstractmethod
    def wait(self, milliseconds: int) -> None:
        """
        Give the windows that long to redraw themselves and answer the keyboard.

        :param milliseconds: How long to hand over.
        """

    @abstractmethod
    def close(self) -> None:
        """
        Take every window off screen.
        """


@dataclass
class OpenCvDisplay(ImageDisplay):
    """
    Puts images on screen through OpenCV's own windowing, which draws on the thread that
    calls it.
    """

    def draw(self, window_name: str, image: np.ndarray) -> None:
        cv2.imshow(window_name, image)

    def wait(self, milliseconds: int) -> None:
        cv2.waitKey(milliseconds)

    def close(self) -> None:
        cv2.destroyAllWindows()


# %% the viewer


@dataclass
class CameraFrameViewer:
    """
    Shows the newest camera frame the node received.

    Frames arrive on the node's subscription threads while a window can only be drawn on
    the thread that owns it, so a frame handed to :meth:`show` is held until
    :meth:`refresh` is called from that thread.
    """

    display: ImageDisplay = field(default_factory=OpenCvDisplay)
    """
    Where the frames are put on screen.
    """

    maximum_width: int = 960
    """
    Widest a frame is drawn, in pixels, so a full resolution frame is scaled down far
    enough to leave both windows on screen at once.
    """

    refresh_milliseconds: int = 30
    """
    How long :meth:`refresh` gives the windows to redraw, which also paces the loop
    calling it.
    """

    _color: Optional[np.ndarray] = field(init=False, default=None)
    """
    The newest colour image, or None until one has arrived.
    """

    _depth: Optional[np.ndarray] = field(init=False, default=None)
    """
    The newest depth image in metres, or None until one has arrived.
    """

    _lock: threading.Lock = field(init=False, default_factory=threading.Lock)
    """
    Guards the held frame against being read while it is being replaced.
    """

    def show_color(self, color: np.ndarray) -> None:
        """
        Hand in the newest colour image, to be drawn at the next :meth:`refresh`.

        :param color: The colour image, blue/green/red.
        """
        with self._lock:
            self._color = color

    def show_depth(self, depth: np.ndarray) -> None:
        """
        Hand in the newest depth image, to be drawn at the next :meth:`refresh`.

        Held apart from the colour image so a stream that has stopped leaves its own
        window empty instead of emptying both.

        :param depth: The depth image in metres.
        """
        with self._lock:
            self._depth = depth

    def refresh(self) -> None:
        """
        Draw the newest frame and let the windows answer the keyboard.

        Draws nothing until a frame has arrived, so an empty screen says the camera is
        not being heard.
        """
        with self._lock:
            color, depth = self._color, self._depth
        if color is not None:
            self.display.draw(
                CameraWindow.COLOR, scale_to_fit(color, self.maximum_width)
            )
        if depth is not None:
            self.display.draw(
                CameraWindow.DEPTH,
                scale_to_fit(colorize_depth(depth), self.maximum_width),
            )
        self.display.wait(self.refresh_milliseconds)

    def close(self) -> None:
        """
        Take the windows off screen.
        """
        self.display.close()
