"""
Ready-made EQL queries for the EQL panel.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple

from typing_extensions import List, Optional

from cramera.knowledge.knowledge_base import EpisodeKnowledgeBase
from cramera.knowledge.scene_bundle import SceneBundle


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

    requires_live: bool = False
    """
    Whether answering this needs a running demo attached to the viewer.

    A bundle declares questions about the demo it was recorded from, which range over
    variables only that demo's live query source offers.
    """

    @classmethod
    def of_scene(cls, scene: Optional[str] = None) -> List[Preset]:
        """
        Ready-made queries for the EQL panel.

        A bundle that declares its own presets replaces the generated scene ones with
        them; otherwise they are generated from the loaded scene, so they stay valid for
        any onboarded robot/environment. The architecture presets are always offered:
        they range over the repository scan rather than the scene.

        :param scene: Name of the scene to build presets for, or None for the active
            one.
        """
        declared = SceneBundle.declared_presets(scene)
        if declared:
            return [
                cls(entry["text"], entry["code"], requires_live=True)
                for entry in declared
            ] + list(ARCHITECTURE_PRESETS)
        return cls._generated_for_scene(scene) + list(ARCHITECTURE_PRESETS)

    @classmethod
    def _generated_for_scene(cls, scene: Optional[str]) -> List[Preset]:
        """
        Ready-made queries derived from what the scene bundle actually contains.

        :param scene: Name of the scene to build presets for, or None for the active
            one.
        """
        knowledge_base = EpisodeKnowledgeBase.of_scene(scene)
        presets = [
            cls("which robot is this?", "the(entity(robot))"),
            cls("which arms does it have?", "an(entity(arm))"),
            cls("each arm and its gripper", "set_of(arm.side, arm.gripper)"),
            cls("what is in the scene?", "an(entity(scene_object))"),
            cls(
                "what gets moved?",
                "an(entity(episode.picks).where(episode.picks != None))",
            ),
        ]
        first_object = next(
            (entry for entry in knowledge_base.objects if entry.kind == "object"), None
        )
        if first_object:
            presets.append(
                cls(
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
                    cls(
                        "where does it place them?",
                        "the(entity(episode.places_at).where(episode.name == %s))"
                        % repr(manipulation.name),
                    )
                )
            if manipulation.performed_by:
                presets.append(
                    cls(
                        "which arm does '%s'?" % manipulation.name,
                        "the(entity(episode.performed_by).where(episode.name == %s))"
                        % repr(manipulation.name),
                    )
                )
        return presets


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
"""
Static presets for the architecture side of the graph.
"""
