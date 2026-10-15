> **Closed 2026-10-15: the ICRA 2027 experiments were completed on the ICRA branches outside this plan. What remains is landing that code upstream one PR at a time.**

# icra-mechanism — standing rules

- The two core mechanisms (per-predicate routing by declared capability, and the physics verification backend) live here, not in `knowledge-directed-perception`. That plan's `imagination-world-rejects-what-a-predicate-refuses` item is covered by `physics-verification-backend` in its narrow form and should be marked so there rather than built twice.
- Three lanes, one per person (see below); items in different lanes run in parallel, an item waits only on what `depends_on`/`blockers` names.
