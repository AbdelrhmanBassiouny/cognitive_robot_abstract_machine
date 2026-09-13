"""
Which hole a piece goes through, decided by rules.

Every piece of the set goes through the hole shaped like it, which is the whole of what
the board is for -- and it is knowledge about this board rather than geometry anything
can be read off, because a hole a piece merely fits is not the hole it belongs in. So
the shape of the hole is concluded by a tree of ripple-down rules stated over the piece:
a piece the rules get wrong is answered by adding a rule rather than by editing the ones
already stated, and the tree can be read as well as run.

What the rules conclude is narrowed further by the statement itself: the hole is then
selected out of the ones the board actually has, and the relation the statement asserts
is read again over each candidate, so the rules choose but never decide alone.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from typing_extensions import Any, ClassVar, Dict, Iterable, List, Optional

from experiments.montessori.semantics import (
    MontessoriShape,
    MontessoriShapeCategory,
    ShapeSortingHole,
)
from krrood.entity_query_language.backends import (
    QueryBackend,
    object_stated_by,
    relations_stated_in,
)
from krrood.entity_query_language.evaluable import Evaluable
from krrood.entity_query_language.factories import (
    ConditionType,
    a,
    add,
    alternative,
    entity,
)
from krrood.entity_query_language.predicate import Triple
from krrood.entity_query_language.query.match import Match
from krrood.entity_query_language.query.query import Entity
from krrood.entity_query_language.rdr.answer_vocabulary import AnswerName
from krrood.entity_query_language.rdr.expert import Expert
from krrood.entity_query_language.rdr.interface import (
    AnswerRequest,
    CaseContext,
    FunctionInterface,
)
from krrood.entity_query_language.rdr.serialization import NullModelSaver
from krrood.entity_query_language.rdr.single_class import EQLSingleClassRDR
from krrood.entity_query_language.utils import T
from krrood.entity_query_language.verbalization.vocabulary.english import Directive
from krrood.entity_query_language.verbalization.vocabulary.parts_of_speech import (
    Noun,
    Verb,
    clause,
)

SHAPE_STATED_BY_THE_HOLE = "shape_category"
"""
The attribute of a hole the rules conclude, by the name the hole gives it.
"""

# %% what a statement says a hole is wanted for


@dataclass(eq=False)
class Admits(Triple):
    """
    Asserts that a hole takes one piece.

    Stated about the hole rather than about the piece, since the hole is what is being
    looked for and the piece is what is already known.
    """

    hole: ShapeSortingHole
    """
    The hole the piece goes through.
    """

    piece: MontessoriShape
    """
    The piece that goes through it.
    """

    @property
    def subject(self) -> ShapeSortingHole:
        return self.hole

    @property
    def object(self) -> MontessoriShape:
        return self.piece

    def __call__(self) -> bool:
        return self.piece.fits_through(self.hole)

    @classmethod
    def _verbalization_fragment_(cls, fields):
        return clause(Noun(fields["hole"]), Verb("admit"), Noun(fields["piece"]))


# %% what the rules read


@dataclass(frozen=True, eq=False)
class PieceToSort:
    """
    One piece, and the shape of the hole it goes through, left open for the rules.

    ..note:: Compared by identity: a piece holds its outline as an array, which does not
        compare as a value.
    """

    piece: MontessoriShape
    """
    The piece being sorted, as the world holds it.
    """

    hole_shape: Optional[MontessoriShapeCategory] = None
    """
    The shape of the hole it goes through, left open for the rules to conclude.

    A case stating nothing here is one still to be decided, which is what the rules are
    asked about; one carrying a shape has been decided already.
    """


# %% the rules themselves


@dataclass
class HoleShapeRules:
    """
    The rule tree that says what shape of hole a piece goes through.

    Its rules are krrood ripple-down rules whose conditions are entity query language
    expressions over the piece itself, so a piece the rules get wrong is corrected by
    adding a rule rather than by editing the ones already stated.
    """

    rules: EQLSingleClassRDR = field(init=False, repr=False, compare=False)
    """
    The rules themselves, as one tree that outlives the pieces it decides.
    """

    expert: Expert = field(init=False, repr=False, compare=False)
    """
    Asked for a new rule's condition, which it reads off
    :meth:`state_the_condition_this_rule_needs`.
    """

    def __post_init__(self) -> None:
        self.expert = Expert(
            interface=FunctionInterface(
                answer_function=self.state_the_condition_this_rule_needs
            )
        )
        self.rules = EQLSingleClassRDR.from_underspecified(
            a(PieceToSort)(hole_shape=...), model_saver=NullModelSaver()
        )
        self.rules.state_rules(self.rules_stated_at_the_start())

    def state_the_condition_this_rule_needs(
        self, context: CaseContext, requests: List[AnswerRequest]
    ) -> Dict[AnswerName, Any]:
        """
        Answer the engine's question about a new rule: what was stated about one piece
        holds for every piece shaped like it, which is the grain the board itself is cut
        at.

        :param context: The piece being fitted, and the shape it is fitted to.
        :param requests: The answers asked for, which this reads nothing from.
        :return: The conditions answer.
        """
        return {
            AnswerName.CONDITIONS: context.case_variable.piece.shape_category
            == context.case_instance.piece.shape_category
        }

    @property
    def case(self) -> PieceToSort:
        """
        The variable every rule is stated over.
        """
        return self.rules.case_variable

    @property
    def concluded_shape(self) -> MontessoriShapeCategory:
        """
        The attribute every rule concludes on.
        """
        return self.rules.conclusion_variable

    def rules_stated_at_the_start(self) -> Entity:
        """
        A piece goes through the hole shaped like it, which is what the board is for and
        what every piece of this set does.
        """
        shapes = list(MontessoriShapeCategory)
        first, rest = shapes[0], shapes[1:]
        rules = entity(self.case).where(self.case.piece.shape_category == first)
        with rules:
            add(self.concluded_shape, first)
            for shape in rest:
                with alternative(self.case.piece.shape_category == shape):
                    add(self.concluded_shape, shape)
        return rules

    def shape_for(self, piece: MontessoriShape) -> Optional[MontessoriShapeCategory]:
        """
        The shape of the hole a piece goes through.

        :param piece: The piece being sorted.
        :return: The shape the rules conclude, or None where no rule reaches it.
        """
        concluded = self.rules.classify(PieceToSort(piece))
        return None if concluded is ... else concluded

    def add_rule(
        self, piece: MontessoriShape, hole_shape: MontessoriShapeCategory
    ) -> None:
        """
        State a piece the rules do not yet answer for, or answer wrongly.

        The rule joins the tree already in use, so such a piece is answered this way
        from the next call onwards without any of the rules already stated being
        rewritten.

        :param piece: The piece the rules were asked about.
        :param hole_shape: The shape of the hole it actually goes through.
        """
        self.rules.fit_case(PieceToSort(piece), hole_shape, self.expert)


# %% the backend


@dataclass(eq=False)
class HoleRulesBackend(QueryBackend):
    """
    Answers a statement about the hole a piece goes through, by concluding the shape of
    that hole from the piece and selecting the board's holes of that shape.

    Neither of the two kinds of backend a statement usually meets. Nothing is
    constructed -- the board's holes are things the world already holds -- but the
    statement leaves the hole's shape unstated, which a backend that only selects has
    nothing to fill in from. These rules are what it is filled in from, and the
    selecting is what happens afterwards.
    """

    opening_directive: ClassVar[Optional[Directive]] = Directive.FIND
    """
    The hole is found among the ones the board has, so this reads as *"Find …"*.
    """

    rules: HoleShapeRules = field(default_factory=HoleShapeRules)
    """
    What says which shape of hole a piece goes through.
    """

    def capability(self, statement: Evaluable) -> ConditionType:
        """
        A statement about a hole whose shape it leaves open, said to be for one piece
        the statement names: the rules conclude the shape from that piece, so a
        statement naming no piece is one they have nothing to conclude from.
        """
        return (
            isinstance(statement, Match)
            and statement._type_ is not None
            and issubclass(statement._type_, ShapeSortingHole)
            and statement._kwargs_.get(SHAPE_STATED_BY_THE_HOLE) is ...
            and self.piece_the_hole_is_wanted_for(statement) is not None
        )

    def evaluate(self, expression: Match[T]) -> Iterable[T]:
        """
        Conclude the shape of the hole wanted, and select the holes of that shape the
        statement admits.

        :param expression: The statement to answer.
        :return: Every hole it is answered by, which is none where no rule reaches the
            piece.
        """
        piece = self.piece_the_hole_is_wanted_for(expression)
        shape = self.rules.shape_for(piece)
        if shape is None:
            return
        yield from expression.answering(
            SHAPE_STATED_BY_THE_HOLE, shape
        )._evaluate_natively_()

    @staticmethod
    def piece_the_hole_is_wanted_for(
        statement: Match[T],
    ) -> Optional[MontessoriShape]:
        """
        :param statement: The statement to read.
        :return: The piece it says the hole is wanted for, or None where it names none.
        """
        pieces: List[MontessoriShape] = [
            object_stated_by(stated)
            for stated in relations_stated_in(statement)
            if stated._type_ is Admits
        ]
        return pieces[0] if len(pieces) == 1 else None
