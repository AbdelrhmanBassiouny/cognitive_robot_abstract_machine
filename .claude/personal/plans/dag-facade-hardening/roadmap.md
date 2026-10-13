# dag-facade-hardening — standing rules

- TDD throughout (AGENTS.md): each fix begins with a failing shared-node regression test in the #90/#92 shape (a node shared across two independent queries, asserting the second query's own evaluation is correct). krrood-internal mimics only — no cross-package imports.
- Run with the project interpreter via pytest: `test_eql`, `test_ormatic`, `test_class_diagrams`, `test_ripple_down_rules`; expect the #89/#90/#92 baselines to stay green with new tests added.
- `black` + `docformatter` (`scripts/format_docstrings.py`) on touched files; RST field docstrings; absolute/top-level imports; no `getattr`; guard clauses; SOLID.
- Commits authored as the human identity, no assistant trailers; "Made with the help of Claude." note permitted.
