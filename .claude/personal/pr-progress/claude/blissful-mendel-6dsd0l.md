## Plan
- Indefinite article: the determiner pass picks the lexeme "a"; the morphology pass realizes a/an (SimpleNLG), pending user approval
- Then run the verbalization and EQL suites, format, and update the PR description

## Done
- Guard test: building clauses loads no inflect, lemminflect, typeguard, jinja2 or IPython (passes)
- Cardinal, index ordinal, verb form and collection-element noun leaves realized by the morphology pass
- WIP commit e6b59b94f pushed

## Next
- Wait for the user's answer on the a/an design; test_existential_noun_pluralised_by_the_pass fails until then
