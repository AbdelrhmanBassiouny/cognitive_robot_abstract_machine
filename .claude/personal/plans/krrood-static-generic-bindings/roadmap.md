# krrood static generic bindings
- The runtime and the static reader share one binding computation; neither re-implements it.
- Nothing in this plan imports, checks out or installs the code under review, and nothing generates stubs or binds a derived parameter a second time by hand.
- basstler's triage knows no krrood pattern: krrood plugs in through the triage's extension point.
- A property, method or classproperty shares one annotation across subclasses, so its type hint names type parameters (tuple[~GenericCoordinate, ...] for a point's coordinates) where a field is narrowed. krrood's one type-hint method takes the owning class and substitutes what it binds, derived parameters included; EQL keeps calling only that method.
