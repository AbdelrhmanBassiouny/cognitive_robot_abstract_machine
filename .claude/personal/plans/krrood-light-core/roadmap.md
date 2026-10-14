# krrood-light-core — standing rules

- Core is everything a plain `pip install krrood` needs: patterns, exceptions, JSON serializer, class diagrams, symbol graph, EQL. Its dependencies stay pure-Python or have Windows wheels (typing_extensions, rustworkx and its numpy, ordered_set, sortedcontainers). Anything else is `all`.
- Only two levels: core and `all` (plus the existing `dev` and `visualization`). No finer extras unless the user asks.
- A library from `all` is imported inside the method that needs it, after `check_dependencies()` raises a custom exception naming the extra. This is the AGENTS.md exception the user approved (option 1); everywhere else imports stay at the top.
- Each decoupling item removes its modules from the core-boundary guard's offender lists (runtime test and import-linter); nothing is ever added to them.
- Never reimplement what the heavy library does to keep a feature in core; move the feature to `all` instead, unless the check is a plain stdlib type test (number_like_field).
