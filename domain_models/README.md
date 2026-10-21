# Domain models

Standalone packages, each modelling one domain, that other packages use without pulling
in the rest of the workspace. A domain model depends on `krrood` and on libraries outside
this repository, never on another workspace package such as `semantic_digital_twin`.

- `krrimage`: images and the positions, boxes and colours on them.
