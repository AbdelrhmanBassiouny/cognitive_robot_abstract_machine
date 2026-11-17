## Plan
- Clause building decides features; the morphology pass realizes every word, including a/an (SimpleNLG)

## Done
- Guard test: building clauses loads no inflect, lemminflect, typeguard, jinja2 or IPython
- Cardinal, index-ordinal, verb-form, collection-element-noun and indefinite-article leaves
- Verbalization + core-boundary tests 786 passed; formatted; PR #611 description and labels updated

## Next
- User: rename `as_fragment` (flagged by krrood check, an API change)?
- semantic_digital_twin's predicate_clause users were not run here
