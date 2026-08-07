"""
Ready-made EQL queries for the EQL panel.
"""

from __future__ import annotations

from typing_extensions import Dict, List

from cram_viz.knowledge.knowledge_base import get_knowledge_base

#: static presets for the architecture side of the graph
ARCH_PRESETS = [
    {
        "text": "CRAM packages by size",
        "code": "set_of(pkg.name, pkg.class_count).ordered_by(pkg.class_count, descending=True)",
    },
    {
        "text": "all Designator classes",
        "code": "an(entity(cls).where(cls.name.endswith('Designator')))",
    },
    {
        "text": "where does EQL live?",
        "code": "set_of(cls.name, cls.module).where(in_('entity_query_language', cls.module)).limit(15)",
    },
    {
        "text": "subclasses of Symbol",
        "code": "an(entity(cls).where(in_('Symbol', cls.bases)))",
    },
    {
        "text": "inside coraplex",
        "code": "an(entity(sub).where(sub.package == 'coraplex'))",
    },
]


def get_presets() -> List[Dict[str, str]]:
    """
    Ready-made queries for the EQL panel.

    Scene presets are generated from the loaded scene, so they stay valid for any
    onboarded robot/environment; the architecture presets are static.
    """
    kb = get_knowledge_base()
    presets = [
        {"text": "which robot is this?", "code": "the(entity(rob))"},
        {"text": "which arms does it have?", "code": "an(entity(arm))"},
        {"text": "each arm and its gripper", "code": "set_of(arm.side, arm.gripper)"},
        {"text": "what is in the scene?", "code": "an(entity(obj))"},
        {
            "text": "what gets moved?",
            "code": "an(entity(ep.picks).where(ep.picks != None))",
        },
    ]
    first_object = next((entry for entry in kb.objects if entry.kind == "object"), None)
    if first_object:
        presets.append(
            {
                "text": "the %s" % first_object.label.lower(),
                "code": "the(entity(obj).where(obj.name == %s))"
                % repr(first_object.name),
            }
        )
    manipulation = next((episode for episode in kb.episodes if episode.picks), None)
    if manipulation:
        if manipulation.places_at:
            presets.append(
                {
                    "text": "where does it place them?",
                    "code": "the(entity(ep.places_at).where(ep.name == %s))"
                    % repr(manipulation.name),
                }
            )
        if manipulation.performed_by:
            presets.append(
                {
                    "text": "which arm does '%s'?" % manipulation.name,
                    "code": "the(entity(ep.performed_by).where(ep.name == %s))"
                    % repr(manipulation.name),
                }
            )
    return presets + ARCH_PRESETS
