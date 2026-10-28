PR #524 (draft, stacked on #527): domain_models/krrimage + Color moved out of SemDT. Plan: domain-models, item krrimage.

Plan
- krrimage on base krrspatial: ImagePlane, ImageCoordinateSystem, ImagePoint (PlanarPoint[ImageCoordinateSystem, float]), ImageBox, Pixel/PixelBox, ColorImage, Color.

Done
- a4e9bbdb: took ImagePlane and ImageCoordinateSystem into krrimage.coordinates from #527's review; geometry.py conflict with main resolved to krrimage's Color. 47 krrimage tests pass.

Next
- Check CI, including the ORM build (local generate_orm fails on base too: MetaData).
- Lands after cram2#761; move Color as #761 left it.
