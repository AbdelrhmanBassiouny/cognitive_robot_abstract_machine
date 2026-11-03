## Plan
- Stacked on #546. matplotlib imported inside drawing functions; OptionalImportChecker (shipped import rule, `krrood check`) reports module-level imports of extra-only distributions in core, read from krrood/pyproject.toml

## Done
- Review round 2 in 66174d0b5b: enums/decorator removed, checker on main's CodeRuleChecker, base retargeted to #546, graph_visualizer/rxnode off #546's offender list; 4 threads resolved
- Local suites green except test_core_boundary failures from main's new modules (object_reference, call_signature, identifier_and_name)

## Next
- #546 must take in main and absorb those core-boundary failures; then CI on #547
- cyclopts thread open until command-line-on-cyclopts lands; agent_rules thread open (other libraries' adoption)
