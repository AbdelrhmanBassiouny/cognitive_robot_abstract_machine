# Why these are free functions, not methods on a class

This note answers a standing review question: *for every function in the EQL
verbalization subsystem that is **not** a method on a class, why is it free, and
why didn't we make a class for it?*

It covers **all 82 module-level functions** in
`entity_query_language/verbalization/`, grouped by the single principle that
keeps each one free. The short version is at the top; the per-function tables
follow.

## The principle

A class earns its place when it does at least one of:

1. **Bundles state with behaviour** — it has fields its methods read or mutate.
2. **Defines a substitutable abstraction** — an interface with two or more
   implementations chosen polymorphically.
3. **Is a value or identity** — an entity/value object with equality and a
   lifecycle.

A function that is a **pure transformation of its arguments**, with no shared
state and no sibling implementation to swap in, gains nothing from a class.
Wrapping it produces a *stateless utility class*: a namespace with extra
ceremony and a `self` nobody reads. A Python module already **is** a namespace,
so the module is the function's correct home.

> References: Fowler, *Refactoring* — *Replace Method with Method Object* is
> motivated by **state** to capture; with none, it is noise. Jack Diederich,
> *"Stop Writing Classes"* (PyCon 2012) — the stateless one-or-two-method class
> should be a function.

The decisive observation is that **wherever this subsystem actually met criteria
1–3, we did build the class.** The free functions are what is *left over* after
the object model is in place — and that residue is small and well-typed:

| Where state / polymorphism lives | The class we built |
| --- | --- |
| Per-construct surface rules (open/closed) | `PhraseRule` + the `*Rule` registry |
| Plan → fragment realisation | `Assembler`, `Planner` hierarchies |
| Competing surface templates for one slot | `SpecificityRule` families: `ConditionForm`, `PredicateTransform`, `RestrictionSubjectRule`, `RankingForm` |
| Conjunct coordination strategies | `ConjunctReducer`, `ConjunctFold` (`RangeBoundFold`, `CoindexedComparisonFold`) |
| Output format (plain / ANSI / HTML) | `Formatter`, `Renderer` hierarchies |
| Referring-expression discourse state | `ReferringExpressions`, `DiscourseModel` |
| The fragment IR itself | the `VerbalizationFragment` dataclass tree |

Everything below is the residue, in seven kinds.

---

## Category 1 — Recursion schemes (catamorphism / functor map)

`engine.fold`, `engine.root_context`, `engine._with_source`,
`fragments.base.fold_fragment`, `map_fragment`, `map_structural_children`,
`flatten_fragment_to_plain_text`.

A recursion scheme is parameterised by an **algebra** (the per-node handlers),
not by object state. `fold_fragment(fragment, word=…, role=…, phrase=…,
block=…)` is the F-algebra catamorphism over the fragment tree: the *scheme* is
the unit of reuse, and each caller supplies a different algebra (flattening,
lowering, plain-text). Making it a method on `VerbalizationFragment` would either fix one
algebra per node class or force a `Visitor` object — re-introducing exactly the
double-dispatch boilerplate the fold removes, scattered across the leaf
subclasses. The scheme lives **once**, free, and every consumer reuses it.

`engine.fold` is the same idea over the *EQL* algebra: the grammar is the
algebra, `fold` is the scheme. `root_context` exists so the recursion
continuation (`recurse`) is defined in exactly one place and shared by `fold`
and the match assembler. `_with_source` is the post-step stamping provenance on
the produced fragment.

> Refs: Meijer, Fokkinga & Paterson (1991), *Bananas, Lenses, Envelopes and
> Barbed Wire*; Bird & de Moor (1997), *Algebra of Programming*.

---

## Category 2 — The one public verb over a polymorphic class family (dispatch facades)

`ranking_surface`, `grammar.conditions.placement.place`,
`grammar.conditions.subject.restriction_subject`,
`grammar.framework.phrase_rule.select`.

The object model **is** the class family behind each of these
(`RankingForm`, `ConditionForm`, `RestrictionSubjectRule`, the `PhraseRule`
set). The free function is a one-line facade —
`RankingForm.most_applicable(request).render(request)` — that gives callers a
verb without exposing the registry. It owns no state and has no alternative
implementation, so it is not itself a polymorphic thing.

These *could* be `@classmethod`s on the base (`RankingForm.surface(...)`). They
are kept as free verbs deliberately, for **one** reason: the subsystem uses the
same shape for every such family — `place(condition, subject)`,
`restriction_subject(query)`, `ranking_surface(request)`, `select(node, rules,
context)` — so the call sites read uniformly and the construct's own `rules` /
`ranking` module is the home. One convention, applied everywhere, beats four
near-identical classmethods.

---

## Category 3 — Pure recognisers over EQL nodes

`grammar.conditions.recognition.*` — `attribute_names`, `single_hop_attribute`,
`is_none_literal`, `is_concrete_object_literal`, `is_atomic_value`, `references`,
`is_boolean_attribute_chain`, `superlative_aggregation`.

