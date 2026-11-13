Plan:
- Run krrood tests per directory, then the other packages that import classproperty
- Add api-break and maintenance labels; update plan item notes
Done:
- All five core crossings removed (classproperty, ontomatic introspector, helpers, causal_relation, module_generation), with a boundary test; commit f9f6b1719
- Decided: dev tools stay out of core; remove all crossings; helpers becomes entity_query_language.class_diagram_lookup
- ORM regeneration fails on main too (coraplex DetectAction), so it isn't from this PR
Next:
- Read the krrood test results and fix any failure the moves caused
