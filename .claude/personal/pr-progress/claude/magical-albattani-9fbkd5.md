Two PRs, decided with the user: full krrood is 2 GB / ~2.5 min install, unfit for a plugin.

Plan
- PR A `claude/krrood-core-package` off main: new light workspace package `krrood_core`
  (deps: typing_extensions only) holding DataclassException, classproperty, singleton,
  SubclassJSONSerializer/DataclassJSONSerializer core, SubClassSafeGeneric, PathEnumeration;
  krrood depends on it and re-exports at the old paths; numpy/scipy/SortedSet serializers stay.
- PR B (this branch) off #501 with PR A merged in: basstler depends on krrood_core; exceptions
  -> DataclassException; board.json/run report round-trips -> serializer; drop basstler's
  classproperty/PathEnumeration; session start installs ./krrood_core editable.
- Add both as items to plan basstler-package.

Done
- Branch re-cut from #501 head. Measured krrood cost.

Next
- Build PR A.
