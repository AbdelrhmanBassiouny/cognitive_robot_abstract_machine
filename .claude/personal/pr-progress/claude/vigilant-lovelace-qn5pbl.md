Plan:
- ORMatic imports the modules of every class a specialized generic's DAO names (its type arguments too)
Done:
- Fix and test in the first commit; krrood ORMatic, code-generation and class-diagram tests pass locally
Next:
- Read CI on the PR
- Union fields and union TypeVar bounds stay out of scope until the shared point interface for #549 is decided
