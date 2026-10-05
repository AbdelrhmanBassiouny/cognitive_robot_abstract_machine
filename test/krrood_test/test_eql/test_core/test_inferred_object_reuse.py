"""
Tests for the identity of objects inferred by rules.

``inference(H)(**kwargs)`` denotes the function term ``f_H(t1, ..., tn)``: for a given
class ``H`` and a given binding of its keyword arguments there is at most one ``H``
object. Re-evaluating a rule, or evaluating another rule built from a separate
``inference(H)(...)`` call with the same binding, must return that same object instead
of constructing a duplicate.
"""

from __future__ import annotations

import gc
import weakref

from krrood.entity_query_language.factories import (
    add,
    alternative,
    an,
    deduced_variable,
    entity,
    inference,
    refinement,
    variable,
)
from krrood.entity_query_language.core.inferred_object_registry import (
    InferredObjectRegistry,
)
from krrood.patterns.role import Role

from ...dataset.example_classes import Person
from ...dataset.eql_rule_tree_doc_example import (
    ExampleConnection,
    ExampleFixedView,
    ExampleView,
)
from ...dataset.inferred_object_reuse_classes import (
    InferredFact,
    InferredFactRole,
    InferredRoleTaker,
    LeveledInferredFactRole,
    RefinedInferredFact,
)
from ...dataset.semantic_world_like_classes import (
    Body,
    Container,
    Door,
    Drawer,
    FixedConnection,
    Handle,
    RevoluteConnection,
    View,
    Wardrobe,
)

# %% idempotence across evaluations


def test_rule_evaluation_reuses_the_same_object_on_reevaluation():
    """
    Re-evaluating the same inference rule returns the same object for the same binding.
    """
    rule = entity(inference(InferredFact)(evidence=1))

    (first,) = rule.evaluate()
    (second,) = rule.evaluate()

    assert first is second


def test_rule_evaluation_answer_count_is_unchanged_on_reevaluation():
    """
    Re-evaluating the same inference rule over several bindings yields the same number
    of answers both times.
    """
    evidence = variable(int, domain=[1, 2, 3])
    rule = entity(inference(InferredFact)(evidence=evidence))

    first = rule.tolist()
    second = rule.tolist()

    assert len(first) == len(second) == 3


# %% sharing across separately built rules and differing bindings


def test_two_separately_built_rules_with_the_same_binding_share_the_object():
    """
    Two independently constructed ``inference`` rules for the same class and the same
    binding denote the same object.
    """
    rule_a = entity(inference(InferredFact)(evidence=7))
    rule_b = entity(inference(InferredFact)(evidence=7))

    (object_a,) = rule_a.evaluate()
    (object_b,) = rule_b.evaluate()

    assert object_a is object_b


def test_different_bindings_infer_different_objects():
    """
    Two ``inference`` rules for the same class but different bindings denote different
    objects.
    """
    rule_a = entity(inference(InferredFact)(evidence=1))
    rule_b = entity(inference(InferredFact)(evidence=2))

    (object_a,) = rule_a.evaluate()
    (object_b,) = rule_b.evaluate()

    assert object_a is not object_b


def test_a_subclass_with_the_same_binding_infers_a_different_object_than_its_base_class():
    """
    A subclass of the inferred class, given the same argument binding as the base class,
    denotes a different object than the base class.
    """
    base_rule = entity(inference(InferredFact)(evidence=1))
    subclass_rule = entity(inference(RefinedInferredFact)(evidence=1))

    (base_object,) = base_rule.evaluate()
    (subclass_object,) = subclass_rule.evaluate()

    assert base_object is not subclass_object


# %% roles


def test_role_evaluation_reuses_the_same_role_on_reevaluation():
    """
    Re-evaluating a rule that infers a role for the same taker returns the same role
    object.
    """
    taker = InferredRoleTaker(name="Alice")
    rule = entity(inference(InferredFactRole)(role_taker=taker))

    (first,) = rule.evaluate()
    (second,) = rule.evaluate()

    assert first is second


