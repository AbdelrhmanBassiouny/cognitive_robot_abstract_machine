**Plan**
- Test first: serializer imports with sqlalchemy/scipy/casadi blocked (done)
- Move HasGeneric and NoGenericError into krrood.patterns (done)
- Move scipy sparse serializers to their own module (done)
- Wait for CI on the ORM/DAO tests I could not run locally

**Done**
- Draft PR #610 pushed, labelled maintenance + api-break, description written
- casadi/symbol_graph part was already landed in f9f6b17

**Next**
- Read CI; decide with code owners whether old import paths stay as re-exports
