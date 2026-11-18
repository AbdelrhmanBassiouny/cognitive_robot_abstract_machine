## Plan
- Test first: krrood is a namespace package, version from importlib.metadata
- Remove krrood/__init__.py; module loggers; fix __file__/__version__ readers
- Fix publish workflow path and docs

## Done
- Bootstrap, draft PR #613
- Tests, __init__ removed, 8 logger imports replaced, readers fixed, wheel builds with all subpackages and no __init__
- 310 krrood tests pass

## Next
- Review; changelog has no Unreleased section, so no entry yet
- Decide home of _version.py in krrood-distributions
