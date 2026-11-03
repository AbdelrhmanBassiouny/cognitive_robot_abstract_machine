## Plan
- Stacked on #546 (which now holds the core-boundary checker). #547 itself: matplotlib imported inside drawing functions, tests that drawing raises ModuleNotFoundError

## Done
- Review round 2: enums/decorator removed; guard reworked in #546 (CoreBoundaryChecker + runtime backstop), merged here; local suites 328 passed
- 4 round-2 threads resolved

## Next
- CI on #546 and #547
- cyclopts thread open until command-line-on-cyclopts lands; agent_rules thread open (other libraries' adoption)
