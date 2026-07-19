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

# Why-Questions Internals

This guide covers the design of the *why* ask surface: how
{py:func}`~krrood.entity_query_language.factories.why` and
{py:class}`~krrood.entity_query_language.rdr.why.WhyQuery` turn "why was this concluded?"
into a first-class EQL construct that verbalizes through the causal grammar. End-user
documentation lives in {doc}`../user/why_questions`.

## Where it sits

The *why* capability is built in layers, each closed for modification once landed:

1. **The answer core** ({py:mod}`~krrood.entity_query_language.rdr.why`) — selects, from the
   classification trace, the fired rule and the conditions that justified the conclusion, and
   packages them as a {py:class}`~krrood.entity_query_language.rdr.why.WhyAnswer`. This is
   *content selection* only: it reads the trace the reasoner already produced.
2. **Causal verbalization** ({py:mod}`~krrood.entity_query_language.verbalization.grammar.causal`)
   — realises a `WhyAnswer` as *"&lt;conclusion&gt; because &lt;conditions&gt;, by the
   &lt;kind&gt; rule"*.
3. **The ask surface** (this layer) — a factory and an expression node that let a caller
   *pose* the question as a composable EQL construct over an explanation the reasoner already
   produced.

## The construct

{py:func}`~krrood.entity_query_language.factories.why` sits in the EQL grammar module beside
`entity`, `an`, and `match`, and returns a
{py:class}`~krrood.entity_query_language.rdr.why.WhyQuery`. The query wraps an explanation
**source** and reads its {py:class}`~krrood.entity_query_language.rdr.why.WhyAnswer` lazily and
once.

- **It composes over a produced explanation, never over the concluded value.** An RDR binds
  *existing, shared* values — in the zoo, one `Species.mammal` member is concluded for dozens
  of animals — so an explanation cannot live on the value: it would be one global slot
  overwritten per classification, and primitives cannot carry attributes at all. The
  explanation is produced once, model-side, and rides on the **result** the reasoner yields.
- **Composition is verbalization.** A `WhyQuery` is a non-foldable root, like a `Match` or a
  bare `WhyAnswer`: the verbalizer routes it through the shared rule registry rather than by a
  hard-coded branch. Its {py:class}`~…grammar.causal.rules.WhyQueryRule` (construct `WhyQuery`,
  disjoint from the `WhyAnswer` rule so `select` never ties) reads the query's answer and hands
  it to the *same* `CausalAssembler`. A query thus verbalizes identically to the answer it
  stands for — the ask surface adds a construct, not a second grammar.

### The explanation-source seam

`WhyQuery` depends on an abstraction, not on a reasoner. Its source is a
{py:data}`~krrood.entity_query_language.rdr.why.WhyAnswerSource` — one of:

- an {py:class}`~krrood.entity_query_language.rdr.why.ExplanationCarrier`: a yielded result
  handle exposing a `conclusion_explanation`. This is the idiomatic surface — a decision is an
  underspecified query over a partially-specified object, choosing is evaluating it with an RDR
  backend, and each fresh handle carries the explanation of how it was filled;
- an {py:class}`~krrood.entity_query_language.rdr.why.RDRConclusionExplanation` — the case
  store-read, e.g. `rdr.explain(case)`;
- a bare `WhyAnswer`.

{py:func}`~krrood.entity_query_language.rdr.why.resolve_why_answer` is the single place a
subject is mapped to its answer, so admitting a new kind of source is one branch there rather
than a new query type. Because the seam is the `ExplanationCarrier` *protocol* (structural),
`why(...)` reads a real yielded handle unchanged the moment the RDR backend attaches
explanations to results — that model-side store and attachment are delivered by the
`rdr/decision-queries` work; this construct is deliberately decoupled from it and tested here
against a carrier mimic.

## Why an explanation rides on the result

Placing the explanation on the result rather than the value is the **why-provenance witness**
model. A witness is a record of *which inputs and which rule* were responsible for a derived
datum, and it annotates the *derivation*, not the value: the provenance semirings of
{cite:t}`green2007provenance` annotate derived tuples, and the why-provenance of
{cite:t}`buneman2001why` characterises the source that justifies each result — neither attaches
to a shared value, precisely because a value participates in many derivations. An RDR
conclusion is a derived datum in exactly that sense, so its witness — the fired rule and the
satisfied conditions — belongs on the yielded result, and `why(...)` exposes it there.

Two further lines ground the design:

- **Justifications (JTMS).** {cite:t}`doyle1979truth` records, for each belief, the
  justification that supports it, so beliefs can be explained and retracted when their support
  changes. A `WhyAnswer` is the read side of the same idea — the justification of one
  conclusion — and shares its value objects with the planned justification-recording (TMS)
  work, where retraction over the dependency graph is added.
- **RDR rule-trace explanation.** {cite:t}`compton1990philosophical` argue that an expert's
  knowledge is best captured, and best explained, as the *context in which a rule fires* — the
  cornerstone case and the discriminating conditions — rather than as decontextualised logic.
  The `rule_code`, `rule_depth`, and `corner_case` a `WhyAnswer` carries are precisely that
  trace.

## Contrastive questions are reserved

`WhyQuery` carries a `contrast`, and `why(source, contrast=...)` records it, but answering a
*contrastive* question — *why this rather than that?* — is not implemented; reading the answer
of a contrastive query raises (see
{py:data}`~krrood.entity_query_language.rdr.why.CONTRAST_NOT_IMPLEMENTED`).
{cite:t}`miller2019explanation` observes that human why-questions are almost always
contrastive, and answering them means comparing the fact against a *foil*: for RDR that is
contrasting the sufficient-condition sets of the two conclusions to surface the first guard the
foil fails. The field and the plumbing are in place so that capability can be added without
changing the ask surface.

```{note}
The `%why` line magic — asking *why* interactively about the last classified case — is
deferred until the interactive RDR interface lands. The construct here is what that magic will
call; it is intentionally usable without any interactive session.
```

## References

The provenance, truth-maintenance, rule-trace, and contrastive-explanation entries cited above
are collected in the {doc}`/bibliography`.
