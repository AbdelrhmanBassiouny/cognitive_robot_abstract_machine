## Plan
- Generic Extra/OptionalModule bases (krrood.patterns); KrroodOptionalModule.MATPLOTLIB.require on every matplotlib importer; `krrood optional-imports` check + hook; rule in shipped ImportsRules

## Done
- Review round 1 (decorator, generalization, checker) pushed in c9666cf146; 5 threads resolved, generalization thread replied, left open
- krrood suites green locally (krrood-only env)

## Next
- User: confirm leaving other libraries' adoption out, then resolve the agent_rules.py thread
- CI on #547; reconcile #546's offender lists with whichever lands second
- krrood-core-and-all-extras: switch MATPLOTLIB's extra to `all`
