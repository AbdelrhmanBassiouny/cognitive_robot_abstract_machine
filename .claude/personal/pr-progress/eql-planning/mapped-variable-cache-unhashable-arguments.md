## Plan
- Resolve #540's fork review and keep cram2 #837 (tomsch420 requested changes) in step.

## Done
- bdcb38fd1a: `CallSignature`, `CallArguments`, `ArgumentsPassableOnlyByPosition` live in `krrood.class_diagrams`; `bind`/`keyword_arguments` take `*args, **kwargs`. 1650 passed (patterns, eql, class_diagram). Bind and move threads resolved.

## Next
- Owner: resolve the four older open threads; update the #540 description (`CallSignature` in class_diagrams, new exception, factory test patches `inspect` directly).
- Next maintenance pass carries d543f35349..bdcb38fd1a to cram2 #837; tomsch420 re-reviews.
