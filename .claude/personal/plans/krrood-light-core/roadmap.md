# krrood-light-core — standing rules

- Each krrood part is its own krrood-* distribution under the krrood.<part> namespace; the krrood distribution only depends on all of them, so `pip install krrood` stays whole.
- krrood-core is patterns, class_diagrams, symbol_graph and exceptions: Role is a pattern and inherits Symbol, so the three ship together. Its dependencies stay pure-Python or have Windows wheels (typing_extensions, rustworkx and its numpy, ordered_set, sortedcontainers).
- krrood distributions pin each other == the root VERSION; a krrood distribution depends on a basstler one only through a range (>=X,<next-major), so neither repository's release waits on the other.
- A library a distribution lists as optional is imported only inside the functions that need it (or under TYPE_CHECKING); everywhere else imports stay at the top.
- Each decoupling item removes boundary crossings; `krrood check --all-lines` over krrood/src lists the ones left, and the pre-commit hook blocks new ones.
- Never reimplement what the heavy library does to keep a feature in core; move the feature to the distribution that owns the library, unless the check is a plain stdlib type test (number_like_field).
- Each distribution's modules and dependencies are declared once, in one map; no other file restates them.
