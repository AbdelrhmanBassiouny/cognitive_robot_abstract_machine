## Plan
- Skip TYPE_CHECKING imports whose module is not found along its whole dotted path; runtime imports keep raising (developer decision)

## Done
- Full-path check (covers krrood.<part>) pushed to #545 at aee4130297 after merging main; 217 krrood tests pass, RDR unchanged; PR description updated

## Next
- Developer review of #545 (marked ready by developer); CI result
- After #546 lands: move helpers into krrood.source_analysis, reuse ModuleLevelImportFinder.type_checking_flag
