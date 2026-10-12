# Statecharts

A cramph statechart composes behaviour out of small, reactive nodes. It provides a structured
way to start, pause, end and reset nodes depending on what other nodes observe, which makes
sequencing, error handling and reactivity part of the structure instead of the control flow of
a script.

## The Problem

Behaviour written as a flat script faces several challenges:

- **Complex Sequencing**: Coordinating many steps that have to run one after another, or at the
  same time, becomes hard to manage as the number of steps increases.
- **Error Handling**: Every step can fail, and handling each contingency in a flat script
  often leads to "spaghetti code."
- **Reactivity**: Steps often have to react to observations, such as "keep going until a
  condition holds" or "stop as soon as something happens."

## How Statecharts Solve It

A statechart is a graph of **nodes**. Every node runs its own small state machine, and
the edges of the graph are the **conditions** under which one node's state machine reacts to
the state of other nodes. All nodes are updated together once per **tick**.

### Node types

- **Node** (`StatechartNode`): observes something and may act while it runs. A monitor, for
  example a counter waiting for a number of ticks, is a plain `StatechartNode`; there is no
  monitor class (see [Who ends a node](#who-ends-a-node)). Packages built on cramph add their
  own kinds of nodes, for example giskardpy's motion tasks.
- **CompositeNode**: A node that contains other nodes and wires their conditions. Composite
  nodes encapsulate reusable, parameterized patterns, such as [the templates](#templates) that
  run steps in order or retry a failed step.
- **Terminal node**: A node that ends the whole statechart. **EndStatechart** ends it
  successfully once it runs and observes True, **CancelStatechart** ends it by raising its
  exception at the end of the tick it starts in.

Every node carries two pieces of state:

- a **life cycle state**, which says where the node is in its own execution, and
- an **observation**, which says whether what the node observes is currently True, False or Unknown.

## Life cycle state

A node's life cycle has six states:

| Life cycle state | Meaning                                                  |
|------------------|----------------------------------------------------------|
| NOT_STARTED      | the node has not started yet, or was reset               |
| RUNNING          | the node is active                                       |
| PAUSED           | the node was running and is suspended until it resumes   |
| SUCCEEDED        | the node ended successfully                              |
| FAILED           | the node ended because it could not continue             |
| INTERRUPTED      | the node was ended from outside                          |

Only RUNNING is active: its observation is recomputed and its `on_tick` callback is
called. SUCCEEDED, FAILED and INTERRUPTED are **final states**,
and together they are the node's **outcome**. A node only leaves a final state when it is
reset.

## Observation state

The observation is a trinary value: **True**, **False** or **Unknown**. It states, for
example, whether a node has reached its goal or whether a monitor's condition holds.
Unknown is needed because a node often cannot give an answer, for example before it has
ever run.

Only a running node observes. The observation is recomputed every tick and may
change in both directions:

| Life cycle state                  | Observation                                              |
|-----------------------------------|----------------------------------------------------------|
| NOT_STARTED                       | Unknown                                                  |
| RUNNING                           | recomputed every tick                           |
| PAUSED                            | frozen at its last value, because the node resumes later |
| SUCCEEDED, FAILED, INTERRUPTED    | Unknown, because the node never observes again           |

The table describes a node that was already in that state when the tick started. A
node that changes state during a tick follows the state it started the control
cycle in until the next one:

- A node that pauses during a tick is still recomputed for the rest of it.
- A node that ends or is reset during a tick keeps the observation it stopped on.

A node's observation expression may read `observation_variable`, `last_observation`,
`life_cycle_variable` and every [predicate](#reading-other-nodes-in-conditions) of other
nodes, and combines them with `trinary_logic_and`, `trinary_logic_or` and `trinary_logic_not`.
An observation that chooses between cases uses `trinary_if_cases`, which selects a case only
while its guard is True.

## Life cycle transitions

```{mermaid}
flowchart LR
    entry(( )) --> NS([NOT_STARTED])
    NS -- start --> R
    NS -- "start while pause is True" --> P
    subgraph active ["active"]
        direction TB
        R([RUNNING]) -- "pause is True" --> P([PAUSED])
        P -- "pause is False" --> R
    end
    subgraph ended ["final, left only by reset"]
        direction TB
        S([SUCCEEDED])
        F([FAILED])
        I([INTERRUPTED])
    end
    active -- success --> S
    active -- fail --> F
    active -- interrupt --> I
    ended -- reset --> NS
    active -- reset --> NS

    classDef notStarted fill:#9CA3AF,stroke:#6B7280,color:#111111
    classDef running fill:#3B82F6,stroke:#1D4ED8,color:#FFFFFF
    classDef paused fill:#EAB308,stroke:#A16207,color:#111111
    classDef succeeded fill:#28A745,stroke:#15803D,color:#FFFFFF
    classDef failed fill:#EF4444,stroke:#B91C1C,color:#FFFFFF
    classDef interrupted fill:#F97316,stroke:#C2410C,color:#111111
    class NS notStarted
    class R running
    class P paused
    class S succeeded
    class F failed
    class I interrupted
```

Each transition is driven by one condition of the node. Conditions are binary: a transition
happens when its condition is **True**, and a paused node resumes as soon as its pause
condition is False again.

| Transition | Condition attribute   | Default | From                          | To          |
|------------|-----------------------|---------|-------------------------------|-------------|
| start      | `start_condition`     | True    | NOT_STARTED                   | RUNNING, or PAUSED while the pause condition is True |
| pause      | `pause_condition`     | False   | RUNNING (True), PAUSED (False) | PAUSED, RUNNING |
| success    | `success_condition`   | False   | RUNNING, PAUSED               | SUCCEEDED   |
| fail       | `fail_condition`      | False   | RUNNING, PAUSED               | FAILED      |
| interrupt  | `interrupt_condition` | False   | RUNNING, PAUSED               | INTERRUPTED |
| reset      | `reset_condition`     | False   | any state                     | NOT_STARTED |

With the defaults a node starts right away and runs until the statechart ends. A node whose
pause condition is already True when it starts goes straight to PAUSED, so it never runs
before its pause condition lets it.

The table lists the conditions written on a node. For succeeding and failing, a node class can
bring a condition of its own on top, its *inherent* condition, for example to succeed once the
node observes True (see [Who ends a node](#who-ends-a-node)). A node succeeds or fails once
either the written or the inherent condition holds; "success condition" and "fail condition"
below mean that combination.

**The condition that ends a node decides its outcome.** What the node observes at that moment
has a say in it only where one of these conditions reads the observation:

- **SUCCEEDED**: the node's success condition held.
- **FAILED**: the node's fail condition held: it cannot continue.
- **INTERRUPTED**: the node's interrupt condition held, or one of its ancestors ended. Neither
  is a judgement of the node itself.

### When several conditions hold at once

A node takes at most one transition triggered by its own conditions per tick.
Transitions its parent forces on it always happen: a node is reset while its parent has not
started, interrupted once its parent has ended and paused while its parent is paused, and it
only starts or unpauses while its parent is running. If several transitions are possible at the
same time, the first matching one in this order wins:

1. the node's own reset condition, or its parent has not started
2. the node's own success condition
3. the node's own fail condition
4. the node's own interrupt condition, or its parent has ended
5. the node's own pause condition, or its parent is paused
6. the node's own start condition, while its parent is running; the node starts paused
   if its own pause condition holds as well

The ladder a RUNNING node goes through in every pass of a tick (see
[One tick](#one-tick)):

```{mermaid}
flowchart TD
    A{"own reset is True, or<br/>the parent has not started?"}
    A -- yes --> NS([NOT_STARTED])
    A -- no --> B{"own success<br/>is True?"}
    B -- yes --> S([SUCCEEDED])
    B -- no --> C{"own fail<br/>is True?"}
    C -- yes --> F([FAILED])
    C -- no --> D{"own interrupt is True, or<br/>the parent has ended?"}
    D -- yes --> I([INTERRUPTED])
    D -- no --> E{"own pause is True, or<br/>the parent is paused?"}
    E -- yes --> P([PAUSED])
    E -- no --> R([RUNNING])

    classDef notStarted fill:#9CA3AF,stroke:#6B7280,color:#111111
    classDef running fill:#3B82F6,stroke:#1D4ED8,color:#FFFFFF
    classDef paused fill:#EAB308,stroke:#A16207,color:#111111
    classDef succeeded fill:#28A745,stroke:#15803D,color:#FFFFFF
    classDef failed fill:#EF4444,stroke:#B91C1C,color:#FFFFFF
    classDef interrupted fill:#F97316,stroke:#C2410C,color:#111111
    class NS notStarted
    class R running
    class P paused
    class S succeeded
    class F failed
    class I interrupted
```

## Reading other nodes in conditions

Conditions are symbolic expressions over the state of other nodes, combined with
`logic_and`, `logic_or` and `logic_not`. Since an observation may be Unknown, a condition
cannot read `observation_variable` or `last_observation` directly
(`UnsupportedConditionVariableError`). Instead, it reads **predicates**, which map a node's
observation or life cycle state to True or False.

- **Observation predicates** ask what a node observes:

  | Predicate            | True while                                                  |
  |----------------------|-------------------------------------------------------------|
  | `observes_true`      | the node observes True                                      |
  | `observes_false`     | the node observes False                                     |
  | `last_observed_true` | the observation the node took most recently is True         |

  A node observing Unknown makes all three False, including a node that has not observed
  anything yet. `observes_true` and `observes_false` turn False on the tick after
  the node ended. `last_observed_true` keeps the value the node observed when it ended,
  however it ended, until the tick after a reset. Read it to ask what a node saw, for example whether a monitor that
  ended itself had fired. It says nothing about how the node ended: a node interrupted while
  observing True still answers True, so read a life cycle predicate to learn its outcome.

  `logic_not(monitor.observes_true)` is True while the monitor observes False *or* Unknown,
  whereas `monitor.observes_false` is True only while it observes False.
- **Life cycle predicates** such as `node.is_succeeded` answer questions about the life cycle
  state of the node:

  | Predicate            | NOT_STARTED | RUNNING | PAUSED | SUCCEEDED | FAILED | INTERRUPTED |
  |----------------------|:-----------:|:-------:|:------:|:---------:|:------:|:-----------:|
  | `is_not_started`     | True        | False   | False  | False     | False  | False       |
  | `is_running`         | False       | True    | False  | False     | False  | False       |
  | `is_paused`          | False       | False   | True   | False     | False  | False       |
  | `is_terminated`      | False       | False   | False  | True      | True   | True        |
  | `is_succeeded`       | False       | False   | False  | True      | False  | False       |
  | `is_failed`          | False       | False   | False  | False     | True   | False       |
  | `is_interrupted`     | False       | False   | False  | False     | False  | True        |

  `logic_not(node.is_succeeded)` is also True before the node has ended. To wait for a node
  to end any way but by succeeding, read `node.is_failed_or_interrupted`, a shorthand for
  `logic_or(node.is_failed, node.is_interrupted)`.

An observation may change in both directions, while an outcome stays fixed until a reset. A
condition that has to keep its answer after the node it reads has ended must therefore read
`last_observed_true`, or the outcome through a life cycle predicate, rather than
`observes_true`:

```{mermaid}
flowchart LR
    c1["RUNNING<br/>observes False<br/><b>last_observed_true: False</b>"]
    c2["RUNNING<br/>observes True<br/><b>last_observed_true: True</b>"]
    c3["RUNNING<br/>observes False<br/><b>last_observed_true: False</b>"]
    c4["RUNNING<br/>observes True<br/><b>last_observed_true: True</b>"]
    c5["SUCCEEDED<br/>observes Unknown<br/><b>last_observed_true: True</b>"]
    c6["SUCCEEDED<br/>observes Unknown<br/><b>last_observed_true: True</b>"]
    c1 --> c2 --> c3 --> c4 -- "success condition is True" --> c5 --> c6

    classDef running fill:#3B82F6,stroke:#1D4ED8,color:#FFFFFF
    classDef succeeded fill:#28A745,stroke:#15803D,color:#FFFFFF
    class c1,c2,c3,c4 running
    class c5,c6 succeeded
```

Conditions are checked when they are set and when the statechart is compiled:

- A condition may read its own node, a sibling (a node with the same parent) or a direct
  child; anything further away raises `ConditionScopeError`.
- A start condition may not read its own node.
- No condition may read an EndStatechart or CancelStatechart node, because nothing happens after one
  of them.
- Only predicates of nodes may appear in a condition, combined with `logic_and`, `logic_or`
  and `logic_not`; anything else, such as the trinary operators or the constant Unknown,
  raises `CannotConvertToStringError`.

## One tick

A tick settles the whole statechart. It calls `on_tick`
once for every node that was running when the tick started, then repeats one
**pass** over all nodes until no life cycle state, observation or last observation changes
any more:

```{mermaid}
sequenceDiagram
    participant C as Executor
    participant T as on_tick
    participant P as Pass
    participant L as Life cycle callbacks
    C->>T: once per node running at the start of the tick
    T->>P: repeat until nothing changes
    Note over P: every node observes, reading the states of the previous pass,<br/>then takes over its last observation,<br/>then takes its next transition, reading the observations of this pass<br/>and the life cycle state its parent reaches in this pass.
    P->>L: once, in the order the changes happened
    Note over L: on_start, on_pause, on_unpause, on_end and on_reset.
    L->>C: done
    Note over C: the tick is recorded in the history,<br/>then a CancelStatechart that started raises its exception,<br/>and an EndStatechart observing True ends the statechart.
```

Every pass reads the states the previous pass left, so how deeply nodes are nested does not
change when they react to each other: a node waiting for another node's outcome, for example
with `start_condition = previous.is_succeeded`, starts on the tick in which that
outcome is reached, even if `previous` is a template several levels deep.

A few rules keep a tick predictable:

- A node started during a tick first observes on the next one. A node that was
  paused when the tick started keeps its observation.
- A node takes at most one transition triggered by its own conditions per tick, so it
  never ends, resets and starts again within one. Two nodes that each pause while the other
  runs therefore take turns once per tick instead of looping.
- Life cycle callbacks run once after the passes, so what they change, for example a value
  an observation reads, is seen by observations from the next tick on. A node its parents
  force through several states within one tick gets each matching callback once, in
  order, for example `on_pause`, `on_end` and `on_reset`. A node that starts paused gets
  `on_start` and then `on_pause`.
- A `CancelStatechart` that starts during a tick raises its exception only after all
  life cycle callbacks of that tick ran and the tick was recorded, even
  if it was interrupted again within the same tick.
- Observations that read each other can contradict each other, for example two nodes each
  observing True while the other does not. Such a tick never settles: a pass
  brings the statechart back to a state it already had in this tick, and the tick
  raises `TickDoesNotSettleError` naming the nodes still changing.
- A tick may take a bounded number of passes, so it always fits into the control
  loop: `Statechart.pass_limit`, plus
  `Statechart.passes_per_nesting_level` for every nesting level of the
  statechart, because an outcome moves up one level per pass. A tick that needs more passes
  raises `TickDoesNotSettleError` as well.

## Who ends a node

> A node decides when it cannot continue. Its owner decides when it is done.

Failing has no side effect, so a node may declare it itself through its fail condition.
Succeeding can have one: a node that is ended stops acting, and what it had just achieved can
then be undone, for example by another node that is still running. That is why such a node
never ends itself on reaching its goal; whoever runs it, its **owner**, writes its success and
interrupt conditions.

Every node class therefore says how it succeeds, by inheriting one of two classes. They
implement the abstract `inherent_success_condition`; constructing a node of a class that
leaves it abstract raises a `TypeError`.

- **`EndedByOwner`**: the node's observation says whether it has reached its goal, but
  only its owner ends it. Monitors (`CountSeconds`, `CountTicks`, `Print`, …), `Parallel`
  and the monitored composite nodes are examples.
- **`SucceedsOnObservingTrue`**: ending the node undoes nothing it did, so it ends itself: it
  succeeds once it observes True. Examples are `Attempt`, the ordering templates,
  `FunctionCall`, `MoveBranch` and `CompositeNodeChoosingItsChild`.

Independently, a node class can inherit **`FailsOnObservingFalse`**: observing False
means it can no longer reach its goal, so it fails once it observes False. `Attempt`,
the ordering templates and `FunctionCall` do.

What a class brings is its *inherent* success and fail condition
(`inherent_success_condition`, `inherent_fail_condition`). The conditions written on a node
(`success_condition`, `fail_condition`) stay as they were written; a node succeeds or fails
once either the written or the inherent condition holds.

A node class with another reason to fail on its own overrides `inherent_fail_condition`
instead of writing its fail condition: `Parallel` fails once too few of its nodes are left to
reach `minimum_success`, and every monitored composite statechart node fails once its
monitored node ended without succeeding.

`Attempt` is the bridge between the two: it runs a node its owner ends and turns it into a node
that ends itself.

```{mermaid}
flowchart LR
    subgraph owner ["EndedByOwner"]
        direction TB
        monitor(["monitors,<br/>counters"])
        parallel(["Parallel"])
        monitored(["PausedWhileTrue, PausedUntilTrue,<br/>StoppedWhenTrue, CancelledWhenTrue"])
    end
    subgraph itself ["SucceedsOnObservingTrue"]
        direction TB
        attempt(["Attempt"])
        ordering(["Sequence, TryInOrder,<br/>TryAll, RepeatUntil"])
        steps(["FunctionCall, MoveBranch,<br/>CompositeNodeChoosingItsChild"])
    end
    owner -- "wrapped in an Attempt" --> attempt
    itself -- "usable as a step of" --> ordering
```

The ordering templates (`Sequence`, `TryInOrder`, `TryAll`, `RepeatUntil`) decide when their
children start and end, so they check every child they are given:

- A child whose owner decides its success is wrapped in an `Attempt` without failure monitors
  automatically. Such an attempt fails only if the child fails on its own, as `Parallel` and
  the monitored composite statechart nodes can.
- `TryInOrder` (for every alternative but the last) and `RepeatUntil` only move on once an
  attempt failed. They reject an `Attempt` that cannot fail, written by hand or created
  automatically, with an `AttemptCannotFailError` at compile time. An attempt cannot fail if it
  has no failure monitors and its task has neither a written nor an inherent fail
  condition.
- A child whose start, pause, success, interrupt or reset condition was already set is
  rejected with a `ChildTransitionAlreadyWiredError`, because those are the template's to
  decide. The fail condition is exempt, since a node declares its own failure.

## Templates

The templates in `cramph.composites` are composite nodes that wire
their children for common patterns. In the diagrams below, an arrow from node A to node B
labelled `transition: expression` means that B's condition for that transition reads A.

### Attempt

Runs a `task` together with a list of `failure_monitors`, and ends as soon as either the task
reaches its goal or a monitor gives up on it.

- It observes **True** once the task's `last_observed_true` is True while the task has not
  ended without succeeding, and then succeeds.
- It observes **False** once any failure monitor's `last_observed_true` is True, and then fails.
  Reaching the goal wins if both happen on the same tick.
- It observes **False** as well once the task ended without succeeding, which is the task
  having concluded on its own; an attempt still waiting for it would never end.
- Otherwise it observes Unknown and keeps going.

The task is never ended by the attempt directly. It keeps running until the attempt
itself ends and interrupts it. The attempt fails on the tick a failure monitor fires,
which interrupts the monitor and keeps what it observed as its last observation, so
`attempt.failure_reasons` can list the monitors that caused a failure after the fact. An empty
`failure_monitors` list states that the attempt cannot fail.

```{mermaid}
flowchart LR
    subgraph attempt ["Attempt"]
        direction TB
        task(["task"])
        m1(["failure monitor 1"])
        m2(["failure monitor 2"])
    end
    obs{"Attempt observes"}
    task -- "last_observed_true" --> obs
    m1 -- "last_observed_true" --> obs
    m2 -- "last_observed_true" --> obs
    obs -- "True: success" --> S([SUCCEEDED])
    obs -- "False: fail" --> F([FAILED])

    classDef succeeded fill:#28A745,stroke:#15803D,color:#FFFFFF
    classDef failed fill:#EF4444,stroke:#B91C1C,color:#FFFFFF
    class S succeeded
    class F failed
```

### Sequence

Runs its `nodes` one after another. Each step starts once the previous one has succeeded.

- It observes **True** once the last step succeeded.
- It observes **False** as soon as any step ended without succeeding.

```{mermaid}
flowchart LR
    subgraph sequence ["Sequence"]
        direction LR
        s1(["step 1"]) -- "start: is_succeeded" --> s2(["step 2"])
        s2 -- "start: is_succeeded" --> s3(["step 3"])
    end
    s3 -. "succeeded" .-> S([Sequence SUCCEEDED])
    sequence -. "any step ended without succeeding" .-> F([Sequence FAILED])

    classDef succeeded fill:#28A745,stroke:#15803D,color:#FFFFFF
    classDef failed fill:#EF4444,stroke:#B91C1C,color:#FFFFFF
    class S succeeded
    class F failed
```

### Parallel

Runs all of its `nodes` at the same time and observes **True** while at least
`minimum_success` of them (all of them by default) have `last_observed_true` True on the same
tick. A node that ended without succeeding stops counting, because the reading it
kept says where it was cut off rather than where it is, and `Parallel` fails once too few
nodes are left to reach `minimum_success` at all.

`Parallel` never ends any of its nodes: ending a node that reached its goal would let a node
that is still running undo what it achieved. For the same reason it is a
node whose owner decides its success and never succeeds on its own; it only fails on its own,
once too few nodes are left. Put it into an `Attempt`, or hand it to an
ordering template, which does that for you, to get a step that finishes once all nodes are at
their goals together.

```{mermaid}
flowchart LR
    subgraph parallel ["Parallel"]
        direction TB
        n1(["node 1"])
        n2(["node 2"])
        n3(["node 3"])
    end
    count{"number of nodes with<br/>last_observed_true ≥<br/>minimum_success?"}
    n1 --> count
    n2 --> count
    n3 --> count
    count -- yes --> T["Parallel observes True"]
    count -- no --> Fa["Parallel observes False"]
```

### TryInOrder

Tries its `nodes` one after another and stops at the first one that succeeds. Each
alternative starts once the previous one ended without succeeding.

- It observes **True** as soon as an alternative succeeded.
- It observes **False** once every alternative ended without succeeding.

Each alternative decides for itself when to give up, typically as an `Attempt` with failure
monitors. An attempt that cannot fail would keep the later alternatives from ever starting, so
it is rejected anywhere but last.

```{mermaid}
flowchart LR
    subgraph try_in_order ["TryInOrder"]
        direction LR
        a1(["alternative 1"]) -- "start: is_failed_or_interrupted" --> a2(["alternative 2"])
        a2 -- "start: is_failed_or_interrupted" --> a3(["alternative 3"])
    end
    try_in_order -. "any alternative succeeded" .-> S([TryInOrder SUCCEEDED])
    try_in_order -. "every alternative ended<br/>without succeeding" .-> F([TryInOrder FAILED])

    classDef succeeded fill:#28A745,stroke:#15803D,color:#FFFFFF
    classDef failed fill:#EF4444,stroke:#B91C1C,color:#FFFFFF
    class S succeeded
    class F failed
```

### TryAll

Runs all of its `nodes` at the same time and takes the first one that works.

- It observes **True** as soon as any alternative succeeded. `TryAll` then succeeds and
  interrupts the alternatives that are still running.
- It observes **False** once every alternative ended without succeeding.

### RepeatUntil

`RepeatUntil` runs a `task` and resets it whenever it fails, until either the task succeeds or
`stop_retry_monitor` calls the retrying off.

- The task is wrapped in an attempt if it needs one. Its failure monitors decide what counts
  as a failed try. An attempt that cannot fail would never be retried, so it is rejected.
- A failed try is reset on the next tick, as long as the stop monitor has not
  observed True. Resetting a goal resets everything below it, so a composite task starts over as a
  whole.
- Once the stop monitor's `last_observed_true` is True, the attempt is interrupted and not
  started again. A stop monitor that has not observed anything yet does not hold the attempt
  back.
- It observes **True** once the attempt succeeded, and **False** once the stop monitor
  observed True.
- If an `exception` is given, a `CancelStatechart` raises it as soon as the stop monitor's
  `last_observed_true` is True.

```{mermaid}
flowchart LR
    subgraph repeat ["RepeatUntil"]
        direction LR
        stop(["stop_retry_monitor"])
        attempt(["attempt"])
        cancel(["CancelStatechart<br/>(only with an exception)"])
    end
    stop -- "start: not last_observed_true<br/>interrupt: last_observed_true" --> attempt
    attempt -- "reset: is_failed and not<br/>last_observed_true of the stop monitor" --> attempt
    stop -- "start: last_observed_true" --> cancel
```

### Monitored composite statechart nodes

These run a `monitored_node` next to a `monitor`, and let the monitor control the
monitored node's life cycle. Their owner decides their success, and their observation is the
monitored node's `last_observation`. Once the monitored node ended without succeeding, it can no
longer arrive, so the template fails.

| Template            | Effect on the monitored node                                            |
|---------------------|-------------------------------------------------------------------------|
| `PausedWhileTrue`   | paused while the monitor observes True                                  |
| `PausedUntilTrue`   | paused while the monitor does not observe True, Unknown included        |
| `StoppedWhenTrue`   | interrupted once the monitor's `last_observed_true` is True             |
| `CancelledWhenTrue` | like `StoppedWhenTrue`, and a `CancelStatechart` ends the whole statechart      |

```{mermaid}
flowchart LR
    monitor(["monitor"])
    node(["monitored node"])
    monitor -- "PausedWhileTrue → pause: observes_true<br/>PausedUntilTrue → pause: not observes_true<br/>StoppedWhenTrue → interrupt: last_observed_true" --> node
```

`StoppedWhenTrue` observes True while the monitored node observes True or once it succeeded,
False once the monitor stopped it, and Unknown otherwise. Stopping the monitored node
interrupts it, so the template fails like any monitored composite statechart node whose
monitored node ended without succeeding.

## Ending the statechart

The statechart ends once an `EndStatechart` node is running and observes True, which it does
as soon as it runs. A `CancelStatechart` node ends the statechart by raising its exception at
the end of the tick it starts in.

An `EndStatechart` must be added at the top level of the statechart; adding it to a composite
node raises `EndInCompositeNodeError`. A `CancelStatechart` may be placed anywhere.

Both are usually created with factory methods that set their start condition:

| Factory                           | Starts once                                                          |
|-----------------------------------|----------------------------------------------------------------------|
| `when_true(node)`                 | `node` observes True, or `node.is_succeeded` is True                 |
| `when_failed(node)`               | `node.is_failed` is True                                             |
| `when_all_true(nodes)`            | every node observes True or has succeeded                            |
| `when_any_true(nodes)`            | any node observes True or has succeeded                              |
| `EndStatechart.when_false(node)`  | `node` currently observes False; this does not look at its outcome   |

## Example

A plan that first tries a slow approach and falls back to a fast one once the slow one takes
too long. Counters stand in for real work:

```python
from cramph.composites import Attempt, Sequence, TryInOrder
from cramph.context import StatechartContext
from cramph.executor import StatechartExecutor
from cramph.monitors import CountTicks
from cramph.node import EndStatechart
from cramph.statechart import Statechart
from semantic_digital_twin.world import World

executor = StatechartExecutor(context=StatechartContext(world=World()))
statechart = Statechart(context=executor.context)

slow_approach = Attempt(
    name="slow approach",
    task=CountTicks(name="slow", ticks=100),
    failure_monitors=[CountTicks(name="timeout", ticks=10)],
)
fast_approach = CountTicks(name="fast approach", ticks=5)

plan = Sequence(
    nodes=[
        TryInOrder(nodes=[slow_approach, fast_approach]),
        CountTicks(name="retreat", ticks=5),
    ]
)
statechart.add_node(plan)
statechart.add_node(EndStatechart.when_true(plan))
```

After running it:

- `slow_approach` is FAILED, and `slow_approach.failure_reasons` names the `timeout` monitor.
- `fast_approach` and `retreat` were wrapped in attempts, which both SUCCEEDED.
- `plan` is SUCCEEDED, and the counters themselves are INTERRUPTED, because their attempts
  ended them.

[Running a Statechart](examples/running_a_statechart.md) executes this plan and plots it.

## Benefits

- **Modularity**: Individual steps and checks are self-contained nodes that can be reused.
- **Clarity**: The statechart structure provides a clear visual and logical representation of
  the behaviour.
- **Robustness**: Error handling and reactivity are built directly into the structure through
  monitors and transitions, and every node that ended carries an outcome saying how.
