# Design Patterns

KRROOD ships two complementary design patterns for building structured, type-safe object models:
**PropertyDelegator** and **Role**. Both patterns deal with the same underlying challenge — you have an
object of type `A` that needs to expose the attributes and behaviour of another object of type `B` — but
they answer different questions about *ownership* and *identity*.

Use this page to decide which pattern fits your situation, then follow the link to the detailed guide.

## Choosing the right pattern

```{mermaid}
%%{init: {'theme': 'base', 'themeVariables': {'fontSize': '20px', 'lineColor': '#333333', 'primaryColor': '#ddeeff', 'primaryTextColor': '#111111', 'primaryBorderColor': '#3a7abf', 'edgeLabelBackground': '#ffffff'}, 'flowchart': {'nodeSpacing': 60, 'rankSpacing': 80, 'padding': 20}}}%%
flowchart TD
    Q1{"Does object A contain<br/>object B as a field?"}
    Q2{"Should A and B be<br/>considered the same entity<br/>(same hash / equality)?"}
    Q3{"Does A need context-specific<br/>attributes that B does not have?"}
    PD["<b>PropertyDelegator</b><br/>Transparent attribute forwarding.<br/>A wraps B; A and B are distinct objects.<br/>→ property_delegator.md"]
    ROLE["<b>Role</b><br/>Identity-preserving extension.<br/>A and B share identity; A adds context.<br/>→ role.md"]
    NEITHER["Neither pattern is needed.<br/>Use plain composition or inheritance."]

    Q1 -->|Yes| Q2
    Q1 -->|No| NEITHER
    Q2 -->|No| Q3
    Q2 -->|Yes| ROLE
    Q3 -->|Yes| PD
    Q3 -->|No| NEITHER
```

## Quick comparison

| | PropertyDelegator                              | Role |
|---|------------------------------------------------|---|
| Relation | A **has-a** B (composition)                    | A **is-a contextual extension of** B |
| Identity | A ≠ B (separate objects)                       | A == B (same entity, different view) |
| Role registry | No                                             | Yes — `b.roles[A]` |
| Role chaining | No                                             | Yes — roles of roles |
| Typical use | Transparent wrapper around a component         | Context-specific semantic view of an object |
| Example | `Robot` exposing `Torso`'s `arms` and `legs` directly | `Kitchen` contextualising a `Room` |

## Pattern guides

- {doc}`property_delegator` — when to use it, how it works, and worked examples from the robot domain.
- {doc}`role` — identity-sharing roles, the role registry, role chaining, and worked examples.
