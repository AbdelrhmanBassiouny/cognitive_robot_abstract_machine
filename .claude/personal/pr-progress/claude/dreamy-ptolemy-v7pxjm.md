Plan:
- Failing test: core boundary checker reports nothing for any core module
- classproperty -> krrood.patterns.classproperty, update every importer
- symbol_graph imports DescriptorAwareIntrospector inside class_diagram builder
- causal_relation -> krrood.entity_query_language.causal_relation
- module_generation -> krrood.code_generation.module_generation (+ its test)
- Run krrood tests by package, pre-commit, update PR and plan notes
Done:
- Bootstrap, draft PR #608, item recorded in progress
- Decided: dev tools stay out of core; remove all core crossings
Next:
- Write the failing boundary test
