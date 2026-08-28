import pytest
from random_events.interval import closed
from random_events.product_algebra import SimpleEvent

from krrood.entity_query_language.backends import ProbabilisticBackend
from krrood.entity_query_language.factories import and_, probability_of, variable
from krrood.parametrization.exceptions import JointQueryAcrossClassesNotSupported
from krrood.parametrization.model_registries import DictRegistry

from ._fixtures import Coin, OtherClass, build_three_independent_variables_circuit


def test_probability_matches_direct_computation():
    circuit, var_a, var_b, var_c = build_three_independent_variables_circuit()
    x = variable(Coin)

    backend = ProbabilisticBackend(model_registry=DictRegistry({Coin: circuit}))
    result = probability_of(x.a < 0.5).first(backend=backend)

    expected = circuit.probability(
        SimpleEvent.from_data({var_a: closed(0, 0.5)}).as_composite_set()
    )
    assert result == pytest.approx(expected)
    # a is independent of b/c and uniform on [0, 1], so P(a < 0.5) == 0.5 regardless
    assert result == pytest.approx(0.5)


def test_probability_of_conjunction():
    circuit, var_a, var_b, var_c = build_three_independent_variables_circuit()
    x = variable(Coin)

    backend = ProbabilisticBackend(model_registry=DictRegistry({Coin: circuit}))
    result = probability_of(and_(x.a < 0.5, x.b < 1)).first(backend=backend)

    # independent uniforms: P(a < 0.5) * P(b < 1) == 0.5 * 0.5
    assert result == pytest.approx(0.25)


def test_probability_rejects_cross_class():
    x = variable(Coin)
    y = variable(OtherClass)

    with pytest.raises(JointQueryAcrossClassesNotSupported):
        probability_of(and_(x.a < 0.5, y.d < 0.5)).first(
            backend=ProbabilisticBackend(model_registry=DictRegistry({}))
        )
