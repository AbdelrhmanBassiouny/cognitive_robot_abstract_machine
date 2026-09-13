"""
A sorting run whose plan leaves its slots open.

The run is the same one: every piece the look put on the table is picked up and let go
over the hole it belongs in. What differs is that the hole is *stated* rather than
looked up -- as the target of putting this piece through this board, with the shape of
that hole left for whoever can conclude it -- and the backends answer it.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from coraplex.robot_plans.actions.core.insertion import InsertionAction
from experiments.montessori.exceptions import NoMatchingHoleError
from experiments.montessori.semantics import MontessoriShape, ShapeSortingHole
from krrood.entity_query_language.backends import BackendChoice
from krrood.entity_query_language.factories import a, an
from krrood.entity_query_language.query.match import Match

from experiments.tracy_experiments.pickup.perceived_sorting import PerceivedSorting


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
        The hole a piece goes through, as the backends answer the one slot this run's
        statement leaves open.

        :param piece: A piece the world holds.
        :return: The first hole they answer with, which is the closest fit of the ones
            the piece goes through.
        :raises NoMatchingHoleError: If they answer with none.
        """
        [wanted] = self.insertion_wanted_for(piece)._stated_matches_
        answers = list(self.backends.evaluate(wanted))
        if not answers:
            raise NoMatchingHoleError(piece, self.board)
        return answers[0]

    def insertion_wanted_for(self, piece: MontessoriShape) -> Match[InsertionAction]:
        """
        What this run says about putting a piece through the board: this piece, through
        a hole of this board.

        The shape of that hole is left open, because which shape of hole a piece belongs
        in is knowledge about this board rather than anything the plan states. Saying it
        as the target of an insertion of this piece is what tells whoever answers it
        what the hole is for, so nothing else has to be added to the description of the
        hole for their sake.

        :param piece: The piece the hole is wanted for.
        :return: The statement.
        """
        return an(InsertionAction)(
            object_designator=piece.root,
            target=a(ShapeSortingHole)(shape_category=...).from_(self.board.apertures),
        )
