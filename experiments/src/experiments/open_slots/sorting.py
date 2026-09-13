"""
A sorting run whose plan leaves its slots open.

The run is the same one: every piece the look put on the table is picked up and let go
over the hole it belongs in. What differs is that the hole is *stated* rather than
looked up -- the plan says the smallest hole of this board that admits this piece, with
the shape of that hole left for whoever can conclude it -- and the backends answer it.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from experiments.montessori.exceptions import NoMatchingHoleError
from experiments.montessori.semantics import MontessoriShape, ShapeSortingHole
from experiments.open_slots.holes import Admits
from experiments.tracy_experiments.pickup.perceived_sorting import PerceivedSorting
from krrood.entity_query_language.backends import BackendChoice
from krrood.entity_query_language.factories import a
from krrood.entity_query_language.query.match import Match


@dataclass
class SortingByAnOpenPlan(PerceivedSorting):
    """
    A sorting run that asks for the hole each piece goes through instead of looking it
    up.
    """

    backends: BackendChoice = field(kw_only=True)
    """
    The backends the statements this run makes are answered by.
    """

    def hole_for(self, piece: MontessoriShape) -> ShapeSortingHole:
        """
        The hole a piece goes through, as the backends answer it.

        :param piece: A piece the world holds.
        :return: The first hole they answer with, which is the smallest one that admits
            the piece.
        :raises NoMatchingHoleError: If they answer with none.
        """
        answers = list(self.backends.evaluate(self.hole_wanted_for(piece)))
        if not answers:
            raise NoMatchingHoleError(piece, self.board)
        return answers[0]

    def hole_wanted_for(self, piece: MontessoriShape) -> Match[ShapeSortingHole]:
        """
        What this run says about the hole it wants.

        The shape of the hole is left open, because which shape of hole a piece belongs
        in is knowledge about this board rather than anything the plan states; that it
        must be a hole of this board, that it must admit this piece, and that the
        smallest such hole is the one wanted, are what the plan does state.

        :param piece: The piece the hole is wanted for.
        :return: The statement.
        """
        hole = a(ShapeSortingHole)(shape_category=...).from_(self.board.apertures)
        hole = hole.where(Admits(hole, piece))
        return hole.ordered_by(hole.cross_section_size)
