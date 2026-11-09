## Plan
- Attempt plain imports under TYPE_CHECKING; ImportError binds no name (developer-approved try/except); runtime imports keep raising

## Done
- 88b34936ee on #545: covers uninstalled packages, missing krrood parts, missing dependencies, extended package paths; 220 krrood tests pass, RDR unchanged, krrood check clean; PR description updated

## Next
- Developer review of #545 (marked ready by developer); CI result
- After #546 lands: move helpers into krrood.source_analysis, reuse ModuleLevelImportFinder.type_checking_flag
