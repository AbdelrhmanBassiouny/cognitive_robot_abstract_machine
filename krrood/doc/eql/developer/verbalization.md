---
jupytext:
  text_representation:
    extension: .md
    format_name: myst
    format_version: 0.13
    jupytext_version: 1.16.4
kernelspec:
  display_name: Python 3
  language: python
  name: python3
---

# Verbalization Internals

This guide explains the architecture of the EQL verbalization subsystem for developers who want to understand, extend, or debug it.  End-user documentation lives in {doc}`../user/verbalization`.

## Overview

The verbalization subsystem translates any EQL symbolic expression into a human-readable English string or a structured fragment tree that can be rendered in plain text, ANSI colour, or HTML.

The entry points are:

```python
# Simplest — plain text, no colour
from krrood.entity_query_language.verbalization.verbalizer import verbalize_expression
text = verbalize_expression(query)

# Full control — choose format, colour, layout, and hyperlinks
from krrood.entity_query_language.verbalization.pipeline import VerbalizationPipeline
pipeline = VerbalizationPipeline.html(hierarchical=True, link_resolver=resolver)
html = pipeline.verbalize(query)
```

---

## Architecture: the Three-Layer Pipeline

```{mermaid}
graph LR
    A[EQL Expression] --> B[EQLVerbalizer]
    B -- VerbFragment tree --> C[FragmentRenderer]
    C -- formatted string --> D[Output]
    E[RuleEngine] -. dispatches .-> B
    F[VerbalizationContext] -. shared state .-> B
    G[Formatter] -. markup .-> C
    H[SourceLinkResolver] -. URLs .-> C
```

### Layer 1 — Fragment Building (`EQLVerbalizer`)

{py:class}`~krrood.entity_query_language.verbalization.verbalizer.EQLVerbalizer` walks the EQL expression tree and produces a parallel tree of
{py:class}`~krrood.entity_query_language.verbalization.fragments.base.VerbFragment` nodes.

It does not produce strings directly. Every call to `build(expr, ctx)` returns a `VerbFragment` — rendering (plain/ANSI/HTML) is deferred to Layer 2.

`EQLVerbalizer` delegates to four sub-verbalizers:

| Sub-verbalizer | Responsibility |
|---|---|
| {py:class}`~krrood.entity_query_language.verbalization.rule_engine.RuleEngine` | Dispatches each expression to the first matching `VerbalizationRule` |
| {py:class}`~krrood.entity_query_language.verbalization.entity_verbalizer.EntityVerbalizer` | Entity / SetOf query rendering (FIND, SUCH THAT, GROUPED BY, …) |
| {py:class}`~krrood.entity_query_language.verbalization.chain_verbalizer.ChainVerbalizer` | MappedVariable chain rendering (possessive paths, bool predicates) |
| {py:class}`~krrood.entity_query_language.verbalization.rule_verbalizer.RuleVerbalizer` | IF … THEN … inference-rule rendering |

### Layer 2 — Fragment Rendering (`FragmentRenderer`)

{py:class}`~krrood.entity_query_language.verbalization.rendering.renderer.FragmentRenderer` traverses the `VerbFragment` tree and produces a single string.

Two concrete renderers:

| Renderer | Output style |
|---|---|
| {py:class}`~krrood.entity_query_language.verbalization.rendering.renderer.ParagraphRenderer` | Flat prose; BlockFragments joined inline |
| {py:class}`~krrood.entity_query_language.verbalization.rendering.renderer.HierarchicalRenderer` | Indented bullet lists; each BlockFragment nesting level adds one indent |

### Layer 3 — Format Markup (`Formatter`)

{py:class}`~krrood.entity_query_language.verbalization.rendering.formatter.Formatter` injects format-specific characters into the renderer output.

| Formatter | Colour encoding | Space | Newline | Links |
|---|---|---|---|---|
| {py:class}`~krrood.entity_query_language.verbalization.rendering.formatter.PlainFormatter` | none | `" "` | `"\n"` | no |
| {py:class}`~krrood.entity_query_language.verbalization.rendering.formatter.ANSIFormatter` | `\033[38;2;R;G;Bm` | `" "` | `"\n"` | OSC 8 |
| {py:class}`~krrood.entity_query_language.verbalization.rendering.formatter.HTMLFormatter` | `<span style="color:…">` | `&nbsp;` | `<br>` | `<a href>` |

