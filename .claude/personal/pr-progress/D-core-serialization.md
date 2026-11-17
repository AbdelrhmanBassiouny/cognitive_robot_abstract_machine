Plan
- Keep #66 and the stack above it mergeable and answered for the cram2 #974 review.

Done
- 2026-11-17: fixed the name clash, the weak tests and the scope comment; merged `main`.
- Renamed RDRSerializer, RDRModuleAttribute and RDRModuleLocalName to RippleDownRules... through all ten branches with basstler's `SymbolRename` (mentions included). Moved `module_loading.py` to #159. Imported `classproperty` from `patterns` with `ImportRelocation`. Markdown by text replacement. Both actions are new, in basstler#245 (draft, on #222).
- Each branch's `test_eql_rdr` and `test_code_generation` compared with its state before the merge: no new failures.

Next
- Read CI on the pushed heads (not read).
- Owner: reply on the cram2 #974 threads (nothing was posted), and decide the `classproperty` abstract-method port and the `integration-conflict` label.
- basstler#243 and #245 are drafts waiting on review; #245 waits on #222.
