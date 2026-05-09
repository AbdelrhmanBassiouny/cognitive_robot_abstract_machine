# Role Pattern

## What is it?

The **Role** pattern lets an existing object take on a new semantic context — adding context-specific
attributes and behaviour — while **remaining the same entity**. A role and its role taker share
identity: they compare equal, have the same hash, and point to each other through a role registry.

This is the key difference from [PropertyDelegator](property_delegator.md). A `PropertyDelegator`
wraps a contained object (A has-a B, A ≠ B). A `Role` extends an existing object in context (A is a
contextual view of B, A == B).

`Role[T]` extends `PropertyDelegator[T]`, so all delegation mechanics described in the
PropertyDelegator guide apply here too. The Role pattern adds identity sharing, a role registry, and
support for role chaining on top.

---

## Motivating problem

In a robot's semantic world model, a physical `Cabinet` is represented as a single object with a body,
storage space, and apertures. Now suppose the robot is in a kitchen and that cabinet is a fridge —
it has doors and a specific temperature zone. In a bedroom, an identical cabinet is a wardrobe — it
has different drawers and stores clothes.

The naive approach creates separate objects:

```python
cabinet = Cabinet(...)
fridge = Fridge(cabinet=cabinet, doors=[...])
wardrobe = Wardrobe(cabinet=cabinet, drawers=[...])
```

But now `cabinet`, `fridge`, and `wardrobe` are three distinct Python objects. Any code that asks
"is this the fridge?" must look it up from the cabinet manually. Equality checks break. The cabinet
does not know it is being used as a fridge. When the robot updates `cabinet.objects`, the fridge does
not reflect the change automatically because it delegates reads — but callers that hold a `Fridge`
reference see the right data while callers that hold the `Cabinet` reference do not know a `Fridge`
context exists.

The Role pattern makes `fridge == cabinet` and `hash(fridge) == hash(cabinet)`. The cabinet knows
about the fridge. There is one physical entity, viewed in two semantic contexts.

---

## Quick example

### Defining a role taker

The object that *takes on* a role must include `HasRoles`. This mixin adds a `roles` dictionary that
maps each active role type to the role instance:

```python
from krrood.patterns.role import HasRoles
from dataclasses import dataclass, field

@dataclass(eq=False)
class Cabinet(Furniture, HasCaseAsRootBody, HasRoles):
    ...
```

### Defining a role

Inherit from `Role[T]` (where `T` is the role taker type), add the role taker as a field, and
implement `role_taker_attribute()` to point to that field:

```python
from krrood.patterns.role.role import Role
from krrood.entity_query_language.factories import variable_from

@dataclass(eq=False)
class Fridge(Role[Cabinet], DelegatorForCabinet, HasDrawers, HasDoors):
    cabinet: Cabinet          # the role taker

    @classmethod
    def role_taker_attribute(cls) -> Attribute[Cabinet]:
        return variable_from(cls).cabinet
```

`DelegatorForCabinet` is the generated mixin (see [PropertyDelegator](property_delegator.md)) that
forwards `Cabinet`'s attributes onto `Fridge`.

### Using the role

```python
cabinet = Cabinet(...)
fridge = Fridge(cabinet=cabinet, doors=[...])

# Identity is shared
assert fridge == cabinet
assert hash(fridge) == hash(cabinet)

# Role registry: the cabinet knows about the fridge
assert cabinet.roles[Fridge] is fridge

# Cabinet attributes are accessible directly on the fridge (via delegation)
fridge.root           # → cabinet.root
fridge.objects        # → cabinet.objects
fridge.hole_direction # → cabinet.hole_direction

# Role-specific attributes live on the fridge
fridge.doors
fridge.drawers
```

---

## More examples from semantic_annotations

### Multiple roles for the same role taker type

A `Cabinet` can be a `Fridge`, a `Wardrobe`, or a `Dresser`. Each is a separate role class that
attaches different context-specific attributes to a plain `Cabinet`:

```python
@dataclass(eq=False)
class Fridge(Role[Cabinet], DelegatorForCabinet, HasDrawers, HasDoors):
    cabinet: Cabinet
    ...

@dataclass(eq=False)
class Wardrobe(Role[Cabinet], DelegatorForCabinet, HasDrawers, HasDoors):
    cabinet: Cabinet
    ...

@dataclass(eq=False)
class Dresser(Role[Cabinet], DelegatorForCabinet, HasDrawers, HasDoors):
    cabinet: Cabinet
    ...
```

Each role is independent. The same cabinet can have at most one role of each type at a time (the
`roles` dict is keyed by role type).

