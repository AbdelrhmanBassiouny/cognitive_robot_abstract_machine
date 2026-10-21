PR #524 (draft, stacked on #512): domain_models/krrimage + Color moved out of SemDT. Plan: domain-models.

Plan
- krrimage on krrspatial: drop ImagePoint/ImageBox/Pixel/PixelBox for krrspatial int/float points and boxes.

Done
- Package, wiring (workspace, CI, version test, ORM further_source_folders), tests pushed.

Next
- Blocked on krrspatial-numeric (claude/krrspatial); then restack #524 onto it.
- Check CI's ORM build (local generate_orm fails on base too: MetaData).