def test_roles_for_has_exactly_one_role_after_several_evaluations():
    """
    ``Role.roles_for`` reports exactly one role for a taker even after the rule
    inferring it has been evaluated several times.
    """
    taker = InferredRoleTaker(name="Alice")
    rule = entity(inference(InferredFactRole)(role_taker=taker))

    # Every evaluation's result is kept alive, so a count above one could not be
    # explained away by an earlier, already garbage-collected role.
    evaluations = [rule.tolist() for _ in range(3)]

    assert len(Role.roles_for(taker, InferredFactRole)) == 1
    assert len(evaluations) == 3


def test_role_with_a_different_literal_field_value_infers_a_different_role_for_the_same_taker():
    """
    A role with an extra literal field infers a different role for the same taker when
    that field's value differs.
    """
    taker = InferredRoleTaker(name="Alice")
    junior_rule = entity(
        inference(LeveledInferredFactRole)(role_taker=taker, level="junior")
    )
    senior_rule = entity(
        inference(LeveledInferredFactRole)(role_taker=taker, level="senior")
    )

    (junior_role,) = junior_rule.evaluate()
    (senior_role,) = senior_rule.evaluate()

    assert junior_role is not senior_role


# %% argument comparison semantics


def test_two_rules_sharing_a_literal_argument_value_share_the_object():
    """
    Two separately built rules that both infer a :class:`Person` for ``name="Alice"``
    denote the same object.
    """
    rule_a = entity(inference(Person)(name="Alice"))
    rule_b = entity(inference(Person)(name="Alice"))

    (person_a,) = rule_a.evaluate()
    (person_b,) = rule_b.evaluate()

    assert person_a is person_b


def test_literal_arguments_of_different_types_infer_different_objects():
    """
    Literal arguments that are equal across types (``True`` and ``1``) infer different
    objects, because the literal is compared by value *and* type.
    """
    boolean_rule = entity(inference(InferredFact)(evidence=True))
    integer_rule = entity(inference(InferredFact)(evidence=1))

    (boolean_object,) = boolean_rule.evaluate()
    (integer_object,) = integer_rule.evaluate()

    assert boolean_object is not integer_object


def test_equal_but_distinct_object_arguments_infer_different_objects():
    """
    Two distinct :class:`Person` arguments that compare equal by value still infer two
    different objects, because a non-literal argument is compared by identity.
    """
    person_a = Person(name="Alice")
    person_b = Person(name="Alice")
    rule_a = entity(inference(InferredFact)(evidence=person_a))
    rule_b = entity(inference(InferredFact)(evidence=person_b))

    (object_a,) = rule_a.evaluate()
    (object_b,) = rule_b.evaluate()

    assert object_a is not object_b


def test_the_same_unhashable_list_argument_shares_the_object():
    """
    The same (unhashable) list object, passed as an argument to two separately built
    rules, is identified by identity, so both rules denote the same object.
    """
    shared_evidence = [1, 2]
    rule_a = entity(inference(InferredFact)(evidence=shared_evidence))
    rule_b = entity(inference(InferredFact)(evidence=shared_evidence))

    (object_a,) = rule_a.evaluate()
    (object_b,) = rule_b.evaluate()

    assert object_a is object_b


def test_equal_but_distinct_list_arguments_infer_different_objects():
    """
    Two distinct, but equal, list arguments infer two different objects, because an
    unhashable argument is compared by identity rather than by value.
    """
    rule_a = entity(inference(InferredFact)(evidence=[1, 2]))
    rule_b = entity(inference(InferredFact)(evidence=[1, 2]))

    (object_a,) = rule_a.evaluate()
    (object_b,) = rule_b.evaluate()

    assert object_a is not object_b


# %% registry


def test_registry_reuses_the_object_for_a_repeated_lookup_with_the_same_key():
    """
    Looking an inferred object up twice for the same class and arguments returns the
    same object.
    """
    first = InferredObjectRegistry().object_for(InferredFact, {"evidence": "same-key"})
    second = InferredObjectRegistry().object_for(InferredFact, {"evidence": "same-key"})

    assert first is second


