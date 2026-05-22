"""
Exceptions for the EQL subsumption module.
"""


class CNFExplosionError(RuntimeError):
    """
    Raised when CNF conversion exceeds the configured atom budget.

    This can happen when distributing OR over deeply nested AND expressions,
    causing an exponential blowup in the number of clauses. The subsumption
    result defaults to False (sound: never a false positive).

    Future: mitigated by quantifier lifting or a smarter distribution strategy.
    """

    def __init__(self, budget: int):
        super().__init__(
            f"CNF conversion exceeded the atom budget of {budget}. "
            "Subsumption result defaults to False (sound but incomplete)."
        )
        self.budget = budget
