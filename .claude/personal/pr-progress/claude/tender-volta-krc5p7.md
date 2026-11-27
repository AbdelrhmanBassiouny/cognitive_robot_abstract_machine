Plan
- Resolve upstream #1060's review; the owner answers LucaKro's open threads there.

Done
- f18503b5: add_facts and apply_effects fold with reduce (LucaKro's two state.py threads). Planning tests 120 passed and both doctests passed locally; fork CI and merge probe clean at 4fe32e5f.

Next
- Owner answers upstream: apply_effects(*effects) vs effects=, docstring notation (:: literal block is what the prose-length checker allows; a doctest counts as prose), krrood dataclass for init fields, affordances.
- Fork CI and merge probe at f18503b5 not read yet.
