"""
Working memory as a snapshot of the twin, refreshed only when it is worth refreshing.

While a piece is held, the twin already follows the gripper's kinematics through the
attachment mechanism -- perception has nothing to add and is not consulted. While idle,
a look is taken at a low rate, and a piece's believed pose is corrected only when the
newly perceived pose differs from it by more than a threshold, so that perception noise
on an unmoved piece is never mistaken for a piece that moved on its own.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

import numpy as np
from typing_extensions import List, Optional

from experiments.montessori.perception.detections import MontessoriScene
from experiments.montessori.semantics import MontessoriShape, MontessoriShapeCategory
from semantic_digital_twin.spatial_types.spatial_types import Pose
from semantic_digital_twin.world import World

# %% what a look reports

POSE_CHANGE_THRESHOLD_METERS = 1e-6
"""
How far a newly perceived position has to differ from the believed one before it is
committed, in metres.

Measured, not chosen: repeating a look at an unchanging simulated scene reproduces the
same detected position to within floating-point noise (~1e-15 m; see
``test_montessori_snapshot_working_memory.py``'s
``test_the_committed_threshold_matches_three_times_the_measured_position_noise``), so
three standard deviations of *that* noise would be a number too small to guard against
anything but the computation's own numerical floor. This default is a numerical safety
margin above that floor instead -- large enough that no repeated look ever crosses it on
its own, and still many orders of magnitude below any real piece movement.

The item's own description asks for the same measurement taken on the real robot, where
sensor noise is not zero. That number is not available in this environment and is
tracked separately (see ``icra-mechanism/roadmap.md``) rather than assumed here; once it
exists, it is the real gate and this simulated figure becomes the fallback for runs with
no such measurement.
"""


@dataclass(frozen=True)
class PerceivedPose:
    """
    A loose piece as one look reported it, narrowed to what deciding whether it moved
    needs.
    """

    category: MontessoriShapeCategory
    """
    The kind of piece perception recognised, matched against a believed piece of the
    same kind.
    """

    pose: Pose
    """
    Where it was seen.
    """


def perceived_poses_of(scene: MontessoriScene) -> List[PerceivedPose]:
    """
    The pieces one look found, narrowed to what :class:`SnapshotWorkingMemory` reads.

    :param scene: One pass of the perception pipeline.
    :return: One entry per piece the look found.
    """
    return [
        PerceivedPose(category=shape.category, pose=shape.pose)
        for shape in scene.shapes
    ]


# %% the snapshot itself


@dataclass
class SnapshotWorkingMemory:
    """
    Keeps the twin's belief about loose pieces a snapshot, refreshed only while idle and
    only where it actually changed.

    Nothing here decides *whether* the robot is idle or *how* a look is taken -- both
    are handed in, so this class depends on the fact of idleness and the fact of a look
    rather than on the gripper or the camera themselves.
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

    pose_change_threshold: float = POSE_CHANGE_THRESHOLD_METERS
    """
    How far a perceived position has to differ from the believed one, in metres, before
    :meth:`tick` commits it. See :data:`POSE_CHANGE_THRESHOLD_METERS`.
    """

    _last_look: float = field(init=False, default=float("-inf"))
    """
    When :meth:`tick` last actually took a look, as a monotonic timestamp.

    Starts at negative infinity rather than zero, so the very first tick is never
    throttled regardless of what clock value ``now`` starts counting from.
    """

    def tick(self, now: float) -> List[MontessoriShape]:
        """
        Take a look and correct whatever piece moved, if it is time to and the robot is
        idle.

        :param now: The current time, as whatever clock the caller's ``minimum_period``
            is measured against.
        :return: The pieces whose believed pose was corrected.
        """
        if not self.is_idle():
            return []
        if now - self._last_look < self.minimum_period:
            return []
        self._last_look = now
        return self._commit_changed_pieces(self.look())

    def _commit_changed_pieces(
        self, perceived_poses: List[PerceivedPose]
    ) -> List[MontessoriShape]:
        """
        Match each perceived pose to the nearest believed piece of the same kind not
        already matched, and commit it where it differs enough to matter.

        :param perceived_poses: What the look found.
        :return: The pieces whose believed pose was corrected.
        """
        matched: set[MontessoriShape] = set()
        committed: List[MontessoriShape] = []
        for perceived in perceived_poses:
            piece = self._nearest_unmatched_piece(perceived, matched)
            if piece is None:
                continue
            matched.add(piece)
            if self._has_moved(piece, perceived.pose):
                self._commit(piece, perceived.pose)
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
        target = self._position_of(perceived.pose)
        return min(
            candidates,
            key=lambda piece: float(
                np.linalg.norm(self._believed_position(piece) - target)
            ),
        )

    def _has_moved(self, piece: MontessoriShape, pose: Pose) -> bool:
        """
        Whether ``pose`` differs from ``piece``'s believed pose by more than
        :attr:`pose_change_threshold`.

        :param piece: The piece to compare against.
        :param pose: Where it was just seen.
        """
        distance = np.linalg.norm(
            self._believed_position(piece) - self._position_of(pose)
        )
        return distance > self.pose_change_threshold

    def _commit(self, piece: MontessoriShape, pose: Pose) -> None:
        """
        Write ``pose`` onto ``piece``'s own connection.

        State, not structure: the piece already exists in the twin, so this only moves
        it, the same way a later look already writes a new placement into the
        connection an earlier one built.

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
