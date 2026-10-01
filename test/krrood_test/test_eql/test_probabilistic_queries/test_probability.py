import pytest
from random_events.interval import closed
from random_events.product_algebra import SimpleEvent

from krrood.entity_query_language.backends import (
    EntityQueryLanguageBackend,
    ProbabilisticBackend,
)
from krrood.entity_query_language.factories import (
    and_,
    entity,
    probability_of,
    set_of,
    variable,
)
from krrood.parametrization.exceptions import JointQueryAcrossClassesNotSupported
from krrood.parametrization.model_registries import DictRegistry

from ._fixtures import (
    Coin,
    OtherClass,
    Threshold,
    build_three_independent_variables_circuit,
)

# A small, hand-picked domain (not sampled) so the expected fraction is exact, not an
# approximation -- 4 out of 6 coins have a < 0.5.
_COIN_DOMAIN = [
    Coin(a=0.1, b=1.0, c=1.0),
    Coin(a=0.2, b=1.0, c=1.0),
    Coin(a=0.3, b=0.5, c=1.0),
    Coin(a=0.4, b=0.5, c=1.0),
    Coin(a=0.6, b=1.0, c=1.0),
    Coin(a=0.9, b=1.0, c=1.0),
]


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


def test_probability_evaluates_natively_by_counting_matching_rows():
    """
    Unlike distribution_of, probability_of also has a native evaluation strategy: a
    probability is definitionally the fraction of a domain's rows the condition holds
    for, so it's counted directly -- no ProbabilisticBackend/fitted model needed, just
    an enumerable domain.
    """
    x = variable(Coin, domain=_COIN_DOMAIN)
    result = probability_of(x.a < 0.5).first()  # no backend -> defaults to native

    assert result == pytest.approx(4 / 6)


def test_probability_native_evaluation_explicit_backend_and_conjunction():
    x = variable(Coin, domain=_COIN_DOMAIN)
    result = probability_of(and_(x.a < 0.5, x.b < 1)).first(
        backend=EntityQueryLanguageBackend()
    )

    # 2 of 6 coins have both a < 0.5 and b < 1 (a=0.3,b=0.5 and a=0.4,b=0.5)
    assert result == pytest.approx(2 / 6)


def test_probability_of_true_rejected_natively_too():
    """
    A content-free condition names no class either way -- there's neither a model to
    resolve (ProbabilisticBackend) nor a domain to count over (native).
    """
    with pytest.raises(JointQueryAcrossClassesNotSupported):
        probability_of(True).first()


# %% a probability used as an operand of another query


def test_probability_compared_in_another_query_filters_by_its_value():
    coin = variable(Coin, domain=_COIN_DOMAIN)
    probability = probability_of(coin.a < 0.5)
    thresholds = [Threshold(0.5), Threshold(0.7), Threshold(0.9)]
    threshold = variable(Threshold, domain=thresholds)

    above = entity(threshold).where(threshold.value > probability).tolist()

    expected_probability = probability.first()
    assert above == [t for t in thresholds if t.value > expected_probability]


def test_probability_on_the_left_of_a_comparison_builds_a_condition():
    coin = variable(Coin, domain=_COIN_DOMAIN)
    probability = probability_of(coin.a < 0.5)
    thresholds = [Threshold(0.5), Threshold(0.7)]
    threshold = variable(Threshold, domain=thresholds)

    below = entity(threshold).where(probability > threshold.value).tolist()

    expected_probability = probability.first()
    assert below == [t for t in thresholds if expected_probability > t.value]


# %% a probability within each group


def test_grouped_probability_is_the_probability_within_each_group():
    coin = variable(Coin, domain=_COIN_DOMAIN)
    probability = probability_of(coin.a < 0.5)

    rows = set_of(coin.b, probability).grouped_by(coin.b).tolist()

    def probability_among(b: float) -> float:
        coins_with_b = variable(Coin, domain=[c for c in _COIN_DOMAIN if c.b == b])
        return probability_of(coins_with_b.a < 0.5).first()

    assert {row[coin.b]: row[probability] for row in rows} == {
        b: probability_among(b) for b in {c.b for c in _COIN_DOMAIN}
    }
