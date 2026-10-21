PR #524 (draft, stacked on #512): domain_models/krrimage + Color moved out of SemDT.

Plan
- krrimage: Resolution, ImagePoint, ImageBox, Pixel, PixelBox, ColorImage, Color.

Done
- Package, wiring (workspace, CI, version test, ORM further_source_folders), tests pushed.

Next
- Check CI's ORM build (local generate_orm fails on base too: MetaData).
- Then: cram2/crollywood on krrimage; depth/segmentation images, intrinsics.
- Discuss a geometry domain model split from SemDT with the user.