Each is `Expression -> bool | Optional[…]`: a stateless classifier answering one
independent question (*"is this an absence literal?"*, *"does this reference the
subject?"*). They share no state and are never asked as a group about a single
held object, so a `ConditionRecognizer` class would have **no fields** — a
stateless namespace. The cohesive home is `recognition.py`, which is that
namespace. (Were several always asked together about one subject, a value object
bundling the answers could pay off — they are not.)

---

## Category 4 — Stateless builders that emit fragments

`microplanning.possessive.*` (`possessive_path`, `pronominal_path`,
`coordinated_genitive`, `attribute_fragment`, `_genitive_step`,
`_relative_clause`, `_extend_hop`); `grammar.query.ranking._cardinal`,
`_key_attribute`, `_quality`; `vocabulary.english.copula_with`,
`predicative_operator`; the pure helpers in `microplanning.coordination`
(`build_between`, `coindexed_natural_parts`, `group_by_owner`,
`group_consecutive_by_owner`, `has_pair`, `coindexed_signature`,
`fold_coindexed_groups`, `fold_range_pairs`, `reduce_conjuncts`,
`_attribute_pair`, `_between_operator`, `_chain_key`, `_classify`,
`_terminal_attribute`).

Each is a pure `inputs -> VerbalizationFragment | data`. They are the *grammar of a phrase
shape*, not an object: nothing persists between calls, so there is nothing to
encapsulate. Where coordination genuinely had a **strategy with state**, we
built it — the `ConjunctFold` subclasses own the fold state machine; these free
functions are the leaf helpers those strategies and the assemblers share. A
shared leaf cannot belong to one sibling class, and hoisting it to a
`@staticmethod` on a common base adds ceremony without adding state.

---

## Category 5 — Stateless facades over a library or lexicon

`morphology.*` (`plural`, `ensure_plural`, `is_plural`, `is_past_participle`,
`indefinite_article`, `ordinal`, `cardinal`); `value_lexicon.value_phrase`;
`relational_attributes.relational_verb`, `relational_verb_phrase`.

A facade over an external library (`inflect`, `lemminflect`) or a fixed lexicon,
with a single shared engine as deliberate module-level state (the
`inflect.engine()` singleton). The facade is *the one place the subsystem touches
inflection*. A class here would be a singleton-with-methods — which is what a
module already is.

---

## Category 6 — Generic algorithms over arbitrary classes

`grammar.framework.specificity.most_specific`, `mro_depth`,
`concrete_subclasses`; `grammar.framework.phrase_rule._is_guarded`.

These are generic over **any** class or rule (`mro_depth(cls)`,
`concrete_subclasses(cls)`). Binding a generic MRO/subclass-graph algorithm to a
method on one type would mis-scope it — it belongs to no single class because it
serves all `SpecificityRule` families equally. They underpin the class
machinery; they are not themselves a domain object.

---

## Category 7 — IO / module-wiring plumbing (not verbalization logic)

`pipeline._is_ipython`, `pipeline.verbalize_expression`;
`rendering.formatter.detect_osc8_support`; `rendering.realization.realize_tree`,
`realize_subtree`; `rendering.source_documentation.*`
(`first_docstring_line`, `docstring_for_source_ref`, `_annotated_target_name`,
`_string_expression_first_line`, `_attribute_docstrings`);
`grammar.framework.registry._load_rule_modules`.

Environment detection, package import, AST docstring scraping for hyperlinks, and
pipeline wiring. `verbalize_expression` is the public one-liner over the
`VerbalizationPipeline` class, which holds the renderer/verbalizer state; the
function is the convenience facade bound to the shared plain pipeline. None of
these perform linguistic logic, so per the doctest scope they are also the set
that does **not** carry a `>>>` example.

---

## Decisions taken

- **Moved** (a clear case, done earlier, commit `b93f177`): the three
  referring-expression helpers `_aggregation_source_ids`,
  `_numberable_type_name`, `_build_disambiguation_map` onto
  `ReferringExpressions` — they read that class's construction inputs and had no
  other caller, so they met criterion 1 (state) and belonged on the class.

- **Considered and kept free** (recommended): every function in Categories 1–7
  above, for the reason stated in its category.

- **Open for your call** (recommended: keep free):
  - `navigation_path.build_path_parts` → `PathStep.from_chain` classmethod. It
    builds a `List[PathStep]`, so a constructor-on-the-type is idiomatic; kept
    free because its body is a *parser* dispatching over EQL node kinds
    (`Attribute` / `Index` / `Call` / `FlatVariable`), i.e. logic about reading
    the EQL chain, not about being a `PathStep`.
  - `grammar.query.ranking._quality` / `_cardinal` / `_key_attribute` →
    `@staticmethod`s on `RankingForm`. Shared by the sibling form subclasses;
    kept free as module-private leaves because a static-method cluster with no
    state is the same stateless namespace with more ceremony.