---

## Fragment Type Hierarchy

All verbalization output is expressed as a tree of `VerbFragment` subclasses before rendering.  Understanding this hierarchy is essential for writing new rules or renderers.

```
VerbFragment (abstract base)
├── WordFragment          — plain text: articles, punctuation, connectives
├── RoleFragment          — text + SemanticRole + optional SourceRef (for hyperlinking)
├── PhraseFragment        — inline sequence of child fragments joined by a separator
└── BlockFragment         — header + list of item fragments (flattens or indents on render)
```

### SemanticRole and Colours

{py:class}`~krrood.entity_query_language.verbalization.fragments.roles.SemanticRole` determines the colour applied by formatters.  Colours match the `QueryGraph.ColorLegend` palette for visual consistency with query graph visualizations.

| Role | Example | Colour |
|---|---|---|
| `KEYWORD` | *Find*, *If*, *such that* | yellow `#eded18` |
| `VARIABLE` | *Robot*, *Employee 1* | cornflower blue |
| `AGGREGATION` | *sum of*, *number of* | red-orange `#F54927` |
| `OPERATOR` | *is greater than*, *is* | orange `#ff7f0e` |
| `LOGICAL` | *and*, *or*, *not*, *for all* | green `#2ca02c` |
| `LITERAL` | `42`, `"hello"` | gray `#949292` |
| `ATTRIBUTE` | *battery*, *tasks* | teal `#8FC7B8` |
| `PLAIN` | *of*, *the*, *,* | none |

### Building Fragments

Convenience factory methods avoid repetitive construction:

```python
from krrood.entity_query_language.verbalization.fragments.base import (
    WordFragment, RoleFragment, PhraseFragment, BlockFragment,
    join_with, oxford_and,
)
from krrood.entity_query_language.verbalization.fragments.roles import SemanticRole

# Plain word
word = WordFragment(text="the")

# Coloured word with optional source link
role_frag = RoleFragment.for_variable("Robot", robot_var)      # VARIABLE role + source link
attr_frag = RoleFragment.for_attribute("battery", Robot, "battery")  # ATTRIBUTE role + link
op_frag   = RoleFragment.for_operator("is greater than")       # OPERATOR role, no link

# Inline sequence
phrase = PhraseFragment.spaced(word, role_frag, op_frag)

# Oxford-comma join
list_frag = oxford_and([frag_a, frag_b, frag_c], Conjunctions.AND.as_fragment())

# Block structure (renders as bullets in HierarchicalRenderer)
block = BlockFragment(header=keyword_frag, items=[item1, item2])
```

---

## Rule Dispatch Mechanism

`EQLVerbalizer.build(expr, ctx)` delegates to `RuleEngine.build(expr, ctx, delegate)`, which:

1. Checks `ctx.binding_overrides` for the expression's `_id_` — if found, returns the override fragment immediately (see [Binding Overrides](#binding-overrides) below).
2. Iterates the sorted rule list and calls `rule_cls.applies(expr, ctx)`.
3. Calls `rule_cls.transform(expr, ctx, delegate)` on the first matching rule.
4. Falls back to `WordFragment(text=expr._name_)` when no rule matches.

### MRO-Depth Sorting

Rules are sorted by `__mro__.index(VerbalizationRule)` (descending) at `RuleEngine` construction time.  A deeper MRO index means the class is more specific (closer to `VerbalizationRule` in the hierarchy).  This ensures subclass rules shadow parent rules without requiring explicit priority integers.

Example from `rules/logical.py`:

```
NotRule           (depth 1)   ← generic fallback
├── NotComparatorRule (depth 2)  ← tried first: Not(Comparator)
└── NotBoolAttrRule   (depth 2)  ← tried first: Not(bool Attribute)
```

### Adding a New Rule

