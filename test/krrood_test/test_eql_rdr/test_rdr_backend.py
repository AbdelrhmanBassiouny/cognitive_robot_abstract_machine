"""
Tests for :class:`~krrood.entity_query_language.rdr.backend.RDRBackend`: the registry of
one RDR per underspecified attribute, and the two ways it hands back what those models
conclude.

The adapter that reads an underspecified query is covered by
``test_underspecified_match.py``, and the engine itself by ``test_single_class_rdr.py``;
what is left here is the backend's own behaviour.
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from typing_extensions import Dict, List

from krrood.entity_query_language.factories import an, entity, variable
from krrood.entity_query_language.rdr.answer_vocabulary import AnswerName
from krrood.entity_query_language.rdr.backend import ModelKey, RDRBackend
from krrood.entity_query_language.rdr.exceptions import (
    ExpertRequired,
    QueryIsNotAMatch,
)
from krrood.entity_query_language.rdr.expert import Expert
from krrood.entity_query_language.rdr.interface import (
    AnswerRequest,
    CaseContext,
    FunctionInterface,
)
from krrood.entity_query_language.rdr.serialization import (
    ModelSaver,
    load_rdr,
    save_rdr,
)
from krrood.entity_query_language.rdr.single_class import EQLSingleClassRDR
from krrood.entity_query_language.rdr.underspecified import UnderspecifiedMatch

from .animal import Animal, Species, make_bird, make_mammal
from .expert_doubles import labelling_expert, maximally_specific_expert

# %% the dataset these tests fit over


def species_of(animal: Animal) -> Species:
    """
    The ground truth every fit below is given.

    :param animal: The animal to label.
    :return:``Species.mammal`` for a milk-bearing animal, ``Species.bird`` otherwise.
    """
    return Species.mammal if animal.milk else Species.bird


@pytest.fixture
def animals() -> List[Animal]:
    """
    :return: Six unclassified animals, three milk-bearing and three feathered, fresh for
        each test so a filling test cannot leak its conclusions into the next one.
    """
    return [make_mammal(name) for name in ("cow", "dog", "bear")] + [
        make_bird(name) for name in ("crow", "duck", "hawk")
    ]


@pytest.fixture
def species_by_name(animals: List[Animal]) -> Dict[str, Species]:
    """
    :return: The ground truth in the shape an expert that labels cases wants it.
    """
    return {animal.name: species_of(animal) for animal in animals}


def milk_conditions(
    context: CaseContext, requests: List[AnswerRequest]
) -> Dict[AnswerName, object]:
    """
    Answer with a condition on ``milk`` alone, which separates the two groups without
    naming whichever attribute the RDR is predicting.

    :param context: The case being fitted.
    :param requests: The answers asked for; ignored, conditions are always supplied.
    :return: The conditions answer.
    """
    return {
        AnswerName.CONDITIONS: context.case_variable.milk == context.case_instance.milk
    }


def milk_expert() -> Expert:
    """
    :return: An expert whose every rule matches on ``milk``.
    """
    return Expert(interface=FunctionInterface(answer_function=milk_conditions))


@dataclass
class CountingModelSaver(ModelSaver):
    """
    A saver that records how often it was asked to persist a model.
    """

    saves: int = 0
    """
    How many times :meth:`save` has been called.
    """

    def save(self, rdr: EQLSingleClassRDR) -> None:
        self.saves += 1


# %% the registry key


def test_a_key_names_the_attributes_owner_type_and_name():
    target = UnderspecifiedMatch(an(Animal)(species=...)).single_target()

    assert ModelKey.from_attribute(target.attribute) == ModelKey(Animal, "species")


def test_every_query_for_one_attribute_is_served_by_one_model(
    animals: List[Animal],
):
    backend = RDRBackend(expert=maximally_specific_expert())

    backend.fit(an(Animal)(species=...).from_(animals), species_of)
    backend.fit(an(Animal)(milk=True, species=...).from_(animals), species_of)

    assert list(backend.models) == [ModelKey(Animal, "species")]


def test_a_second_attribute_is_served_by_a_model_of_its_own(animals: List[Animal]):
    backend = RDRBackend(expert=milk_expert())

    backend.fit(an(Animal)(species=...).from_(animals), species_of)
    backend.fit(an(Animal)(legs=...).from_(animals), lambda animal: animal.legs)

    assert set(backend.models) == {
        ModelKey(Animal, "species"),
        ModelKey(Animal, "legs"),
    }


# %% fitting


def test_ground_truth_labels_every_case_the_query_keeps(animals: List[Animal]):
    backend = RDRBackend(expert=maximally_specific_expert())

    backend.fit(an(Animal)(species=...).from_(animals), species_of)

    model = backend.models[ModelKey(Animal, "species")]
    assert {animal.name: model.classify(animal) for animal in animals} == {
        animal.name: species_of(animal) for animal in animals
    }


def test_fitting_returns_the_backend_for_chaining(animals: List[Animal]):
    backend = RDRBackend(expert=maximally_specific_expert())

    assert backend.fit(an(Animal)(species=...).from_(animals), species_of) is backend


def test_without_ground_truth_the_expert_labels_each_case(
    animals: List[Animal], species_by_name: Dict[str, Species]
):
    backend = RDRBackend(expert=labelling_expert(species_by_name))

    backend.fit(an(Animal)(species=...).from_(animals))

    model = backend.models[ModelKey(Animal, "species")]
    assert {
        animal.name: model.classify(animal) for animal in animals
    } == species_by_name


def test_a_fit_persists_the_model_once_rather_than_once_per_case(
    animals: List[Animal],
):
    saver = CountingModelSaver()
    backend = RDRBackend(
        expert=maximally_specific_expert(),
        models={
            ModelKey(Animal, "species"): EQLSingleClassRDR(
                Animal, "species", model_saver=saver
            )
        },
    )

    backend.fit(an(Animal)(species=...).from_(animals), species_of)

    assert saver.saves == 1


def test_a_fit_with_neither_ground_truth_nor_an_expert_raises(animals: List[Animal]):
    backend = RDRBackend()

    with pytest.raises(ExpertRequired):
        backend.fit(an(Animal)(species=...).from_(animals))


# %% inference is lazy, filling is eager


def test_inference_does_no_work_until_it_is_iterated(animals: List[Animal]):
    backend = RDRBackend()

    bindings = backend.infer(an(Animal)(species=...).from_(animals))

    with pytest.raises(ExpertRequired):
        next(iter(bindings))


def test_filling_has_done_its_work_by_the_time_it_returns(animals: List[Animal]):
    backend = RDRBackend()

    with pytest.raises(ExpertRequired):
        backend.fill(an(Animal)(species=...).from_(animals))


# %% inference


def test_inference_binds_each_case_and_its_conclusion_to_the_query(
    animals: List[Animal],
):
    backend = RDRBackend(expert=maximally_specific_expert())
    query = an(Animal)(species=...).from_(animals)
    backend.fit(query, species_of)

    bindings = list(backend.infer(query))

    assert [bound[query._variable_] for bound in bindings] == animals
    assert [bound[query._variable_.species] for bound in bindings] == [
        species_of(animal) for animal in animals
    ]


def test_inference_leaves_the_instances_unclassified(animals: List[Animal]):
    backend = RDRBackend(expert=maximally_specific_expert())
    query = an(Animal)(species=...).from_(animals)
    backend.fit(query, species_of)

    list(backend.infer(query))

    assert [animal.species for animal in animals] == [None] * len(animals)


def test_inference_reaches_only_the_cases_the_concrete_constraints_keep(
    animals: List[Animal],
):
    backend = RDRBackend(expert=maximally_specific_expert())
    query = an(Animal)(milk=True, species=...).from_(animals)
    backend.fit(query, species_of)

    bindings = list(backend.infer(query))

    assert [bound[query._variable_].name for bound in bindings] == [
        animal.name for animal in animals if animal.milk
    ]


def test_inference_fits_an_attribute_it_has_no_model_for(
    animals: List[Animal], species_by_name: Dict[str, Species]
):
    backend = RDRBackend(expert=labelling_expert(species_by_name))
    query = an(Animal)(species=...).from_(animals)

    bindings = list(backend.infer(query))

    assert list(backend.models) == [ModelKey(Animal, "species")]
    assert {
        bound[query._variable_].name: bound[query._variable_.species]
        for bound in bindings
    } == species_by_name


# %% filling


def test_filling_sets_the_inferred_attribute_on_every_matching_instance(
    animals: List[Animal],
):
    backend = RDRBackend(expert=maximally_specific_expert())
    query = an(Animal)(species=...).from_(animals)
    backend.fit(query, species_of)

    backend.fill(query)

    assert {animal.name: animal.species for animal in animals} == {
        animal.name: species_of(animal) for animal in animals
    }


def test_filling_returns_the_instances_it_filled(animals: List[Animal]):
    backend = RDRBackend(expert=maximally_specific_expert())
    query = an(Animal)(milk=True, species=...).from_(animals)
    backend.fit(query, species_of)

    assert backend.fill(query) == [animal for animal in animals if animal.milk]


# %% a model that has been through a file


def test_a_reloaded_model_concludes_what_the_original_did(
    animals: List[Animal], tmp_path
):
    backend = RDRBackend(expert=maximally_specific_expert())
    query = an(Animal)(species=...).from_(animals)
    backend.fit(query, species_of)
    destination = tmp_path / "animal_species_rdr.py"
    save_rdr(backend.models[ModelKey(Animal, "species")], str(destination))

    reloaded = RDRBackend(
        models={ModelKey(Animal, "species"): load_rdr(str(destination))}
    )

    assert [bound[query._variable_.species] for bound in reloaded.infer(query)] == [
        bound[query._variable_.species] for bound in backend.infer(query)
    ]


# %% answering a query through the backend


def test_a_query_evaluated_through_the_backend_yields_its_completed_instances(
    animals: List[Animal],
):
    backend = RDRBackend(expert=maximally_specific_expert())
    query = an(Animal)(milk=True, species=...).from_(animals)
    backend.fit(query, species_of)

    completed = list(query.evaluate(backend=backend))

    assert completed == [animal for animal in animals if animal.milk]
    assert {animal.name: animal.species for animal in completed} == {
        animal.name: species_of(animal) for animal in animals if animal.milk
    }


def test_evaluating_a_query_completes_the_instances_before_it_hands_any_back(
    animals: List[Animal],
):
    backend = RDRBackend(expert=maximally_specific_expert())
    query = an(Animal)(species=...).from_(animals)
    backend.fit(query, species_of)

    query.evaluate(backend=backend)

    assert [animal.species for animal in animals] == [
        species_of(animal) for animal in animals
    ]


def test_a_query_with_no_attribute_to_complete_is_refused(animals: List[Animal]):
    backend = RDRBackend(expert=maximally_specific_expert())

    with pytest.raises(QueryIsNotAMatch):
        entity(variable(Animal, animals)).evaluate(backend=backend)
