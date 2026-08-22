PR #186 (draft, `bug`) — item `chain-outside-evaluation-truncates-silently`, track
`mapping-semantics` of the `match-query-ergonomics` plan. Off `main`, independent of #182.

**Commits**
1. `9587ca1c4` — `apply_mapping_on_external_root` took `next(...)` of each step, so a step
   reaching several values contributed only its first. Now reports instead.
2. `21bbc73c9` — a base class separates mappings determined by their child and arguments
   from anonymous iteration; `flat_variable`'s cache bypass stated and guarded.
3. `bd3aab87a` — `Index` split into `IndexByValue` (single-valued) and `IndexByExpression`,
   so the walk checks the chain's mappings instead of counting values.
4. `436514635` — review: the operators that build a mapping name it in their return type;
   `Index`/`IndexByValue`/`IndexByExpression`/`Call` became generic so `Iterable[T]` is
   expressible.
5. `b5b084522` — review: write-back moved to `IndexByValue`; the base stored under the key
   the index holds, which for an expression key is the expression object. Chasing it found
   `_set_external_root_instance_value_` still had the first-value truncation its reading
   sibling was fixed for.
6. `1ce18ca3c` — review: `Projection` renamed `SingleValueMapping`; `NotImplementedError`
   replaced by `ReadOnlyMapping`; the match walk takes the same index distinction.
7. `4a9eec6e5` — the rename had left the class docstring describing pre-split behaviour.
8. `2287715f7`, `d7f67696b` — review: the refusal to write says which question it answers
   (`Call` reaches one value and still cannot be written through) and names all five
   mappings.
9. `b8b9c1434` — test for the match walk's guard.

**State**: full krrood suite 2158 passed; the 2 `test_object_diagram` failures are this
container missing the Graphviz `dot` binary and fail identically on `main`. All review
threads on #186 replied to and resolved; PR description rewritten to match the current
state.

**Correction posted on #186**: I had said the match walk's bad case was unreachable
through the public API. Wrong — `AttributeMatch.variable` is typed
`Union[Attribute, FlatVariable]`, so a flattening there is what the field itself sanctions,
and the old `assert_never(step)` fired on it. Test added.

**Two process notes worth keeping**
- Never edit the tree while a suite runs — two phantom `test_generation_process` failures
  came from exactly that, not from a regression.
- Another session appended its own roadmap §14 concurrently; mine collided and is now §15.
  Re-fetch and check section numbering before appending to a shared roadmap.

**Still open for the developer, from #182's rounds**
(a) `having` without `grouped_by` crashes on a `None` deref (`query.py:628`) on any query
type; one-line fix verified, offered as its own focused PR.
(b) name-based selection (`query["Body"]`) as a language feature, if wanted.
