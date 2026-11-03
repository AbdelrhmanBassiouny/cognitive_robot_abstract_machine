# krrood-light-core — standing rules

- Core is everything a plain `pip install krrood` needs: patterns, exceptions, JSON serializer, class diagrams, symbol graph, EQL. Its dependencies stay pure-Python or have Windows wheels (typing_extensions, rustworkx and its numpy, ordered_set, sortedcontainers). Anything else is `all`.
- Only two levels: core and `all` (plus the existing `dev` and `visualization`). No finer extras unless the user asks.
- A library from an extra is imported in core only inside the functions that need it (or under TYPE_CHECKING); everywhere else imports stay at the top.
- Each decoupling item removes core-boundary crossings; `krrood check --all-lines` over krrood/src lists the ones left, and the pre-commit hook blocks new ones.
- Never reimplement what the heavy library does to keep a feature in core; move the feature to `all` instead, unless the check is a plain stdlib type test (number_like_field).
- Core's packages and dependencies are declared once, in [tool.krrood.core-boundary] of krrood/pyproject.toml; no other file restates them.
- `krrood check` (CoreBoundaryChecker) reports a core module loading a non-core module or a disallowed distribution at module level.
