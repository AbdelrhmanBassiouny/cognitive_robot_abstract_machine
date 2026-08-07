"""
The recorded demo scene as an EQL (Entity Query Language) knowledge base.

EQL is krrood's pythonic relational query language. This package models the recorded
coraplex/giskardpy episode — bench objects, robot parts, action episodes, per-joint
motion — as plain dataclasses and exposes:

fresh_namespace()  -> dict for evaluating one EQL query (fresh variables)
run_query(code)    -> execute an EQL query string, return JSON-able result
graph_payload()    -> nodes/edges/details/presets for the UI knowledge graph
view_payload(name) -> one of the graph-panel tabs (knowledge / kinematics / plan /
chart)

krrood is imported lazily: without it the static viewer still works, only the EQL panel
is unavailable. Scene bundles are read from paths.scenes_dir().
"""

from __future__ import annotations

import logging

from typing_extensions import Any, Dict, Optional

from cram_viz.knowledge.architecture_entities import (
    Package as Package,
    PythonClass as PythonClass,
)
from cram_viz.knowledge.eql_session import run_query
from cram_viz.knowledge.graph_payload import graph_payload
from cram_viz.knowledge.knowledge_base import (
    get_knowledge_base,
    reset_knowledge_base as reset_knowledge_base,
)
from cram_viz.knowledge.presets import get_presets
from cram_viz.knowledge.scene_bundle import load_scene as load_scene
from cram_viz.knowledge.views.architecture import (
    CLASS_CAP as CLASS_CAP,
    SUBCLASS_CAP as SUBCLASS_CAP,
    _class_id,
    _package_view,
    _subpackage_view,
    _class_view,
)
from cram_viz.knowledge.views.kinematics import _urdf_view
from cram_viz.knowledge.views.plan import (
    _plan_view,
    shorten_action_label as shorten_action_label,
)

# %% drill-down subgraphs
# Double-clicking a node in the UI asks for its inside view: package → its
# subpackages + top-level classes, subpackage → its classes (with inheritance
# edges), class → its base classes and every subclass in the repo.


# %% the graph-panel tabs
def view_payload(name: str) -> Dict[str, Any]:
    """
    One tab of the graph panel.

    ``knowledge`` is the entity graph (the default, with drill-down); the others are
    structural views of the same demo that the UI can overlay with live status from the
    bridge (see :mod:`cram_viz.live.http`, ``/plan`` and ``/chart``).
    """
    kb = get_knowledge_base()
    if name == "knowledge":
        return graph_payload()
    if name == "kinematics":
        return _urdf_view(kb)
    if name == "plan":
        return _plan_view()
    if name == "chart":
        return _chart_view()
    return {"ok": False, "error": "unknown view: %s" % name}


def _chart_view() -> Dict[str, Any]:
    """
    The (live-only) statechart tab.

    Motion statecharts only exist while giskardpy executes them: one is
    compiled per merged motion group and thrown away afterwards, and nothing
    of it is recorded into the bundle — the UI fills this view from the
    bridge's ``/chart`` while attached.
    """
    return {
        "ok": True,
        "crumb": "motion statechart",
        "nodes": [],
        "edges": [],
        "details": {},
        "layout": "hier",
        "live": "chart",
        "empty": "Motion statecharts are built and ticked at execution time. "
        "Start the demo with cram-viz-live and press ◉ Live — "
        "the statechart of the running motion group appears here, "
        "coloured by its node life cycle.",
    }


def expand_node(node_id: str) -> Optional[Dict[str, Any]]:
    """
    The inside view of a double-clicked node, or None if not drillable.
    """
    kb = get_knowledge_base()
    if node_id == kb.robot.name:  # robot → full URDF kinematic tree
        return _urdf_view(kb)
    if node_id == "plan":  # → the executed plan tree
        return _plan_view()
    package = next((entry for entry in kb.packages if entry.name == node_id), None)
    if package:
        return _package_view(kb, package)
    subpackage = next(
        (entry for entry in kb.subpackages if entry.name == node_id), None
    )
    if subpackage:
        return _subpackage_view(kb, subpackage)
    python_class = next(
        (entry for entry in kb.classes if _class_id(entry) == node_id), None
    )
    if python_class:
        return _class_view(kb, python_class)
    return None


if __name__ == "__main__":
    # smoke test: run every preset against the active scene
    logging.basicConfig(level=logging.INFO)
    for preset in get_presets():
        try:
            result = run_query(preset["code"])
            logging.info("OK   %-32s -> %d rows", preset["text"], result["count"])
        except Exception as error:
            logging.error(
                "FAIL %-32s -> %s: %s", preset["text"], type(error).__name__, error
            )
