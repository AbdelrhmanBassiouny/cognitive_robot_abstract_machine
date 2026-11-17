## Plan
- Test: loading EQL in a fresh interpreter loads no inflect, lemminflect, jinja2, IPython
- Cardinal and index ordinal become leaves realized by the morphology pass
- Verb read off a class name becomes a leaf lemmatized by the morphology pass
- Indefinite article chosen only in the determiner pass
- Run the verbalization suite and doctests unchanged

## Done
- Branch, draft PR #611, plan record

## Next
- Write the failing import test
