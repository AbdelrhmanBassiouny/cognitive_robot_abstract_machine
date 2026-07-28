"""Filesystem locations for cram_viz, all overridable via environment.

The frontend (``web/``) ships inside the package. Scene bundles are GENERATED
artifacts (tens to hundreds of MB per scene, produced by ``cram-viz-onboard``)
and are deliberately not part of the repository — they live in a data directory
that defaults to ``~/.cram_viz/scenes`` and can be pointed anywhere:

    CRAM_VIZ_SCENES=/path/to/scenes           scene bundles (onboarder output)
    CRAM_VIZ_ARCHITECTURE=/path/to/repo       CRAM repo scanned by the KB graph
"""

from __future__ import annotations

import os
from pathlib import Path

#: the packaged frontend: index.html, panels, vendored libraries
WEB_ROOT = Path(__file__).resolve().parent / "web"


def scenes_dir() -> Path:
    """Directory holding the onboarded scene bundles (``<name>/scene.json``)."""
    env = os.environ.get("CRAM_VIZ_SCENES")
    if env:
        return Path(env).expanduser()
    return Path.home() / ".cram_viz" / "scenes"


def architecture_root() -> Path:
    """The CRAM repository whose packages/classes the knowledge graph shows.

    Defaults to the repository this package is checked out in, which is the
    common case inside the workspace; falls back to the conventional clone
    location otherwise.
    """
    env = os.environ.get("CRAM_VIZ_ARCHITECTURE")
    if env:
        return Path(env).expanduser()
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "coraplex").is_dir() and (parent / "krrood").is_dir():
            return parent
    return Path.home() / "cognitive_robot_abstract_machine"
