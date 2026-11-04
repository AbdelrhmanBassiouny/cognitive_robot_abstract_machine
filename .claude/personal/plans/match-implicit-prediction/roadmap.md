# Infer predicted attributes in underspecified matches

- `...` means *predict*; selective backends keep rejecting it. An unstated attribute is what leaves a selective query unconstrained.
- An optional field is predicted only when the pattern marks it with `...`; inference never touches fields that have defaults.
- Inference runs only in generative backends, so selective evaluation is unaffected by it.
- A pattern given a domain takes existing objects: `...` there completes a missing attribute, and required-field inference never applies to it.
