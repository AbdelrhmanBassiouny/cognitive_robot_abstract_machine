from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing_extensions import TYPE_CHECKING, Dict, List

if TYPE_CHECKING:
    from krrood.entity_query_language.core.base_expressions import SymbolicExpression
    from krrood.entity_query_language.verbalization.fragments.base import (
        VerbalizationFragment,
    )


@dataclass
class BindingScope:
    """
    Per-pass verbalization state: a generic node-substitution map, plus the
    deferred-constraint frame stack used when verbalizing an instantiated variable.

    :attr:`binding_overrides` is a generic mechanism (read by the fold engine for any node id),
    with two independent consumers today: :class:`~…grammar.instantiated.assembler.InstantiatedAssembler`
    registers a field's own rendered reference so a later deferred constraint on that field reuses
    it instead of re-verbalizing (e.g. ``inference(Drawer)(container=fc.parent)`` rendered as *"a
    Drawer where the container of the Drawer is …"*); :class:`~…grammar.causal.assembler.CausalAssembler`
    registers a classified case's variable as a definite instance reference (*"the Animal"*) so a
    why-answer's conclusion and conditions read with the concrete case. :attr:`constraint_frames`
    is instantiated-variable-specific and unrelated to :attr:`binding_overrides`; it stays here as
    the other piece of per-pass state a grammar assembler may need to mutate mid-``realize``.
    """

    constraint_frames: List[List[SymbolicExpression]] = field(default_factory=list)
    """
    Stack of deferred-expression frames.

    Each frame belongs to one nesting level of InstantiatedVariable verbalization.
    """

    binding_overrides: Dict[uuid.UUID, VerbalizationFragment] = field(
        default_factory=dict
    )
    """
    Maps a node's ``_id_`` → a :class:`VerbalizationFragment` that substitutes for it on
    subsequent encounters, so a pre-rendered fragment is reused instead of being verbalized
    again.
    """

    def push_constraint_frame(self) -> None:
        """
        Open a new constraint frame for the current InstantiatedVariable.
        """
        self.constraint_frames.append([])

    def pop_constraint_frame(self) -> List[SymbolicExpression]:
        """
        Close the current frame and return its deferred expressions (empty when none
        open).

        :return: Deferred expressions from the closed frame, in deferral order.
        """
        return self.constraint_frames.pop() if self.constraint_frames else []

    def defer_constraint(self, expression: SymbolicExpression) -> None:
        """
        Defer *expression* into the top constraint frame; a no-op when no frame is open.

        :param expression: EQL expression to defer.
        """
        if self.constraint_frames:
            self.constraint_frames[-1].append(expression)
