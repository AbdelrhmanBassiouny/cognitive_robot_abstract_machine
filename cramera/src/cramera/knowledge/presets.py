"""
Ready-made EQL queries for the EQL panel.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple

from typing_extensions import List

from cramera.knowledge.knowledge_base import get_knowledge_base


@dataclass
class Preset:
    """
    One ready-made EQL query offered by the EQL panel.
    """

    text: str
    """
    Human-readable label shown in the presets list.
    """

    code: str
    """
    EQL source the panel runs when this preset is picked.
    """


#: static presets for the architecture side of the graph
ARCHITECTURE_PRESETS: Tuple[Preset, ...] = (
    Preset(
        "CRAM packages by size",
        "set_of(package.name, package.class_count)"
        ".ordered_by(package.class_count, descending=True)",
    ),
    Preset(
        "all Designator classes",
        "an(entity(python_class).where(python_class.name.endswith('Designator')))",
    ),
    Preset(
        "where does EQL live?",
        "set_of(python_class.name, python_class.module)"
        ".where(in_('entity_query_language', python_class.module)).limit(15)",
    ),
    Preset(
        "subclasses of Symbol",
        "an(entity(python_class).where(in_('Symbol', python_class.bases)))",
    ),
    Preset(
        "inside coraplex",
        "an(entity(subpackage).where(subpackage.package == 'coraplex'))",
    ),
)


def get_presets() -> List[Preset]:
    """
    Ready-made queries for the EQL panel.

    Scene presets are generated from the loaded scene, so they stay valid for any
    onboarded robot/environment; the architecture presets are static.
    """
    knowledge_base = get_knowledge_base()
    presets = [
        Preset("which robot is this?", "the(entity(robot))"),
        Preset("which arms does it have?", "an(entity(arm))"),
        Preset("each arm and its gripper", "set_of(arm.side, arm.gripper)"),
        Preset("what is in the scene?", "an(entity(scene_object))"),
        Preset(
            "what gets moved?", "an(entity(episode.picks).where(episode.picks != None))"
        ),
    ]
    first_object = next(
        (entry for entry in knowledge_base.objects if entry.kind == "object"), None
    )
    if first_object:
        presets.append(
            Preset(
                "the %s" % first_object.label.lower(),
                "the(entity(scene_object).where(scene_object.name == %s))"
                % repr(first_object.name),
            )
        )
    manipulation = next(
        (episode for episode in knowledge_base.episodes if episode.picks), None
    )
    if manipulation:
        if manipulation.places_at:
            presets.append(
                Preset(
                    "where does it place them?",
                    "the(entity(episode.places_at).where(episode.name == %s))"
                    % repr(manipulation.name),
                )
            )
        if manipulation.performed_by:
            presets.append(
                Preset(
                    "which arm does '%s'?" % manipulation.name,
                    "the(entity(episode.performed_by).where(episode.name == %s))"
                    % repr(manipulation.name),
                )
            )
    return presets + list(ARCHITECTURE_PRESETS)
