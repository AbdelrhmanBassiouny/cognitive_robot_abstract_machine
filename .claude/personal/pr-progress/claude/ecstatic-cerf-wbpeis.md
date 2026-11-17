**Plan**
- Wait for CI on 98eefdb to confirm probabilistic_model passes
- Decide with code owners whether old import paths stay as re-exports

**Done**
- Serializer loads without sqlalchemy/scipy/casadi (fresh-interpreter test)
- HasGeneric/NoGenericError moved to krrood.patterns; sparse serializers in their own module
- CI failure in probabilistic_model fixed: probability_table.py imports the sparse serializer module

**Next**
- Read the next CI run
