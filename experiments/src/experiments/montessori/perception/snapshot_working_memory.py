"""
Working memory as a snapshot of the twin, refreshed only when it is worth refreshing.

While a piece is held, the twin already follows the gripper's kinematics through the
attachment mechanism -- perception has nothing to add and is not consulted. While idle,
a look is taken at a low rate and every piece it reports is written straight onto the
twin's belief. Whether a piece actually moved, and whether the robot moved it, is not
this class's question: it belongs to the event system that watches the twin over time
(:class:`~segmind.detectors.atomic_event_detectors_nodes.TranslationDetector` and its
kin), which sees every correction this class commits.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

import numpy as np
from typing_extensions import List, Optional

from experiments.montessori.perception.detections import MontessoriScene
from experiments.montessori.semantics import MontessoriShape, MontessoriShapeCategory
from krrood.patterns.role import Role
from semantic_digital_twin.spatial_types.spatial_types import Pose
from semantic_digital_twin.world import World

# %% what a look reports


@dataclass(eq=False)
class PerceivedPose(Role[Pose]):
    """
    A loose piece as one look reported it, narrowed to what matching it to a believed
    piece needs.

    A role of the pose one look reported, the same pattern
    :class:`~experiments.montessori.perception.detections.DetectedMontessoriShape`
    already uses for a sighting: the perceived :class:`Pose` is the role taker, reached
    through :attr:`~krrood.patterns.role.Role.role_taker`, and this role adds only what
    matching needs on top of it.
    """

    category: MontessoriShapeCategory = field(kw_only=True)
    """
    The kind of piece perception recognised, matched against a believed piece of the
    same kind.
    """


def perceived_poses_of(scene: MontessoriScene) -> List[PerceivedPose]:
    """
    The pieces one look found, narrowed to what :class:`SnapshotWorkingMemory` reads.

    :param scene: One pass of the perception pipeline.
    :return: One entry per piece the look found.
    """
    return [
        PerceivedPose(category=shape.category, role_taker=shape.pose)
        for shape in scene.shapes
    ]


# %% the snapshot itself


@dataclass
class SnapshotWorkingMemory:
    """
    Keeps the twin's belief about loose pieces a snapshot, refreshed only while idle.

    Nothing here decides *whether* the robot is idle or *how* a look is taken -- both
    are handed in, so this class depends on the fact of idleness and the fact of a look
    rather than on the gripper or the camera themselves. It also does not decide
    *whether* a piece moved: every look it takes is written onto the twin
    unconditionally, and telling a piece the robot moved from one that moved on its own
    is the event system's question to answer over the corrections this class commits,
    not this class's own.
    """

    world: World
    """
    The twin whose pieces' believed poses this corrects.
    """

    look: Callable[[], List[PerceivedPose]]
    """
    Takes one look at the scene, in whatever way the caller has set up (a real camera in
    simulation, a live one on the robot).
    """

    is_idle: Callable[[], bool]
    """
    Whether the robot is not currently executing a manipulation action.

    While it is acting, the grasped piece already follows the gripper kinematically
    through the attachment mechanism, so :meth:`tick` does nothing at all rather than
    contending with perception it has no need to consult.
    """

    minimum_period: float = 0.5
    """
    Shortest time between two looks, in seconds.

    Matches :class:`~experiments.montessori.perception.node.MontessoriPerceptionNode`'s
    own ``minimum_period``: idle re-perception is not time-critical, so it is throttled
    the same way the continuous node throttles its own camera-rate pipeline runs.
    """

    _last_look: float = field(init=False, default=float("-inf"))
    """
    When :meth:`tick` last actually took a look, as a monotonic timestamp.

    Starts at negative infinity rather than zero, so the very first tick is never
    throttled regardless of what clock value ``now`` starts counting from.
    """

    def tick(self, now: float) -> List[MontessoriShape]:
        """
        Take a look and write what it found onto the twin, if it is time to and the
        robot is idle.

        :param now: The current time, as whatever clock the caller's ``minimum_period``
            is measured against.
        :return: The pieces whose believed pose was written.
        """
        if not self.is_idle():
            return []
        if now - self._last_look < self.minimum_period:
            return []
        self._last_look = now
        return self._commit_matched_pieces(self.look())

    def _commit_matched_pieces(
        self, perceived_poses: List[PerceivedPose]
    ) -> List[MontessoriShape]:
        """
        Match each perceived pose to the nearest believed piece of the same kind not
        already matched, and write it onto that piece unconditionally.

        :param perceived_poses: What the look found.
        :return: The pieces whose believed pose was written.
        """
        matched: set[MontessoriShape] = set()
        committed: List[MontessoriShape] = []
        for perceived in perceived_poses:
            piece = self._nearest_unmatched_piece(perceived, matched)
            if piece is None:
                continue
            matched.add(piece)
            self._commit(piece, perceived.role_taker)
            committed.append(piece)
        return committed

    def _nearest_unmatched_piece(
        self, perceived: PerceivedPose, matched: set[MontessoriShape]
    ) -> Optional[MontessoriShape]:
        """
        The believed piece of ``perceived``'s own kind standing closest to where it was
        seen, excluding pieces a look already matched this tick.

        Matches greedily by nearest position rather than solving general multi-instance
        disambiguation -- adequate for the scenes this plan measures, and no weaker than
        :func:`~coraplex.perception.Detection.apply_to`, which raises rather than
        disambiguating an annotation that resolves to more than one body.

        :param perceived: The perceived pose to match.
        :param matched: Pieces already matched earlier this tick.
        :return: The nearest candidate, or None if every piece of that kind is already
            matched.
        """
        candidates = [
            piece
            for piece in self.world.get_semantic_annotations_by_type(MontessoriShape)
            if piece.shape_category == perceived.category and piece not in matched
        ]
        if not candidates:
            return None
        target = self._position_of(perceived.role_taker)
        return min(
            candidates,
            key=lambda piece: float(
                np.linalg.norm(self._believed_position(piece) - target)
            ),
        )

    def _commit(self, piece: MontessoriShape, pose: Pose) -> None:
        """
        Write ``pose`` onto ``piece``'s own connection.

        State, not structure: the piece already exists in the twin, so this only moves
        it, the same way a later look already writes a new placement into the connection
        an earlier one built.

        :param piece: The piece whose believed pose is corrected.
        :param pose: Where it was just seen.
        """
        connection = piece.root.parent_connection
        connection.origin = self.world.transform(
            pose, connection.parent
        ).to_homogeneous_matrix()

    def _believed_position(self, piece: MontessoriShape) -> np.ndarray:
        """
        Where the twin currently believes ``piece`` stands, in the world root's frame.

        :param piece: The piece to locate.
        """
        return self.world.compute_forward_kinematics_np(self.world.root, piece.root)[
            :3, 3
        ]

    def _position_of(self, pose: Pose) -> np.ndarray:
        """
        ``pose``'s position, in the world root's frame.

        :param pose: The pose to read.
        """
        return self.world.transform(pose, self.world.root).to_position().to_np()[:3]
