"""
Contact-friction tuning for a MuJoCo-simulated gripper's grasp on a loose object and for
the surface it is released onto, generalized from ``coraplex_panda_demo``'s own
reliably-grasped cube.
"""

from __future__ import annotations

from typing_extensions import Iterable

from experiments.montessori.semantics import MontessoriShape, MontessoriShapeCategory
from experiments.tracy_experiments.equipment import _mujoco_geom_for
from semantic_digital_twin.world_description.world_entity import Body

GRASP_FRICTION = [0.3, 0.05, 0.001]
"""
Contact friction (sliding, torsional, rolling; see
:attr:`~semantic_digital_twin.adapters.multi_sim.MujocoGeom.friction`) given to every
loose shape's collision geometry.

History of the sliding component: started at ``coraplex_panda_demo``'s own ``1.0``
(tuned for a reliable grip between rubber fingertips, which keep their own separate
friction); lowered to ``0.5`` as an experiment to stop a shape landing centered and
upright on a hole's rim from staying stuck there; tried at ``1.0`` again for every shape
except the cube (a per-category override), which over a 90-run batch traded down overall
(blowup-magnitude physics instability jumped from 10% to 39% of runs, and pass rates for
rectangular_hole and circular_hole_2 fell rather than improving) -- so reverted back to
``0.5`` globally.

Now set to ``0.3``: contact friction is combined by MuJoCo as the element-wise maximum
of the two participating geoms, and the shape-sorting board's own collision geometry had
no friction set at all until :data:`BOARD_FRICTION`, defaulting to MuJoCo's own ``1.0``
sliding friction -- so every shape-board contact was silently pinned at ``1.0`` no matter
what this value was tuned to, and every prior experiment here was only ever testing the
finger-shape grip (where the fingertip's own ``~1.0`` friction dominates regardless of
this value), never the rim-sticking interaction it was meant to fix. ``0.3`` approximates
real sliding friction between painted wood/plastic surfaces (~0.25-0.4), now paired with
an equally explicit :data:`BOARD_FRICTION` so the shape-board contact can actually drop
below the finger-dominated grip instead of being masked by it.
"""

GRASP_FRICTION_OVERRIDES: dict[MontessoriShapeCategory, list[float]] = {}
"""
Per-:class:`~experiments.montessori.semantics.MontessoriShapeCategory` override of
:data:`GRASP_FRICTION`, used by :func:`apply_montessori_grasp_contact_parameters`. A
category absent from this mapping (currently all of them) uses :data:`GRASP_FRICTION`.
"""

BOARD_FRICTION = [0.3, 0.005, 0.0001]
"""
Contact friction (sliding, torsional, rolling) given to the shape-sorting board's
collision geometry via :func:`apply_contact_friction`.

Approximates real sliding friction between painted wood/plastic surfaces (~0.25-0.4),
matching :data:`GRASP_FRICTION`'s own sliding component so the shape-board contact is
governed by this pair rather than by MuJoCo's own ``1.0`` default the board previously
had no override for (see :data:`GRASP_FRICTION`'s docstring for why that masked every
prior friction experiment). Torsional and rolling use MuJoCo's own defaults rather than
:data:`GRASP_FRICTION`'s grip-stabilizing multiples of them, since the board is never
pinched between fingers.
"""

GRASP_SOLVER_REFERENCE = [0.008, 1.0]
"""
Contact solver reference (see
:attr:`~semantic_digital_twin.adapters.multi_sim.MujocoGeom.solver_reference`) given to
every loose shape, matching ``coraplex_panda_demo``'s cube (``solref="0.008"``).

Stiffer than MuJoCo's own default (``0.02``): a soft contact lets a pinched shape sink
into the fingers and then slip back out as the arm lifts, rather than being held solidly
between them.
"""

GRASP_SOLVER_IMPEDANCE = [0.96, 0.99, 0.001, 0.5, 2.0]
"""
Contact solver impedance (see
:attr:`~semantic_digital_twin.adapters.multi_sim.MujocoGeom.solver_impedance`) given to
every loose shape, matching ``coraplex_panda_demo``'s cube (``solimp="0.96 0.99"``, the
remaining three values MuJoCo's own defaults).

Harder than MuJoCo's own default (``0.9 0.95``), for the same reason as
:data:`GRASP_SOLVER_REFERENCE`.
"""


def apply_contact_friction(bodies: Iterable[Body], friction: list[float]) -> None:
    """
    Give every collision geometry of every body in ``bodies`` the given contact
    friction (see :attr:`~semantic_digital_twin.adapters.multi_sim.MujocoGeom.friction`),
    without touching solver reference or impedance (see
    :func:`apply_grasp_contact_parameters` for a grasped-shape variant that also sets
    those).

    :param bodies: The bodies to modify in place.
    :param friction: Contact friction to give every body's collision geometry.
    """
    for body in bodies:
        for geometry in body.collision:
            _mujoco_geom_for(geometry).friction = list(friction)


def apply_grasp_contact_parameters(
    shapes: Iterable[Body], friction: list[float]
) -> None:
    """
    Give every body in ``shapes`` the contact parameters that let a gripper pick it up
    and hold it: ``friction`` plus the solver reference and solver impedance of
    ``coraplex_panda_demo``'s own reliably-grasped cube (see :data:`GRASP_FRICTION`,
    :data:`GRASP_SOLVER_REFERENCE`, :data:`GRASP_SOLVER_IMPEDANCE`).

    :param shapes: The bodies to modify in place.
    :param friction: Contact friction to give every body's collision geometry.
    """
    for shape in shapes:
        for geometry in shape.collision:
            mujoco_geom = _mujoco_geom_for(geometry)
            mujoco_geom.friction = list(friction)
            mujoco_geom.solver_reference = list(GRASP_SOLVER_REFERENCE)
            mujoco_geom.solver_impedance = list(GRASP_SOLVER_IMPEDANCE)


def apply_montessori_grasp_contact_parameters(
    shapes: Iterable[MontessoriShape],
) -> None:
    """
    :func:`apply_grasp_contact_parameters` for a mix of Montessori shapes, giving each
    its own :attr:`~experiments.montessori.semantics.MontessoriShape.shape_category`'s
    friction (see :data:`GRASP_FRICTION_OVERRIDES`).

    :param shapes: The shapes to modify in place.
    """
    for shape in shapes:
        friction = GRASP_FRICTION_OVERRIDES.get(shape.shape_category, GRASP_FRICTION)
        apply_grasp_contact_parameters([shape.root], friction)
