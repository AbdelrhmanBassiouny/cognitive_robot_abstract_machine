**Plan**
- Test first: fresh interpreter imports krrood.adapters.json_serializer with sqlalchemy, scipy, casadi blocked (fails today)
- Move HasGeneric and NoGenericError into krrood.patterns; update importers
- Move the scipy sparse-array serializers into their own adapters module
- Label the PR (maintenance; api-break if old paths are not kept)

**Done**
- Branch, draft PR #610, plan item recorded
- symbol_graph/casadi part found already landed in f9f6b17; nothing to do there

**Next**
- Install krrood's test environment, write the failing test
