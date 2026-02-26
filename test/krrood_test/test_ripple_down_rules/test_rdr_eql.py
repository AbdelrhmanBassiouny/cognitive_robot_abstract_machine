import os
from dataclasses import dataclass
from typing import ClassVar, Iterable

import pytest
from typing_extensions import T, Generic

from krrood.entity_query_language.factories import match_variable
from krrood.ripple_down_rules import CaseQuery, SingleClassRDR
from krrood.ripple_down_rules.datastructures.case import Case
from krrood.ripple_down_rules.experts import Human
from krrood_test.test_ripple_down_rules.datasets import load_zoo_dataset, Species, load_zoo_cases


@dataclass
class TestDataDirectories:
    test_results_dir: ClassVar[str] = os.path.join(os.path.dirname(__file__), "test_results")
    expert_answers_dir: ClassVar[str] = os.path.join(
        os.path.dirname(__file__), "test_expert_answers"
    )
    generated_rdrs_dir: ClassVar[str] = os.path.join(
        os.path.dirname(__file__), "test_generated_rdrs"
    )


@pytest.fixture
def ensure_folders_exist():
    for test_dir in [
        TestDataDirectories.test_results_dir,
        TestDataDirectories.expert_answers_dir,
        TestDataDirectories.generated_rdrs_dir,
    ]:
        if not os.path.exists(test_dir):
            os.makedirs(test_dir)


@dataclass
class Target(Generic[T]):
    value: T


@dataclass
class Targets(Generic[T]):
    value: Iterable[T]


@pytest.fixture
def zoo_dataset_case_queries():
    # fetch dataset
    cache_file = os.path.join(TestDataDirectories.test_results_dir, "zoo_dataset.pkl")
    all_cases, targets = load_zoo_dataset(cache_file=cache_file)

    new_case_queries = match_variable(Case, all_cases)(species=Targets(targets))
    old_case_queries = [
        CaseQuery(
            case,
            "species",
            Species,
            True,
            _target=target)
        for case, target in zip(all_cases, targets)]
    return [
        CaseQuery(
            case,
            "species",
            Species,
            True,
            _target=target,
            case_factory=load_zoo_cases,
            case_factory_idx=i,
        )
        for i, (case, target) in enumerate(zip(all_cases, targets))
    ]


def test_classify_scrdr(zoo_dataset_case_queries):
    case_queries = zoo_dataset_case_queries
    use_loaded_answers = True
    save_answers = False
    filename = os.path.join(
        TestDataDirectories.expert_answers_dir, "scrdr_expert_answers_classify"
    )
    expert = Human(use_loaded_answers=use_loaded_answers)
    if use_loaded_answers:
        expert.load_answers(filename)

    scrdr = SingleClassRDR()
    cat = scrdr.fit_case(
        case_queries[0], expert=expert, scenario=test_classify_scrdr
    )
    assert cat == case_queries[0].target_value

    if save_answers:
        cwd = os.path.dirname(__file__)
        file = os.path.join(cwd, filename)
        expert.save_answers(file)
