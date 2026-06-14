"""
Doctest harness for the verbalization grammar rules and forms.

Every dispatch rule / form docstring carries a concrete ``>>> verbalize_expression(...)`` example
next to its template form, so the documented output is *executed* and cannot silently drift from
what the grammar actually produces.

The examples are kept to a single readable line by injecting a shared namespace — the EQL
factories, ``Not``, ``verbalize_expression`` and the example-domain classes — so a docstring need
only write ``verbalize_expression(variable(Task, []).completed)`` rather than re-import everything.
The example domain is the same module Sphinx AutoAPI documents, so the rendered examples also
hyperlink to real API pages.
"""

from __future__ import annotations

import doctest

import pytest

from krrood.entity_query_language import factories
from krrood.entity_query_language.operators.core_logical_operators import Not
from krrood.entity_query_language.operators.logical_quantifiers import Exists, ForAll
from krrood.entity_query_language.verbalization import example_domain
from krrood.entity_query_language.verbalization.grammar import english, restriction
from krrood.entity_query_language.verbalization.grammar.assembly import chains
from krrood.entity_query_language.verbalization.pipeline import verbalize_expression

# The grammar modules whose rule/form docstrings carry executable examples.
_MODULES = [english, restriction, chains]

# Names every rule docstring may use, so each example stays a single line.
_FACTORY_NAMES = [
    "variable",
    "an",
    "the",
    "entity",
    "set_of",
    "and_",
    "or_",
    "max",
    "min",
    "sum",
    "count",
    "contains",
    "in_",
    "for_all",
    "exists",
]
_GLOBS = {name: getattr(factories, name) for name in _FACTORY_NAMES}
_GLOBS.update(
    verbalize_expression=verbalize_expression,
    Not=Not,
    Exists=Exists,
    ForAll=ForAll,
)
# The example-domain classes (defined in that module, not imported into it).
_GLOBS.update(
    {
        name: obj
        for name, obj in vars(example_domain).items()
        if isinstance(obj, type) and obj.__module__ == example_domain.__name__
    }
)


@pytest.mark.parametrize("module", _MODULES, ids=lambda module: module.__name__)
def test_rule_docstring_examples_execute(module):
    """Each rule/form docstring's ``>>>`` example produces exactly the documented output."""
    finder = doctest.DocTestFinder()
    failures: list[str] = []
    for test in finder.find(module, module.__name__, extraglobs=_GLOBS):
        # A fresh runner per docstring — DocTestRunner.run reports cumulative counts.
        runner = doctest.DocTestRunner(optionflags=doctest.FAIL_FAST)
        result = runner.run(test, clear_globs=False)
        if result.failed:
            failures.append(test.name)
    assert not failures, f"doctest failures in {module.__name__}: {failures}"
