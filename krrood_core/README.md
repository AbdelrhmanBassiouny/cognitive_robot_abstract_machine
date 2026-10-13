# krrood_core

The general Python patterns [krrood](../krrood) is built on, packaged so that tools which
need only these patterns can install them without krrood's scientific stack.

- `krrood_core.exceptions.DataclassException` - exceptions declared as dataclasses, with a
  message and a suggested correction.
- `krrood_core.adapters.json_serializer` - JSON (de)serialization that restores the
  concrete class it wrote, for dataclasses and any class registered with an
  `ExternalClassJSONSerializer`.
- `krrood_core.class_property.classproperty` - a value read off the class itself.
- `krrood_core.path_enumeration.PathEnumeration` - an enumeration whose members are paths.
- `krrood_core.standard_streams.StandardStreamHandler` - logging for a command-line tool,
  printing its output bare on standard output and its failures on standard error.

Its only dependencies are pure-Python packages. krrood depends on it and keeps every name
importable from its old place, so code written against krrood needs no change.