### Room roles — Kitchen, Bedroom, Bathroom, LivingRoom

A `Room` is a physical area. Its semantic purpose — *kitchen*, *bedroom*, *living room* — is a role:

```python
@dataclass(eq=False)
class Room(SemanticAnnotation, HasRoles):
    floor: Floor = field(kw_only=True)

@dataclass(eq=False)
class Kitchen(Role[Room], DelegatorForRoom):
    room: Room

    @classmethod
    def role_taker_attribute(cls) -> Attribute[Room]:
        return variable_from(cls).room

@dataclass(eq=False)
class Bedroom(Role[Room], DelegatorForRoom):
    room: Room

    @classmethod
    def role_taker_attribute(cls) -> Attribute[Room]:
        return variable_from(cls).room
```

Usage:

```python
room = Room(floor=floor)
kitchen = Kitchen(room=room)

assert kitchen == room
assert room.roles[Kitchen] is kitchen

# Room attributes accessible on kitchen (via DelegatorForRoom)
kitchen.floor   # → room.floor
```

### Typed container roles — WineBottle, SoapBottle, MustardBottle

A `Bottle[TLiquid]` is generic. A `WineBottle` is a `Bottle[Wine]` used in a wine context, a
`SoapBottle` is a `Bottle[LiquidSoap]` used for soap:

```python
@dataclass(eq=False)
class Bottle(HasCaseAsRootBody, HasStorageSpace[TLiquid]):
    ...

@dataclass(eq=False)
class WineBottle(Role[Bottle[Wine]], DelegatorForBottle):
    bottle: Bottle[Wine]

    @classmethod
    def role_taker_attribute(cls) -> Attribute[Bottle[Wine]]:
        return variable_from(cls).bottle

@dataclass(eq=False)
class SoapBottle(Role[Bottle[LiquidSoap]], DelegatorForBottle):
    bottle: Bottle[LiquidSoap]

    @classmethod
    def role_taker_attribute(cls) -> Attribute[Bottle[LiquidSoap]]:
        return variable_from(cls).bottle
```

The role carries the semantic meaning (this bottle *is* a wine bottle), while the underlying `Bottle`
object holds the physics, geometry, and storage space.

---

## Identity sharing

When a `Role` is constructed, `__post_init__` automatically registers it in the role taker's `roles`
dict and links the two objects in the symbol graph. From that point on:

- `role == role_taker` (and vice versa)
- `hash(role) == hash(role_taker)`
- `role_taker.roles[RoleClass]` returns the role instance

This means any collection, set, or dictionary keyed by the original object automatically reflects the
role, and code that receives either object can navigate to the other:

```python
cabinet = Cabinet(...)
fridge = Fridge(cabinet=cabinet)

# Both references refer to "the same thing" in sets and dicts
s = {cabinet}
assert fridge in s

# Navigate from either direction
fridge.role_taker         # → cabinet
cabinet.roles[Fridge]     # → fridge
```

---

## Role chaining

A role's role taker can itself be a role. This is called **role chaining** and lets you layer multiple
levels of semantic context onto a single physical entity.

In the university ontology example bundled with krrood's tests, a `Person` can become a `CEO`, and a
`CEO` can become a `Representative`:

```python
@dataclass(eq=False)
class Person(Symbol):
    name: str

@dataclass(eq=False)
class CEO(Role[Person]):
    person: Person
    head_of: Company = None

@dataclass(eq=False)
class Representative(Role[CEO]):
    ceo: CEO
    represents: Company = None
```

All three objects are equal and have the same hash:

```python
person = Person(name="Alice")
ceo = CEO(person=person, head_of=acme)
rep = Representative(ceo=ceo, represents=acme)

assert rep == ceo == person
assert hash(rep) == hash(ceo) == hash(person)

# Each role taker in the chain sees all roles
assert person.roles[CEO] is ceo
assert person.roles[Representative] is rep
```

The `Role` class provides helpers to navigate chains:

| Method / Property | Description |
|---|---|
| `role.role_taker` | The immediate role taker (may itself be a role). |
| `Role.get_root_role_taker_type()` | Walks the chain to find the non-Role base type. |
| `role.role_taker_roles` | All roles registered on the root role taker. |
| `Role.has_role(entity, RoleType)` | Checks if `entity` (or anything equal to it) has the given role. |
| `Role.get_taker_roles_of_type(entity, RoleType)` | Returns all roles of a given type. |

---

## How it works

### `__post_init__`

When a role is constructed, `Role.__post_init__` runs automatically (because `Role` is a
`@dataclass`). It:

