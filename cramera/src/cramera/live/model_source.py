"""
Tracks which model sources a live world was built from.

Unlike a recording's :class:`~cramera.onboard.demo.Recorder`, the live bridge never
bundles anything itself here — it only remembers what to bundle later, when a browser
actually attaches. See :mod:`cramera.live.live_bundle` for the bundling step, which
reuses the same onboarding bundler every recorded scene already goes through.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field

from typing_extensions import Callable, List

from cramera.onboard.bundle_urdf import BundleReport


@dataclass(frozen=True)
class TrackedSource:
    """
    One model source a running demo built its world from.
    """

    path: str
    """
    Absolute path, or ``package://`` URI, of the source file.
    """

    bundler: Callable[..., BundleReport]
    """
    Bundles :attr:`path` into an output directory — ``BundleReport.of_source`` for a
    URDF/xacro source, or one of ``BundledWorld``'s Gazebo/MJCF equivalents.
    """


@dataclass
class LiveModelCatalog:
    """
    Model sources a running demo loaded, in load order, deduplicated by path.
    """

    sources: List[TrackedSource] = field(default_factory=list)
    """
    Tracked sources, in load order.
    """

    _lock: threading.Lock = field(default_factory=threading.Lock)
    """
    Guards :attr:`sources`.

    Deliberately a lock of its own, never :class:`~cramera.live.bridge.Bridge`'s — the
    tick hook holds that one while publishing every snapshot, and bundling a snapshot (a
    slow xacro expansion, for the PR2 description) can take seconds; sharing a lock
    would stall the running demo for that long every time a browser attaches.
    """

    def remember(self, path: str, bundler: Callable[..., BundleReport]) -> None:
        """
        Remember a model source the world was built from, at most once.

        :param path: Absolute path, or ``package://`` URI, of the source file.
        :param bundler: Bundles this source's kind into an output directory.
        """
        with self._lock:
            if not any(tracked.path == path for tracked in self.sources):
                self.sources.append(TrackedSource(path=path, bundler=bundler))

    def snapshot(self) -> List[TrackedSource]:
        """
        Every tracked source, in load order.
        """
        with self._lock:
            return list(self.sources)
