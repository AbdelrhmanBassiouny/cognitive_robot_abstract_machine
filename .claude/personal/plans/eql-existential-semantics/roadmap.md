# eql-existential-semantics — standing rules

- Range supplied by the quantifier ⇒ the variable is mandatory. Tuple relational calculus (`∃t ∈ R`), Z (`∃ x : T | P`), Alloy (`some x: X | F`), OCL (`coll->exists(v | body)`), XQuery (`some $x in E satisfies P`), LINQ (`source.Any(x => …)`).
- Range supplied by the body ⇒ no variable. SQL's `EXISTS (subquery)`, SPARQL's `FILTER EXISTS { pattern }`, Cypher's `EXISTS { … }`, Datalog and Prolog rule bodies, and description logic's `∃R.C`, which has no variables in its syntax at all. Relational algebra likewise expresses ∃ purely as projection.
- The variable named only to control projection. Prolog's `bagof/3` groups by the goal's free variables, and `Y^Goal` marks `Y` existential so it stops participating in the grouping; `findall/3` is `bagof` with every free variable so marked. Explicitly about *which variables escape*, not *whether the goal is true*.
- It is mildly non-compositional. A condition's local set depends on the query around it. SQL has the same property. It means the set must be computed at build/plan time against the root, and *the same condition object reused in two queries can have two different local sets*.
- If you want the inner rows, don't use `exists`. That is SQL's story unchanged: `EXISTS` is a boolean filter; wanting the apples means writing the join.
- Sequence against #99: block wave 1 on it merging.
- OR / safe-range: own parallel track — characterize, then enforce.
- API migration: hard break, all five call sites in one PR, no deprecation shim.
- Tracking issue: yes (#137).
- `for_all` keeps its variable. The ∀/∃ split among a condition's free variables is not derivable and interleaved quantifier order is meaningful. `Exists` and `ForAll` sharing `QuantifiedConditional`'s `(left, right)` shape is a false symmetry, and it is what pulled the redundant argument in.
- Counting quantifiers are out of scope. `∃≥n` is a graded/qualified number restriction, cannot stop at the first witness, and is `count(...) >= n` — a different operator. Do not generalize `exists` into it. *(Amended 2026-08-29: this is the quantifier over one variable's bindings, which stays out of scope — `exists` must not be generalized into it.
