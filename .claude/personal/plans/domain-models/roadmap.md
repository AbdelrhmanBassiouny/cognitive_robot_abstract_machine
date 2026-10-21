# domain-models — standing rules

- A domain model under `domain_models/` depends only on `krrood` and external libraries, never on another workspace package.
- Never duplicate a class to drop a dependency. Shared behaviour lives once in an abstract base; implementations bind its generic coordinate parameter.
- casadi is an optional extra (`krrspatial[symbolic]`); numeric types import none of it.
- Spatial types are generic over their coordinate type. Integer coordinates get no operations whose results leave the integers (norms, scaling, rotations, transforms).
- Package names (krrspatial, krrimage, krrollywood) are open to change in review.
