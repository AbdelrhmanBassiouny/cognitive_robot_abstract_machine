"""
The backends a Montessori sorting plan is run with, and which is preferred over which.

A plan states four things it does not supply -- the piece to pick up, whether it is
where the plan needs it to be, how to take hold of it, and the hole to put it through --
and each is answered by a different faculty. What answers which is not written into the
plan: every backend declares what it can answer, and the choice asks them in the order
stated here.
"""

from __future__ import annotations

from experiments.montessori.perception.backend import MontessoriPerceptionBackend
from experiments.open_slots.holes import HoleRulesBackend
from experiments.open_slots.world import WorldBackend
from krrood.entity_query_language.backends import BackendChoice, ProbabilisticBackend
from semantic_digital_twin.world import World


def backends_for(looking: MontessoriPerceptionBackend, world: World) -> BackendChoice:
    """
    The four backends that answer a sorting plan's open slots, in the order they are
    preferred.

    The look comes first: it alone reports a thing nobody has seen yet, and nothing else
    can answer a statement about one. The world comes next, because a thing it already
    holds is to be found rather than invented, and a relation between two of them is
    read off their geometry there. Then the rules, which answer what no amount of
    looking or measuring settles: which hole a piece belongs in. The probabilistic
    backend comes last because it answers any pattern at all, which makes it the one
    that supplies what nothing else has -- how to take hold of a piece, say.

    :param looking: The backend that answers by looking at the scene.
    :param world: The world the robot plans in, which is also where a look's findings
        are stood.
    :return: The choice to run the plan with.
    """
    return BackendChoice(
        backends=[
            looking,
            WorldBackend(world=world),
            HoleRulesBackend(),
            ProbabilisticBackend(),
        ]
    )
