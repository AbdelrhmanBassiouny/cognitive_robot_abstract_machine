# krrood-light-core — standing rules

- Core is everything a plain `pip install krrood` needs: patterns, exceptions, JSON serializer, class diagrams, symbol graph, EQL. Its dependencies stay pure-Python or have Windows wheels (typing_extensions, rustworkx and its numpy, ordered_set, sortedcontainers). Anything else is `all`.
- Only two levels: core and `all` (plus the existing `dev` and `visualization`). No finer extras unless the user asks.
- A library from an extra is imported in core only inside the functions that need it (or under TYPE_CHECKING); everywhere else imports stay at the top.
- Each decoupling item removes its modules from the core-boundary guard's offender lists (runtime test and import-linter); nothing is ever added to them.
- Never reimplement what the heavy library does to keep a feature in core; move the feature to `all` instead, unless the check is a plain stdlib type test (number_like_field).
- Core's subpackages, its dependencies and both offender lists are declared once, in krrood/pyproject.toml (the import-linter contract and [tool.krrood.core-boundary]); no other file restates them.
- `krrood check` (OptionalImportChecker) reports a core module importing a library from an extra at module level; extras come from krrood/pyproject.toml, never restated.
