PR #186 (draft, `bug`) — item `chain-outside-evaluation-truncates-silently`, track
`mapping-semantics` of the `match-query-ergonomics` plan. Off `main`, independent of #182.

**Commits**
1. `9587ca1c4` — `apply_mapping_on_external_root` took `next(...)` of each step, so a step
   reaching several values contributed only its first. Now reports instead.
2. `21bbc73c9` — `Projection` separates mappings determined by their child and arguments
   from anonymous iteration; `flat_variable`'s cache bypass stated and guarded.
3. `bd3aab87a` — `Index` split into `IndexByValue` (a `Projection`) and
   `IndexByExpression`, so the walk checks the chain's mappings instead of counting values.
4. `436514635` — review: the operators that build a mapping name it in their return type;
   `Index`/`IndexByValue`/`IndexByExpression`/`Call` became generic so `Iterable[T]` is
   expressible.
5. `b5b084522` — review: write-back moved to `IndexByValue`; the base stored under the key
   the index holds, which for an expression key is the expression object. Chasing it found
   `_set_external_root_instance_value_` still had the first-value truncation its reading
   sibling was fixed for.

**State**: full krrood suite 2158 passed; the 2 `test_object_diagram` failures are this
container missing the Graphviz `dot` binary and fail identically on `main`.

**Open on #186 (both awaiting the developer)**
- Is `Projection` the right term? I argue it collides with the SQL select-list sense, since
  we already have `_selected_variables_`; proposed `SingleValueMapping`, caveat that the
  honest guarantee is *at most* one value. Thread left unresolved.
- `query/match.py:661` walks an access path with `current_value[step._key_]` under
  `isinstance(step, Index)`, carrying the same expression-key assumption. Pre-existing;
  offered to fix here or separately.

**Two process notes worth keeping**
- Never edit the tree while a suite runs — two phantom `test_generation_process` failures
  came from exactly that, not from a regression.
- Another session appended its own roadmap §14 concurrently; mine collided and is now §15.
  Re-fetch and check section numbering before appending to a shared roadmap.

**Also still open for the developer, from #182's rounds**
(a) `having` without `grouped_by` crashes on a `None` deref (`query.py:628`) on any query
type; one-line fix verified, offered as its own focused PR.
(b) name-based selection (`query["Body"]`) as a language feature, if wanted.
