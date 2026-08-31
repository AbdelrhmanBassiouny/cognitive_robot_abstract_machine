"""
A selective backend that answers a query by looking at the world rather than by
recalling it, mimicking the shape a backend over a sensor takes.

Such a backend supplies the domain itself: it takes what it can of the query's
conditions into the look, leaves the rest for the query's own evaluation to apply over
what came back, and refuses a condition it can do neither with.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from typing_extensions import ClassVar, Iterable, List, Optional

from krrood.entity_query_language.backends import AttributeEqualityToLiteral, SelectiveBackend
from krrood.entity_query_language.core.base_expressions import Selectable
from krrood.entity_query_language.evaluable import Evaluable
from krrood.entity_query_language.exceptions import BackendCannotResolveCondition
from krrood.entity_query_language.query.query import Query
from krrood.entity_query_language.verbalization.vocabulary.english import Directive

# %% what a look finds


@dataclass(frozen=True)
class Sighting:
    """
    One thing a look found, and where it was standing.
    """

    label: str
    """
    What it was recognised as.
    """

    place: str
    """
    What the world calls the place it was found in.
    """


# %% the backend


@dataclass
class BackendThatLooksAtTheWorld(SelectiveBackend):
    """
    Answers a query by looking, over a fixed set of sightings standing in for a scene.
    """

    opening_directive: ClassVar[Optional[Directive]] = Directive.LOOK_FOR
    """
    Going to look reads as *"Look for …"*.
    """

    sightings: List[Sighting] = field(default_factory=list)
    """
    Everything a look could find, were it to search everywhere.
    """

    searched_place: Optional[str] = field(init=False, default=None)
    """
    The place the last evaluated query narrowed the look to, or ``None`` when it named
    none.
    """

    PLACE_ATTRIBUTE_NAME: ClassVar[str] = "place"
    """
    The attribute of a sighting a condition narrows the look by.
    """

    def _evaluate(self, expression: Query) -> Iterable:
        """
        Look for what the query asks about, then let the query itself filter what came
        back.

        :param expression: The query to answer.
        :raises BackendCannotResolveCondition: If a condition constrains anything other
            than the variable being selected, which a look can neither narrow to nor
            filter on.
        """
        [selection] = expression._selected_variables_
        self.searched_place = None
        for condition in self._conditions_of(expression):
            self._narrow_by(condition, selection)
        selection._update_domain_(self._look())
        yield from expression._evaluate_natively_()

    @staticmethod
    def _conditions_of(expression: Query) -> Iterable[Evaluable]:
        """
        :param expression: The query to read.
        :return: Its own ``where`` conditions, empty when it states none.
        """
        builder = expression._where_builder_
        return builder.conditions if builder is not None else ()

    def _narrow_by(self, condition: Evaluable, selection: Selectable) -> None:
        """
        Take into the look whatever this condition says about where to search.

        A condition over the selected variable that the look cannot act on is left for
        the query's own evaluation to apply afterwards.

        :param condition: The condition to read.
        :param selection: The variable the query selects.
        :raises BackendCannotResolveCondition: If the condition constrains any other
            variable.
        """
        if condition._constrained_variables_ - {selection}:
            raise BackendCannotResolveCondition(condition, type(self))
        equality = AttributeEqualityToLiteral.read_from(condition, selection)
        if (
            equality is not None
            and equality.attribute_name == self.PLACE_ATTRIBUTE_NAME
        ):
            self.searched_place = equality.value

    def _look(self) -> List[Sighting]:
        """
        :return: What a look narrowed to :attr:`searched_place` finds, or everything when
            no condition narrowed it.
        """
        if self.searched_place is None:
            return list(self.sightings)
        return [
            sighting
            for sighting in self.sightings
            if sighting.place == self.searched_place
        ]
