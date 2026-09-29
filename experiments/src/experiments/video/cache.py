"""
Pictures and readings a scene takes a while to compute, kept on disk so a video is
rendered again without recomputing them.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path

import cv2
import numpy as np
from typing_extensions import Any, Dict, Optional

from experiments.video.timeline import Frame

CACHE_DIRECTORY_VARIABLE = "EXPERIMENTS_VIDEO_CACHE"
"""
Environment variable naming where the video keeps what it computed.
"""

DEFAULT_CACHE_DIRECTORY = Path.home() / ".cache" / "experiments" / "video"
"""
Where the video keeps what it computed unless told otherwise.
"""


def configured_cache_directory() -> Path:
    """
    Where the video keeps what it computed, as the environment says or by default.
    """
    return Path(os.getenv(CACHE_DIRECTORY_VARIABLE, DEFAULT_CACHE_DIRECTORY))


@dataclass
class SceneCache:
    """
    One scene's kept pictures and readings, under a name of its own.
    """

    name: str
    """
    What the scene's corner of the cache is called.
    """

    root: Path = field(default_factory=configured_cache_directory)
    """
    Where every scene's corner lies.
    """

    @property
    def directory(self) -> Path:
        """
        This scene's corner, made if it is not there yet.
        """
        directory = self.root / self.name
        directory.mkdir(parents=True, exist_ok=True)
        return directory

    def picture(self, key: str) -> Optional[Frame]:
        """
        :param key: What the picture was kept as.
        :return: The picture as red, green and blue, or None if none was kept.
        """
        path = self.directory / f"{key}.png"
        if not path.is_file():
            return None
        return cv2.cvtColor(cv2.imread(str(path)), cv2.COLOR_BGR2RGB)

    def keep_picture(self, key: str, picture: Frame) -> None:
        """
        :param key: What to keep the picture as.
        :param picture: The picture, as red, green and blue.
        """
        cv2.imwrite(
            str(self.directory / f"{key}.png"), cv2.cvtColor(picture, cv2.COLOR_RGB2BGR)
        )

    def record(self, key: str) -> Optional[Dict[str, Any]]:
        """
        :param key: What the readings were kept as.
        :return: The readings, or None if none were kept.
        """
        path = self.directory / f"{key}.json"
        if not path.is_file():
            return None
        return json.loads(path.read_text())

    def keep_record(self, key: str, readings: Dict[str, Any]) -> None:
        """
        :param key: What to keep the readings as.
        :param readings: Readings JSON can carry.
        """
        (self.directory / f"{key}.json").write_text(json.dumps(readings, indent=1))
