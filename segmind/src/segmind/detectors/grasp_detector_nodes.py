from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

from giskardpy.motion_statechart.context import MotionStatechartContext
from segmind.datastructures.events import DetectionEvent, GraspEvent, LossOfGraspEvent
from segmind.detectors.base import AbstractDetector, SegmindContext
from semantic_digital_twin.reasoning.predicates import contact
from semantic_digital_twin.world_description.world_entity import Body

TCP_PROXIMITY_THRESHOLD = 0.05
"""
Maximum distance, in metres, between a tracked object and a gripper's tool center point
for :class:`GraspDetector` to consider it close enough to be grasped.

The tool center point is a massless URDF link with no collision geometry of its own, so
unlike the two fingers it can never register a real mesh contact; a properly grasped
object's own centre sits close to it by construction (a pick action aims the gripper's
own finger midpoint, which the tool center point tracks, at the object's centre -- see
:func:`~experiments.tracy_experiments.pick_and_place_action._top_down_pose_builder`).
Not yet empirically validated against a real grasp on any particular robot's own scale
of object -- tune down if it is triggering while the object is still merely nearby, or
up if a genuine grasp is not being recognized.
"""


@dataclass(eq=False, repr=False)
class BaseGraspDetector(AbstractDetector):
    """
    Abstract base class for grasp-based detectors.

    Provides shared functionality for checking whether a tracked object is currently
    held by a gripper: in contact with both of its fingers, and close to its tool center
    point (see :data:`TCP_PROXIMITY_THRESHOLD`).
    """

    finger_tips: List[Body] = field(default_factory=list, kw_only=True)
    """
    The gripper's own two fingertip bodies, both required to be in contact with a
    tracked object for it to count as grasped.
    """

    tool_frame: Body = field(kw_only=True, default=None)
    """
    The gripper's own tool center point body.
    """

    tcp_proximity_threshold: float = TCP_PROXIMITY_THRESHOLD
    """
    See :data:`TCP_PROXIMITY_THRESHOLD`.
    """

    def get_grasped_objects(self, tracked_objects: List[Body]) -> List[Body]:
        """
        Which of ``tracked_objects`` are currently grasped.

        :param tracked_objects: Bodies that should be checked.
        :return: The subset of ``tracked_objects`` in contact with every one of
            :attr:`finger_tips` and within :attr:`tcp_proximity_threshold` of
            :attr:`tool_frame`.
        """
        return [obj for obj in tracked_objects if self._is_grasped(obj)]

    def _is_grasped(self, obj: Body) -> bool:
        if not all(contact(obj, finger_tip) for finger_tip in self.finger_tips):
            return False
        distance_to_tcp = obj.global_pose.to_position().euclidean_distance(
            self.tool_frame.global_pose.to_position()
        )
        return distance_to_tcp <= self.tcp_proximity_threshold


@dataclass(eq=False, repr=False)
class GraspDetector(BaseGraspDetector):
    """
    Detects when a tracked object starts being grasped by a gripper.
    """

    def update_context_and_events(
        self,
        context: MotionStatechartContext,
        segmind_context: SegmindContext,
        tracked_objects: List[Body],
    ) -> List[DetectionEvent]:
        """
        Detects newly grasped objects.

        :param context: The current motion statechart context.
        :param segmind_context: The shared SegmindContext containing the information required to track events.
        :param tracked_objects: Bodies that should be evaluated for newly starting grasps.
        :return: List of GraspEvent objects representing newly detected grasps.
        """
        events = []
        for obj in self.get_grasped_objects(tracked_objects):
            if obj in segmind_context.latest_grasp:
                continue
            segmind_context.latest_grasp.add(obj)
            events.append(GraspEvent(tracked_object=obj, with_object=self.tool_frame))

        return events


@dataclass(eq=False, repr=False)
class LossOfGraspDetector(BaseGraspDetector):
    """
    Detects when a tracked object previously grasped by a gripper (see
    :class:`GraspDetector`) is no longer held.
    """

    def update_context_and_events(
        self,
        context: MotionStatechartContext,
        segmind_context: SegmindContext,
        tracked_objects: List[Body],
    ) -> List[DetectionEvent]:
        """
        Detects grasps that are no longer held.

        :param context: The current motion statechart context.
        :param segmind_context: The shared SegmindContext containing the information required to track events.
        :param tracked_objects: Bodies that should be evaluated for lost grasps.
        :return: List of LossOfGraspEvent objects representing grasps that ended.
        """
        still_grasped = set(self.get_grasped_objects(tracked_objects))

        events = []
        for obj in tracked_objects:
            if obj not in segmind_context.latest_grasp or obj in still_grasped:
                continue
            segmind_context.latest_grasp.discard(obj)
            events.append(
                LossOfGraspEvent(tracked_object=obj, with_object=self.tool_frame)
            )

        return events