1. Create a class in the appropriate `rules/*.py` file (or a new file).
2. Subclass {py:class}`~krrood.entity_query_language.verbalization.rule_engine.VerbalizationRule` (or an existing rule for deeper priority).
3. Implement `applies(cls, expr, ctx) -> bool` and `transform(cls, expr, ctx, delegate) -> VerbFragment`.
4. Register the class in {py:data}`~krrood.entity_query_language.verbalization.rules.registry.ALL_RULES`.

```python
# rules/my_rule.py
from krrood.entity_query_language.verbalization.rule_engine import VerbalizationRule
from krrood.entity_query_language.verbalization.fragments.base import WordFragment
from my_package.expressions import MyExpression

class MyRule(VerbalizationRule):
    """Verbalizes MyExpression as 'my custom phrase'."""

    @classmethod
    def applies(cls, expr, ctx) -> bool:
        return isinstance(expr, MyExpression)

    @classmethod
    def transform(cls, expr, ctx, delegate):
        child = delegate.build(expr.child, ctx)
        return PhraseFragment.spaced(WordFragment(text="my custom phrase"), child)
```

Then in `rules/registry.py`, add `MyRule` to `ALL_RULES`.

---

## VerbalizationContext Internals

A single {py:class}`~krrood.entity_query_language.verbalization.context.VerbalizationContext`
instance is threaded through the entire `EQLVerbalizer.build()` call tree.

### Coreference Tracking (`seen`)

```python
ctx.seen: dict   # maps expr._id_ → display label
```

The first time a `Variable` is encountered, `noun_for_parts()` records it in `seen` and returns `INDEFINITE` (→ "a Robot").  Subsequent encounters return `DEFINITE` (→ "the Robot").

### Disambiguation Map

Created by `VerbalizationContext.from_expression(expr)`, which pre-scans the full expression tree.  Types with a single variable keep the plain type name; collisions get numbered labels:

```
Robot    (single)  →  "Robot"
Apple 1  (first)   →  "Apple 1"
Apple 2  (second)  →  "Apple 2"
```

### Constraint Frames

Used by the `InstantiatedVariable` verbalization path:

```python
ctx.push_constraint_frame()   # open a frame
ctx.defer_constraint(expr)    # add expr to the top frame
deferred = ctx.pop_constraint_frame()  # retrieve and close
```

When an `Entity` is used as a chain root inside an `InstantiatedVariable`, its WHERE condition is deferred into the top frame rather than verbalized inline.  After all binding overrides are registered, the deferred expressions are verbalized and emitted as a *"such that …"* clause.

### Binding Overrides

```python
ctx.binding_overrides: dict   # maps expr._id_ → VerbFragment
```

Populated by `_verbalize_instantiated_natural` for each field binding.  Before any rule is consulted, `RuleEngine.build` checks this dict.  This ensures that when a variable appears a second time as a WHERE condition value, the renderer uses the same *"the field of the Type"* fragment rather than re-verbalizing the raw variable.

---

## Source References and Link Resolvers

{py:class}`~krrood.entity_query_language.verbalization.fragments.source_ref.SourceRef`
is a frozen dataclass that identifies the Python entity a `RoleFragment` represents:

```python
SourceRef(cls=Robot)                          # class reference
SourceRef(cls=Robot, attribute="battery")     # attribute reference
```

A {py:class}`~krrood.entity_query_language.verbalization.rendering.source_link_resolver.SourceLinkResolver`
maps these to URL strings:

```python
class SourceLinkResolver(Protocol):
    def resolve(self, ref: SourceRef) -> Optional[str]: ...
```

The built-in implementation is {py:class}`~krrood.entity_query_language.verbalization.rendering.source_link_resolver.AutoAPIResolver`,
which builds Sphinx AutoAPI URLs:

```python
from krrood.entity_query_language.verbalization.rendering.source_link_resolver import AutoAPIResolver
from krrood.entity_query_language.verbalization.pipeline import VerbalizationPipeline

# Auto-detect local docs
resolver = AutoAPIResolver.for_package("krrood")
pipeline = VerbalizationPipeline.html(link_resolver=resolver)
```

The resolver is passed to the renderer at construction time (via `VerbalizationPipeline` factory methods).  When `_render_role` encounters a `RoleFragment` with a non-`None` `source_ref` and a non-`None` `_link_resolver`, it calls `resolver.resolve(ref)` and wraps the coloured text with a hyperlink.

