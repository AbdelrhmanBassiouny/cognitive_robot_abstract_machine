"""
Ready-made EQL queries for the EQL panel.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, replace
from typing import Tuple

from typing_extensions import TYPE_CHECKING, List, Optional

from cramera.knowledge.eql_session import EqlSession
from cramera.knowledge.knowledge_base import EpisodeKnowledgeBase
from cramera.knowledge.query_verbalization import QueryVerbalization
from cramera.knowledge.queryable_knowledge import QueryScope
from cramera.knowledge.scene_bundle import SceneBundle

if TYPE_CHECKING:
    from cramera.knowledge.query_runner import EqlQueryRunner


WORD_START = re.compile(r"(?<!^)(?=[A-Z])")
"""
Where a word begins inside a camel-case class name, which is where a space belongs when
that name is said out loud.
"""


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

    scope: QueryScope = QueryScope.CURRENT_STATE
    """
    Which of the demo's bodies of knowledge this question is about, and so the heading
    it is offered under.
    """

    verbalization: Optional[QueryVerbalization] = None
    """
    The question read back as English, or None while nothing that knows the query's
    variables has worded it (see :meth:`worded`).
    """

    def worded(self, runner: EqlQueryRunner) -> Preset:
        """
        This preset with its question read back as English by ``runner``.

        A preset whose code the runner cannot build keeps no verbalization: its button
        still shows its label, and running it reports its own error.

        :param runner: The runner whose variables the preset's code ranges over.
        """
        return replace(self, verbalization=runner.verbalize(self.code))

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
            presets = [
                cls(
                    entry["text"],
                    entry["code"],
                    requires_live=True,
                    scope=QueryScope.of_name(
                        entry.get("scope", QueryScope.CURRENT_STATE)
                    ),
                )
                for entry in declared
            ] + list(ARCHITECTURE_PRESETS)
        else:
            presets = cls._generated_for_scene(scene) + list(ARCHITECTURE_PRESETS)
        return cls._worded_by_scene(presets, scene)

    @classmethod
    def _worded_by_scene(
        cls, presets: List[Preset], scene: Optional[str]
    ) -> List[Preset]:
        """
        The presets with their questions read back as English by the scene's runner.

        A bundle-declared question ranges over a demo's own variables, which the
        recorded scene does not know; it is worded by the live bridge instead and stays
        unworded here.

        :param presets: The presets to word.
        :param scene: Name of the scene whose runner words them, or None for the active
            one.
        """
        runner = EqlSession.of_scene(scene).runner()
        return [preset.worded(runner) for preset in presets]

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


@dataclass(frozen=True)
class PresetsPerType:
    """
    The same question asked once per type a record can be, e.g. "give me all pick up
    events" for every kind of event a demo detects.

    Written out rather than shown as buttons: a panel has room for the question, not for
    one button per type it can name.
    """

    class_suffix: str
    """
    The word every one of these types' class names ends in, e.g. ``"Event"``.
    """

    class_names: Tuple[str, ...]
    """
    The class name of every type a question may name.
    """

    code: str
    """
    The query answering the question, with ``%s`` for the type's class name.
    """

    scope: QueryScope = QueryScope.CURRENT_STATE
    """
    Which body of knowledge these questions are about.
    """

    def questions(self) -> List[Preset]:
        """
        One question per type, worded the way it is asked out loud.
        """
        return [
            Preset(
                "give me all %s %s" % (self._spoken_type(name), self._plural_noun),
                self.code % name,
                scope=self.scope,
            )
            for name in self.class_names
        ]

    @property
    def _plural_noun(self) -> str:
        """
        What several of these records are called out loud, e.g. ``"events"``.
        """
        return self.class_suffix.lower() + "s"

    def _spoken_type(self, class_name: str) -> str:
        """
        One type as a question names it: ``"PickUpEvent"`` becomes ``"pick up"``.

        :param class_name: The type's class name.
        """
        return WORD_START.sub(" ", class_name[: -len(self.class_suffix)]).lower()


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
