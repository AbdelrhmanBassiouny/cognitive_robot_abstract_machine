# Domain models

Standalone packages, each modelling one domain, that other packages use without pulling
in the rest of the workspace. A domain model depends on `krrood` and on libraries outside
this repository, never on another workspace package such as `semantic_digital_twin`.

- `krrspatial`: points and vectors in reference frames.
