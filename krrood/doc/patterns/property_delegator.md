# PropertyDelegator

## What is it?

`PropertyDelegator[T]` is a pattern for **transparent attribute forwarding**. When class `A` holds an
instance of class `B` as a field, `PropertyDelegator` automatically generates properties on `A` that
forward every attribute and method of `B`. The result is that callers can write `a.some_attr` instead
of `a.b_field.some_attr`, without any hand-written boilerplate.

It is the foundation on which the [Role](role.md) pattern is built. Every `Role[T]` is also a
`PropertyDelegator[T]`, but the reverse is not true — you can use `PropertyDelegator` on its own
whenever you want simple, transparent delegation without identity sharing.

---

## Motivating problem

Consider a `Robot` that contains a `Torso`. The torso holds the robot's `arms` and `legs` and
provides motion methods. Without a delegation pattern, every call site has to dereference `.torso`
explicitly:

```python
@dataclass
class Arm:
    name: str
    reach: float

@dataclass
class Leg:
    name: str
    length: float

@dataclass
class Torso:
    arms: List[Arm]
    legs: List[Leg]

    def move(self, direction: str) -> str:
        return f"Torso moving {direction}"

@dataclass
class Robot:
    torso: Torso
    name: str
```

```python
robot = Robot(torso=Torso(arms=[Arm("left", 0.8), Arm("right", 0.8)],
                          legs=[Leg("left", 1.0), Leg("right", 1.0)]),
              name="R2D2")

# Every call site carries the .torso. dereference
print(robot.torso.arms)          # [Arm("left", ...), Arm("right", ...)]
print(robot.torso.legs)          # [Leg("left", ...), Leg("right", ...)]
print(robot.torso.move("north")) # "Torso moving north"
```

`robot.arms` and `robot.legs` is what callers mean. The fact that these live on a nested `Torso` is
an implementation detail that should not leak into every call site.

---

## Solution

Inherit from `PropertyDelegator[Torso]`, declare which field holds the torso, and let the transformer
generate the forwarding properties:

```python
from krrood.patterns.property_delegator import PropertyDelegator
from dataclasses import dataclass, field

@dataclass
class Robot(PropertyDelegator[Torso], DelegatorForTorso):
    torso: Torso
    name: str

    @classmethod
    def delegatee_attribute_name(cls) -> str:
        return "torso"
```

```python
robot = Robot(torso=Torso(arms=[Arm("left", 0.8), Arm("right", 0.8)],
                          legs=[Leg("left", 1.0), Leg("right", 1.0)]),
              name="R2D2")

# Torso attributes are now directly accessible on Robot
print(robot.arms)          # [Arm("left", ...), Arm("right", ...)]
print(robot.legs)          # [Leg("left", ...), Leg("right", ...)]
print(robot.move("north")) # "Torso moving north"

# Robot's own attributes are unaffected
print(robot.name)          # "R2D2"
```

---

## How it works

### 1. Declaring the delegatee

Subclass `PropertyDelegator[T]`, declare the field that holds the `T` instance, and implement
`delegatee_attribute_name()` to return that field's name:

```python
@dataclass
class Robot(PropertyDelegator[Torso]):
    torso: Torso   # the delegatee field
    name: str

    @classmethod
    def delegatee_attribute_name(cls) -> str:
        return "torso"
```

### 2. Code generation — the DelegatorFor mixin

`PropertyDelegator` alone does not add any properties. The actual forwarding properties are generated
at development time by `RoleTransformer`. For each delegatee type `T`, the transformer produces a
`DelegatorFor<T>` mixin class and writes it to a `role_mixins/` sibling folder of your module.

For the `Robot` → `Torso` case the generated mixin looks like this (simplified):

```python
# role_mixins/robots_role_mixins.py  (auto-generated — do not edit)

class DelegatorForTorso(ABC):
    @property
    @abstractmethod
    def delegatee(self) -> Torso: ...

    @property
    def arms(self) -> List[Arm]:
        return self.delegatee.arms

    @arms.setter
    def arms(self, value: List[Arm]) -> None:
        self.delegatee.arms = value

    @property
    def legs(self) -> List[Leg]:
        return self.delegatee.legs

    @legs.setter
    def legs(self, value: List[Leg]) -> None:
        self.delegatee.legs = value

    def move(self, direction: str) -> str:
        return self.delegatee.move(direction)
```

Your class then inherits from both `PropertyDelegator[Torso]` and the generated mixin:

```python
from role_mixins.robots_role_mixins import DelegatorForTorso

@dataclass
class Robot(PropertyDelegator[Torso], DelegatorForTorso):
    torso: Torso
    name: str

    @classmethod
    def delegatee_attribute_name(cls) -> str:
        return "torso"
```

### 3. The `delegatee` cached property

Internally, `PropertyDelegator` provides a `delegatee` cached property that calls
`getattr(self, delegatee_attribute_name())`. The generated `DelegatorFor<T>` mixin declares
`delegatee` as an abstract property so that IDEs and type checkers know its return type. The concrete
subclass satisfies this contract via the matching field (`torso`).

### 4. Regenerating the mixins

Run the transformer whenever you add a new delegator class or change a delegatee type:

```python
from krrood.patterns.role.helpers import transform_roles_in_class_diagram

transform_roles_in_class_diagram(your_module, write=True)
```

The generated files are committed alongside the source — they are plain Python and should be treated
as part of your codebase.

---

## When to use PropertyDelegator

- You have **composition** (A contains B as a field) and want callers to access B's interface
  directly on A.
- You want **type-safe, IDE-friendly delegation** rather than a dynamic `__getattr__` override.
- Callers repeatedly dereference the same intermediate field — the chain is noise, not domain logic.
- You are building a **Role** (see [Role pattern](role.md)) — `Role[T]` already extends
  `PropertyDelegator[T]`, so you get delegation for free.

## When NOT to use PropertyDelegator

- **B's attributes semantically belong to A directly** — in that case, give A the fields itself or
  use inheritance.
- **A and B must be considered the same entity** (same hash, equality) — use the [Role](role.md)
  pattern instead.
- **The delegatee field is optional and may be `None`** — generated properties will raise
  `AttributeError` if the delegatee is absent; guard with `None`-checks or keep explicit access.
- **The delegatee changes at runtime** — `delegatee` is a `cached_property`; the delegation target
  is fixed after construction.
- **Delegating would create a name clash** — if A already has an attribute with the same name as one
  on B, the generated property silently shadows it; prefer explicit delegation in that case.

---

## API reference

### `PropertyDelegator[T]`

`krrood.patterns.property_delegator.PropertyDelegator`

| Member | Kind | Description |
|---|---|---|
| `delegatee_attribute_name()` | abstract classmethod | Returns the name of the field that holds the `T` instance. |
| `delegatee` | cached_property | Returns `getattr(self, delegatee_attribute_name())`. |
| `get_delegatee_type()` | classmethod | Returns the resolved runtime type of `T`, handling forward references and TypeVars. |

The generated `DelegatorFor<T>` mixin provides one property/method per public attribute of `T`. It
is produced by `RoleTransformer` and placed in `role_mixins/<module>_role_mixins.py`.
