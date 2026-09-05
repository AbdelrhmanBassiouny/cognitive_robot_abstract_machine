"""
The demonstration: one statement about the Montessori scene, watched as it is read.

Run it as::

    python -m experiments.montessori.perception.watch_narrowing

The statement says the whole of it -- what the piece rests on, which way it lies from
two of the board's own holes, what colour it is, and what those things it is related to
are -- and :func:`~experiments.montessori.perception.step_by_step.show_step_by_step`
does the rest: it takes the look, reads the statement one stated condition at a time,
and draws what each one leaves. Press any key for the next condition; press ``q`` or
escape to stop.
"""

from __future__ import annotations

import logging

from experiments.montessori.hole_geometry import HOLE_NAME_BY_CATEGORY
from experiments.montessori.perception.detections import DetectedMontessoriShape
from experiments.montessori.perception.recorded_setup import board_holes_in, lid_surface
from experiments.montessori.perception.step_by_step import (
    RecordedLook,
    WatchedCapture,
    show_step_by_step,
)
from experiments.montessori.pieces import KNOWN_PIECE_BY_CATEGORY
from experiments.montessori.semantics import MontessoriShapeCategory
from krrood.entity_query_language.factories import a, variable
from krrood.entity_query_language.query.match import Match
from semantic_digital_twin.reasoning.predicates import (
    Above,
    Colored,
    LeftOf,
    SupportedBy,
)
from semantic_digital_twin.world_description.world_entity import Body


def look_for_the_cube_on_the_lid(
    look: RecordedLook,
) -> Match[DetectedMontessoriShape]:
    """
    The statement the demonstration watches, written whole: the piece it is looking for,
    the things it says that piece stands in relation to, and every one of those
    relations.

    Nothing is fetched out of the world beforehand. The lid and the two holes are
    described in the statement itself, by what the world calls them -- the lid beside
    the relation naming it, each hole as a statement of its own handed to the relation
    in its place -- and answering those descriptions is the backend's own first move,
    which is what lets the relations that mention them narrow the look at all.

    Support first, because it is the narrowing the request language already had and the
    one the digital twin answers by itself: naming the surface names a stretch of a
    plane the world describes. Directions from two of the board's own holes second,
    because they are the world's own vocabulary saying where on that surface to look.
    The colour last, because it narrows what is worth fitting rather than where to fit
    it, and so is the one narrowing a picture of the region cannot show on its own.

    A direction is read from where the camera stands, so left, right and above mean what
    they mean on screen. Which of them tells the two pieces on the lid apart is measured
    rather than assumed: on ``tracy_pickup_demo`` the cube stands left of the square
    hole in the picture and above the triangle hole, and the cylinder stands right of
    the one and below the other.

    :param look: The look the statement is about, which is what says where the board
        stands; its holes are put in that look's world here so the statement can
        describe two of them.
    :return: The whole statement.
    """
    board_holes_in(look.world, look.board)
    lid = variable(Body, look.world.bodies)
    cube = KNOWN_PIECE_BY_CATEGORY[MontessoriShapeCategory.CUBE]
    triangle = KNOWN_PIECE_BY_CATEGORY[MontessoriShapeCategory.TRIANGULAR_PRISM]
    square_hole = a(Body)().from_(look.world.bodies)
    square_hole.where(
        square_hole.variable.name.name == HOLE_NAME_BY_CATEGORY[cube.category]
    )
    triangle_hole = a(Body)().from_(look.world.bodies)
    triangle_hole.where(
        triangle_hole.variable.name.name == HOLE_NAME_BY_CATEGORY[triangle.category]
    )
    sought = a(DetectedMontessoriShape)()
    return sought.where(
        lid.name == lid_surface().name,
        SupportedBy(sought.variable, lid),
        LeftOf(sought.variable, square_hole.expression, look.seen_from),
        Above(sought.variable, triangle_hole.expression, look.seen_from),
        Colored(sought.variable, cube.color),
    )


def main() -> None:
    """
    Watch that statement being read, on a capture named on the command line.
    """
    logging.basicConfig(level=logging.INFO)
    show_step_by_step(look_for_the_cube_on_the_lid, WatchedCapture.from_command_line())


if __name__ == "__main__":
    main()
