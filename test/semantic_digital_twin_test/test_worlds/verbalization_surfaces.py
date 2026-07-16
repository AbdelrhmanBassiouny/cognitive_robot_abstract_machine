"""
Committed verbalization surfaces for semantic_digital_twin's symbolic callables.

The snapshot for :mod:`test_verbalization_surfaces` -- one
:class:`~krrood.entity_query_language.verbalization.surface_verification.VerbalizationSurface`
per covered predicate / symbolic function, referencing the class itself (so a rename or removal
breaks this import) and its approved sentence. Update an entry when the surface-match test
prints a new sentence for an intentional change.
"""

from __future__ import annotations

from typing_extensions import Tuple

from krrood.entity_query_language.verbalization.surface_verification import (
    VerbalizationSurface,
)
from semantic_digital_twin.reasoning.predicates import (
    Above,
    AllClose,
    Behind,
    Below,
    BodyInRegionFraction,
    Contact,
    ContainsType,
    EuclideanPlanarDistance,
    GetVisibleBodies,
    InFrontOf,
    InsideOf,
    IsPlaceOccupied,
    IsSupportedBy,
    IsSupporting,
    LeftOf,
    OccludingBodies,
    Reachable,
    RightOf,
    Stable,
    Visible,
)
from semantic_digital_twin.reasoning.queries import (
    AnnotationVolume,
    ClassNameLowercased,
)
from semantic_digital_twin.reasoning.robot_predicates import (
    BlockingBodies,
    BodiesInGripper,
    BodyInGripperFraction,
    IsGripperHoldingSomething,
    IsPoseFreeForRobot,
    RobotCollisions,
    RobotHoldsBody,
)

SURFACES: Tuple[VerbalizationSurface, ...] = (
    VerbalizationSurface(Above, "Point3 1 is above Point3 2"),
    VerbalizationSurface(
        AllClose,
        "each element of ndarray 1 is close to the matching element of ndarray 2",
    ),
    VerbalizationSurface(Behind, "Point3 1 is behind Point3 2"),
    VerbalizationSurface(Below, "Point3 1 is below Point3 2"),
    VerbalizationSurface(
        BodyInRegionFraction, "the body in region fraction of a Body and a Region"
    ),
    VerbalizationSurface(Contact, "Body 1 is in contact with Body 2"),
    VerbalizationSurface(ContainsType, "object 1 contains an instance of object 2"),
    VerbalizationSurface(
        EuclideanPlanarDistance,
        "the euclidean planar distance of Body 1, Body 2, and a Vector3",
    ),
    VerbalizationSurface(GetVisibleBodies, "the visible bodies of a Camera"),
    VerbalizationSurface(InFrontOf, "Point3 1 is in front of Point3 2"),
    VerbalizationSurface(
        InsideOf, "KinematicStructureEntity 1 is inside of KinematicStructureEntity 2"
    ),
    VerbalizationSurface(
        IsPlaceOccupied,
        "place occupied holds given a BoundingBox, a Pose, a World, and a Body",
    ),
    VerbalizationSurface(
        IsSupportedBy, "Body 1 is supported by Body 2 a floating-point number"
    ),
    VerbalizationSurface(
        IsSupporting, "supporting holds given a Body and a floating-point number"
    ),
    VerbalizationSurface(LeftOf, "Point3 1 is left of Point3 2"),
    VerbalizationSurface(
        OccludingBodies, "the occluding bodies of a Camera and a Body"
    ),
    VerbalizationSurface(
        Reachable, "a HomogeneousTransformationMatrix is reachable by Body 2"
    ),
    VerbalizationSurface(RightOf, "Point3 1 is right of Point3 2"),
    VerbalizationSurface(Stable, "a Body is stable"),
    VerbalizationSurface(
        Visible, "a KinematicStructureEntity is visible from a Camera"
    ),
    VerbalizationSurface(
        AnnotationVolume, "the annotation volume of a SemanticAnnotation"
    ),
    VerbalizationSurface(ClassNameLowercased, "the class name lowercased of a type"),
    VerbalizationSurface(
        BlockingBodies,
        "the blocking bodies of a HomogeneousTransformationMatrix, Body 1, and Body 2",
    ),
    VerbalizationSurface(
        BodiesInGripper, "the bodies in gripper of a HasTwoFingers and an Integer"
    ),
    VerbalizationSurface(
        BodyInGripperFraction,
        "the body in gripper fraction of a Body, an EndEffector, and an Integer",
    ),
    VerbalizationSurface(IsGripperHoldingSomething, "an EndEffector holds something"),
    VerbalizationSurface(IsPoseFreeForRobot, "a Pose is free for an AbstractRobot"),
    VerbalizationSurface(
        RobotCollisions,
        "the robot collisions of an AbstractRobot, an object, and a floating-point number",
    ),
    VerbalizationSurface(RobotHoldsBody, "an AbstractRobot holds a Body"),
)
