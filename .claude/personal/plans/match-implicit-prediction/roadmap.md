# Infer predicted attributes in underspecified matches

- An optional field is predicted only when the pattern marks it with `...`; inference never touches fields that have defaults.
- Inference adds no query conditions, so selective evaluation and an already-lowered match are unaffected by it.
