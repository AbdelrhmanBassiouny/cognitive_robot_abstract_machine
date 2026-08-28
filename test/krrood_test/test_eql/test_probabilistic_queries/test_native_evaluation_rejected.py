import pytest

from krrood.entity_query_language.backends import EntityQueryLanguageBackend
from krrood.entity_query_language.exceptions import BackendCannotEvaluateProbabilisticQuery
from krrood.entity_query_language.factories import a, distribution_of, probability_of, variable

from ._fixtures import Coin

# Every ProbabilisticQuery subclass shares the same _evaluate_natively_/backend-rejection
# behavior (defined once on the ProbabilisticQuery base), so one parametrized test covers
# both rather than duplicating the same three assertions per construct. average(...) is
# NOT a ProbabilisticQuery -- it has an ordinary native meaning (a per-row average) and
# is only reinterpreted probabilistically by ProbabilisticBackend, so it belongs in
# test_average.py, not here.
CONSTRUCTORS = [
    lambda x, match: distribution_of(match),
    lambda x, match: probability_of(x.a > 0.5),
]


@pytest.mark.parametrize(
    "construct", CONSTRUCTORS, ids=["distribution_of", "probability_of"]
)
def test_native_evaluation_rejected(construct):
    x = variable(Coin)
    match = a(Coin)(a=..., b=..., c=...)
    query = construct(x, match)

    with pytest.raises(BackendCannotEvaluateProbabilisticQuery):
        list(query._evaluate_natively_())

    with pytest.raises(BackendCannotEvaluateProbabilisticQuery):
        query.first()

    with pytest.raises(BackendCannotEvaluateProbabilisticQuery):
        query.first(backend=EntityQueryLanguageBackend())