def test_registry_clear_forces_a_new_object_for_the_same_key():
    """
    ``InferredObjectRegistry.clear()`` forgets every inferred object, so a later lookup
    for a previously-seen class and arguments constructs a new object.
    """
    first = InferredObjectRegistry().object_for(InferredFact, {"evidence": "clear-me"})

    InferredObjectRegistry.clear()
    second = InferredObjectRegistry().object_for(InferredFact, {"evidence": "clear-me"})

    assert first is not second


def test_registry_does_not_keep_an_inferred_object_alive():
    """
    Once the caller drops every reference to an inferred object, the registry's own hold
    on it must not keep it alive.
    """

    def build_and_drop_the_inferred_object() -> weakref.ReferenceType:
        inferred_object = InferredObjectRegistry().object_for(
            InferredFact, {"evidence": "weakly-held"}
        )
        return weakref.ref(inferred_object)

    reference = build_and_drop_the_inferred_object()
    gc.collect()

    assert reference() is None


# %% rule trees with a refinement and an alternative


def test_refinement_rule_tree_evaluation_is_idempotent():
    """
    Re-evaluating a rule tree with a refinement branch yields the same conclusion
    objects both times.
    """
    connections = [ExampleConnection(1, "c1"), ExampleConnection(2, "c2")]
    connection = variable(ExampleConnection, domain=connections)
    view = deduced_variable(ExampleView)
    query = entity(view).where(connection.name.startswith("c"))

    with query:
        add(view, inference(ExampleView)(connection=connection))
        with refinement(connection.type_code == 1):
            add(view, inference(ExampleFixedView)(connection=connection))

    first = query.tolist()
    second = query.tolist()

    assert len(first) == len(second) == 2
    assert all(one is other for one, other in zip(first, second))


def test_refinement_conclusion_still_overrides_the_default_class_with_reuse_enabled():
    """
    A refinement's conclusion still replaces the default conclusion's class once
    inferred objects are reused.
    """
    connections = [ExampleConnection(1, "c1")]
    connection = variable(ExampleConnection, domain=connections)
    view = deduced_variable(ExampleView)
    query = entity(view).where(connection.name.startswith("c"))

    with query:
        add(view, inference(ExampleView)(connection=connection))
        with refinement(connection.type_code == 1):
            add(view, inference(ExampleFixedView)(connection=connection))

    (result,) = query.evaluate()

    assert type(result) is ExampleFixedView


def test_alternative_rule_tree_evaluation_is_idempotent(doors_and_drawers_world):
    """
    Re-evaluating a rule tree with an alternative branch yields the same conclusion
    objects both times.
    """
    world = doors_and_drawers_world
    body = variable(Body, domain=world.bodies)
    container = variable(Container, domain=world.bodies)
    handle = variable(Handle, domain=world.bodies)
    fixed_connection = variable(FixedConnection, domain=world.connections)
    revolute_connection = variable(RevoluteConnection, domain=world.connections)
    views = deduced_variable(View)
    query = an(
        entity(views).where(
            body == fixed_connection.parent,
            handle == fixed_connection.child,
        )
    )

    with query:
        add(views, inference(Drawer)(handle=handle, container=body))
        with refinement(body.size > 1):
            add(views, inference(Door)(handle=handle, body=body))
            with alternative(
                body == revolute_connection.child,
                container == revolute_connection.parent,
            ):
                add(
                    views,
                    inference(Wardrobe)(handle=handle, body=body, container=container),
                )

    first = list(query.evaluate())
    second = list(query.evaluate())

    assert len(first) == len(second) == 3
    assert all(one is other for one, other in zip(first, second))


# %% opting out of reuse


def test_reuse_can_be_disabled_to_restore_a_fresh_object_per_evaluation():
    """
    Passing ``reuse_inferred_objects=False`` restores the old behaviour: each evaluation
    constructs its own, distinct object for the same binding.
    """
    rule = entity(inference(InferredFact, reuse_inferred_objects=False)(evidence=1))

    (first,) = rule.evaluate()
    (second,) = rule.evaluate()

    assert first is not second
