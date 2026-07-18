## P2 operand naming — PR #87 (draft, base main). REDESIGN PENDING developer direction.

First cut pushed (commit 2f7c989a): `microplanning/operand_naming.py`, occurrence count on
`ReferringExpressions`, wired at `InstantiatedVerbalizableRule.build`; snapshot + hand-written
surfaces + 2 doctests updated. CI fully green (18 checks incl. krrood + sdt).

Developer reviewed (12 comments) and contests the design — do NOT proceed until confirmed:
- Remove hardcoded heuristics (`GENERIC_OPERAND_NAMES`, ordinal-prefix stripping). Deterministic or
  explicit field metadata; no "sometimes wrong" heuristics.
- Occurrence-count anonymity + type-based grouping is a smell. Disambiguate off referent identity
  (`_id_` / equality), integrating the existing coreference machinery — not type/name collision.
- "the other point" → indefinite "a point … another point" for fresh distinct entities. Labels
  (numbers vs ordinals — open q; I recommend ordinal words) only for REUSED/tracked entities.
- Concrete-type operand: type identifies on first mention ("a Handle" / "a body of type Handle"),
  then coreference. Field name is NOT a blanket replacement for the type.
- Triple: "a point, a second point, and a third point ARE collinear" (all "a", plural copula — real
  agreement gap for conjunctive subjects). Concise "Three points are collinear" → P3.
- IsSubclass operands should use literal VALUES (value-using form) → P3, not this PR.
- Small: `%%` dividers in test_operand_naming.py; rename reachability example attribute → "location"
  (intent unconfirmed).

Posted synthesis + recommendations in-session (AskUserQuestion tool errored; asked in text). Nothing
re-pushed, no threads resolved. Fallback check-in armed. NEXT on direction: rewrite operand_naming
to lean on coreference/_id_, drop heuristics, fix plural copula, then reply-and-resolve each thread.