---

## Specialized Verbalizers

### EntityVerbalizer

Handles three forms of `Entity` rendering:

| Method | When used | Output form |
|---|---|---|
| `verbalize_query` | Top-level query | *"Find X such that …"* |
| `as_noun` | Nested Entity selector | *"a Robot where …"* |
| `as_inline_noun` | Chain root inside InstantiatedVariable | *"a Robot"* (defers WHERE) |

The IF/THEN inference-rule form is detected in `verbalize_query` and delegated to `RuleVerbalizer.verbalize`.

### ChainVerbalizer

Builds *"the attr of the Root"* possessive paths from walked chains:

```
robot.arm.joint   →  "the joint of the arm of the Robot"
```

Boolean terminal attributes trigger the predicative form:

```
robot.is_charging  →  "the Robot is charging"
Not(robot.is_charging)  →  "the Robot is not charging"
```

### RuleVerbalizer

Handles `Entity` queries whose selected variable is an `InstantiatedVariable`.  Uses `RuleAnalyzer.analyze()` to decompose the query into:

- **Primary antecedents** — IF clause bullets (have conditions)
- **Secondary antecedents** — registered for coreference only
- **Consequent bindings** — THEN clause bullets

---

## How to Add a New Output Format

Subclass {py:class}`~krrood.entity_query_language.verbalization.rendering.formatter.Formatter` and optionally
{py:class}`~krrood.entity_query_language.verbalization.rendering.renderer.FragmentRenderer`:

```python
from dataclasses import dataclass
from krrood.entity_query_language.verbalization.rendering.formatter import Formatter
from krrood.entity_query_language.verbalization.fragments.roles import SemanticRole, ROLE_COLORS

@dataclass
class MarkdownFormatter(Formatter):
    """Renders colour as Markdown bold (no true colour support in plain Markdown)."""

    def colorize(self, text: str, role: SemanticRole) -> str:
        if role in (SemanticRole.KEYWORD, SemanticRole.VARIABLE):
            return f"**{text}**"
        return text

    @property
    def space(self) -> str:
        return " "

    @property
    def newline(self) -> str:
        return "\n"

    def wrap_link(self, text: str, url: str) -> str:
        return f"[{text}]({url})"
```

Then pass it to any `FragmentRenderer`:

```python
from krrood.entity_query_language.verbalization.rendering.renderer import ParagraphRenderer
from krrood.entity_query_language.verbalization.pipeline import VerbalizationPipeline

pipeline = VerbalizationPipeline(ParagraphRenderer(MarkdownFormatter()))
```

---

## API Reference

### Core

- {py:class}`~krrood.entity_query_language.verbalization.verbalizer.EQLVerbalizer`
- {py:func}`~krrood.entity_query_language.verbalization.verbalizer.verbalize_expression`
- {py:class}`~krrood.entity_query_language.verbalization.pipeline.VerbalizationPipeline`
- {py:class}`~krrood.entity_query_language.verbalization.context.VerbalizationContext`
- {py:class}`~krrood.entity_query_language.verbalization.context.ArticleSelection`
- {py:class}`~krrood.entity_query_language.verbalization.rule_engine.VerbalizationRule`
- {py:class}`~krrood.entity_query_language.verbalization.rule_engine.RuleEngine`

### Fragment Hierarchy

- {py:class}`~krrood.entity_query_language.verbalization.fragments.base.VerbFragment`
- {py:class}`~krrood.entity_query_language.verbalization.fragments.base.WordFragment`
- {py:class}`~krrood.entity_query_language.verbalization.fragments.base.RoleFragment`
- {py:class}`~krrood.entity_query_language.verbalization.fragments.base.PhraseFragment`
- {py:class}`~krrood.entity_query_language.verbalization.fragments.base.BlockFragment`
- {py:func}`~krrood.entity_query_language.verbalization.fragments.base.join_with`
- {py:func}`~krrood.entity_query_language.verbalization.fragments.base.oxford_and`
- {py:class}`~krrood.entity_query_language.verbalization.fragments.roles.SemanticRole`
- {py:data}`~krrood.entity_query_language.verbalization.fragments.roles.ROLE_COLORS`
- {py:func}`~krrood.entity_query_language.verbalization.fragments.roles.role_for`
- {py:class}`~krrood.entity_query_language.verbalization.fragments.source_ref.SourceRef`

