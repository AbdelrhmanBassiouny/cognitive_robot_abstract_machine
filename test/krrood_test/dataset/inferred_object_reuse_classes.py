"""
Mimic classes for exercising the rule-inference object reuse pattern: constructing a
class with the same keyword-argument binding through ``inference`` must denote one
object, not a fresh object for every evaluation.
"""

from __future__ import annotations

from dataclasses import dataclass

from typing_extensions import Any

from krrood.patterns.role import Role

# %% a plain class a rule infers from one piece of evidence


@dataclass(eq=False)
class InferredFact:
    """
    A fact a rule infers from one piece of evidence, used to test that an inference
    denotes one object per argument binding rather than a fresh object for every
    evaluation.
    """

    evidence: Any
    """
    The evidence value the fact is inferred from.
    """


@dataclass(eq=False)
class RefinedInferredFact(InferredFact):
    """
    A subclass of :class:`InferredFact` with no fields of its own, used to test that an
    inference's identity depends on its exact class as well as its argument binding, so
    a subclass sharing the base class's binding is inferred as a separate object.
    """


# %% a role taker and the roles a rule can infer for it


@dataclass(eq=False)
class InferredRoleTaker:
    """
    A role taker a rule can infer a role for, used to test that inferring a role denotes
    one role per taker and argument binding.
    """

    name: str
    """
    The name identifying the role taker.
    """


@dataclass(eq=False)
class InferredFactRole(Role[InferredRoleTaker]):
    """
    A role a rule infers for an :class:`InferredRoleTaker`, with no fields of its own
    beyond the inherited role taker.
    """


@dataclass(eq=False)
class LeveledInferredFactRole(Role[InferredRoleTaker]):
    """
    A role like :class:`InferredFactRole` but with an extra literal field, used to test
    that two different literal values for that field are inferred as two different roles
    for the same taker.
    """

    level: str = ""
    """
    The literal value distinguishing which role is inferred for the same taker.
    """