1. Retrieves the role taker from the declared field (`role_taker_attribute_name()`).
2. Registers `self` in `role_taker.roles[type(self)]`.
3. Updates the symbol graph to link the role and role taker.

### `role_taker_attribute()`

This abstract classmethod must be implemented by every role subclass. It returns a symbolic
`Attribute` reference to the role-taker field, which both the transformer and EQL use for type
introspection and query generation:

```python
@classmethod
def role_taker_attribute(cls) -> Attribute[Cabinet]:
    return variable_from(cls).cabinet
```

### Shared fields

If the role class and the role taker class share a common base (e.g. both inherit `Symbol`), the
shared fields — such as a persistent `id` — are not duplicated. The role's fields for those
attributes are set to `init=False` and delegate to the role taker via the generated mixin.

### The generated `RoleFor` mixin

`RoleTransformer` generates a `DelegatorFor<RoleTaker>` mixin (identical in structure to the
[PropertyDelegator](property_delegator.md) mixin) that forwards every public attribute and method of
the role taker onto the role. This is how `fridge.root` reaches `fridge.cabinet.root`.

---

## When to use the Role pattern

- An object needs **context-specific attributes** that do not logically belong to the original type
  but are tightly coupled to a specific usage of that object.
- The extended object and the original object must be **considered the same entity** throughout the
  system (same hash, equality, shared identity in collections).
- You are modelling an **ontology concept** where the same physical thing plays different semantic
  roles in different situations (room → kitchen, cabinet → fridge, bottle → wine bottle).
- You want a **role registry**: any part of the system should be able to ask "does this cabinet have a
  fridge role?" without scanning all fridge instances.

## When NOT to use the Role pattern

- **The extension is permanent and always present** — if every cabinet is always a fridge, just
  inherit from `Cabinet` directly.
- **You do not need identity sharing** — if the wrapper and the wrapped object can be separate
  entities, a plain [PropertyDelegator](property_delegator.md) is simpler.
- **You need more than one role of the same type at the same time** — the `roles` dict is keyed by
  type, so only one instance of each role type per role taker is supported.
- **The role taker type changes after construction** — `delegatee` is a `cached_property`; the role
  taker is fixed.

---

## Decision guide

```{mermaid}
%%{init: {'theme': 'base', 'themeVariables': {'fontSize': '20px', 'lineColor': '#333333', 'primaryColor': '#ddeeff', 'primaryTextColor': '#111111', 'primaryBorderColor': '#3a7abf', 'edgeLabelBackground': '#ffffff'}, 'flowchart': {'nodeSpacing': 60, 'rankSpacing': 80, 'padding': 20}}}%%
flowchart TD
    Q1{"Should the wrapper and<br/>the original object be<br/>the same entity?"}
    Q2{"Does the wrapper need<br/>its own attributes beyond<br/>what the original has?"}
    ROLE["<b>Role[T]</b><br/>Identity-sharing, role registry,<br/>optional chaining."]
    PD["<b>PropertyDelegator[T]</b><br/>Transparent forwarding,<br/>no identity sharing."]
    NEITHER["Plain composition or inheritance<br/>may be sufficient."]

    Q1 -->|Yes| ROLE
    Q1 -->|No| Q2
    Q2 -->|Yes| PD
    Q2 -->|No| NEITHER
```

---

## API reference

### `Role[T]`

`krrood.patterns.role.role.Role`

| Member | Kind | Description |
|---|---|---|
| `role_taker_attribute()` | abstract classmethod | Returns a symbolic `Attribute[T]` pointing to the role-taker field. |
| `role_taker_attribute_name()` | classmethod | Name of the role-taker field (derived from `role_taker_attribute()`). |
| `role_taker` | property | Semantic alias for `delegatee`; returns the role taker instance. |
| `get_role_taker_type()` | classmethod | Returns the type of `T`. |
| `get_root_role_taker_type()` | classmethod | Walks the chain to find the non-Role base type. |
| `has_role(entity, RoleType)` | classmethod | `True` if `entity` or any entity equal to it has a role of `RoleType`. |
| `get_taker_roles_of_type(entity, RoleType)` | classmethod | Returns all roles of `RoleType` for the given entity. |
| `role_taker_roles` | property | All roles registered on the root role taker. |
| `all_role_takers` | property | All role taker instances for this role. |

### `HasRoles`

`krrood.patterns.role.role.HasRoles`

A mixin that must be added to any class that will be used as a role taker. It adds:

| Member | Kind | Description |
|---|---|---|
| `roles` | field (`Dict[type, Any]`) | Registry mapping role type → role instance. Populated automatically on role construction. |