### Rendering

- {py:class}`~krrood.entity_query_language.verbalization.rendering.renderer.FragmentRenderer`
- {py:class}`~krrood.entity_query_language.verbalization.rendering.renderer.ParagraphRenderer`
- {py:class}`~krrood.entity_query_language.verbalization.rendering.renderer.HierarchicalRenderer`
- {py:class}`~krrood.entity_query_language.verbalization.rendering.formatter.Formatter`
- {py:class}`~krrood.entity_query_language.verbalization.rendering.formatter.PlainFormatter`
- {py:class}`~krrood.entity_query_language.verbalization.rendering.formatter.ANSIFormatter`
- {py:class}`~krrood.entity_query_language.verbalization.rendering.formatter.HTMLFormatter`
- {py:class}`~krrood.entity_query_language.verbalization.rendering.source_link_resolver.SourceLinkResolver`
- {py:class}`~krrood.entity_query_language.verbalization.rendering.source_link_resolver.AutoAPIResolver`

### Sub-Verbalizers and Analysis

- {py:class}`~krrood.entity_query_language.verbalization.entity_verbalizer.EntityVerbalizer`
- {py:class}`~krrood.entity_query_language.verbalization.chain_verbalizer.ChainVerbalizer`
- {py:class}`~krrood.entity_query_language.verbalization.rule_verbalizer.RuleVerbalizer`
- {py:class}`~krrood.entity_query_language.verbalization.rule_analysis.RuleAnalyzer`
- {py:class}`~krrood.entity_query_language.verbalization.rule_analysis.RuleStructure`
- {py:class}`~krrood.entity_query_language.verbalization.rule_analysis.AntecedentInfo`
- {py:class}`~krrood.entity_query_language.verbalization.rule_analysis.ConsequentBinding`
- {py:class}`~krrood.entity_query_language.verbalization.rule_analysis.AggregationStatus`

### Utilities

- {py:func}`~krrood.entity_query_language.verbalization.chain_utils.walk_chain`
- {py:func}`~krrood.entity_query_language.verbalization.chain_utils.chain_root`
- {py:func}`~krrood.entity_query_language.verbalization.chain_utils.build_path_parts`
- {py:func}`~krrood.entity_query_language.verbalization.chain_utils.verbalize_plural`
- {py:func}`~krrood.entity_query_language.verbalization.utils._str`
- {py:func}`~krrood.entity_query_language.verbalization.utils._camel_to_words`
- {py:func}`~krrood.entity_query_language.verbalization.utils._ordinal`
- {py:func}`~krrood.entity_query_language.verbalization.utils._ensure_plural`

### Vocabulary

- {py:class}`~krrood.entity_query_language.verbalization.vocabulary.english.Keywords`
- {py:class}`~krrood.entity_query_language.verbalization.vocabulary.english.Logicals`
- {py:class}`~krrood.entity_query_language.verbalization.vocabulary.english.Aggregations`
- {py:class}`~krrood.entity_query_language.verbalization.vocabulary.english.Copulas`
- {py:class}`~krrood.entity_query_language.verbalization.vocabulary.english.Operators`
- {py:class}`~krrood.entity_query_language.verbalization.vocabulary.english.Articles`
- {py:class}`~krrood.entity_query_language.verbalization.vocabulary.english.ExistentialPhrase`
- {py:class}`~krrood.entity_query_language.verbalization.vocabulary.words.PlainWord`
- {py:class}`~krrood.entity_query_language.verbalization.vocabulary.words.RoleWord`
- {py:class}`~krrood.entity_query_language.verbalization.vocabulary.words.OperatorPhrase`
- {py:class}`~krrood.entity_query_language.verbalization.vocabulary.words.VocabEnum`

### Rule Registry

- {py:data}`~krrood.entity_query_language.verbalization.rules.registry.ALL_RULES`
