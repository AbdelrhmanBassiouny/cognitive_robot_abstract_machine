"""
Comparing Gaussian mixtures and joint probability trees on a small dataset.

Each test pins one property the benchmark's numbers have to have, on iris, the smallest
dataset, so that it runs quickly.
"""

import math

import pytest

from experiments.probabilistic_circuit_experiments.gaussian_mixture_benchmark import (
    Dataset,
    Method,
    Setting,
    benchmark,
)


@pytest.fixture(scope="module")
def iris_table():
    return benchmark(
        Dataset.IRIS,
        [
            Setting(Method.GAUSSIAN_MIXTURE, 1),
            Setting(Method.GAUSSIAN_MIXTURE, 3),
            Setting(Method.JOINT_PROBABILITY_TREE, 0.1),
        ],
    )


def test_iris_is_loaded_with_its_species_as_the_symbolic_column():
    data, symbolic = Dataset.IRIS.load()

    assert symbolic == "label"
    assert data[symbolic].nunique() == 3
    assert data.drop(columns=symbolic).mean().abs().max() < 1e-5


def test_every_row_of_the_data_it_was_fitted_on_is_possible(iris_table):
    for row in iris_table.experiments:
        assert row.impossible_rows == 0
        assert math.isfinite(row.average_log_likelihood)


def test_a_single_component_predicts_the_species_by_its_frequency(iris_table):
    """
    One component makes the species independent of the measurements, so the best it
    can do is the frequency of each species, a third.
    """
    [single_component] = [
        row
        for row in iris_table.experiments
        if row.method is Method.GAUSSIAN_MIXTURE and row.setting == "1 component"
    ]

    assert single_component.symbolic_given_rest == pytest.approx(math.log(1 / 3))


def test_components_that_see_the_species_predict_it_well(iris_table):
    [three_components] = [
        row
        for row in iris_table.experiments
        if row.method is Method.GAUSSIAN_MIXTURE and row.setting == "3 components"
    ]

    assert three_components.symbolic_given_rest > math.log(0.9)


def test_the_table_renders_one_row_per_setting(iris_table):
    assert len(iris_table.experiments) == 3
    assert iris_table.as_json_rows()[0]["dataset"] == "IRIS"
