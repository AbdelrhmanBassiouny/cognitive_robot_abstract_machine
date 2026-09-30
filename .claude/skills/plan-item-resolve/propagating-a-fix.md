# Carrying a resolved fix into what is stacked on the branch

A resolve ends with a push to one branch. Every pull request based on that
branch still has the state the fix replaced, and nothing carries it up on its
own: `/stacked-pr-maintenance` does, but it is whole-board and runs when it
runs. So a resolve that stops at its own push leaves its own descendants
stale, and the next person to touch one of them re-hits what was just fixed.

## When this applies

After the item's branch has been pushed, and only then — there is nothing to
carry before that. Skip it when no open pull request is based on this item's
branch; the pass below reports exactly that, so running it is the cheapest way
to find out.

## Carrying it

```bash
python3 -m basstler.maintenance board --write
python3 -m basstler.maintenance restack --stacked-on <this item's branch>
```

The second command plans only the branches stacked on the named one — directly
or through the branches between them — and puts each through the same steps a
whole-board pass uses, parent before child. It prints one line per branch:
`pushed` (it took the fix and was published), `up-to-date` (it already had it),
or `conflict`, plus the paths that collided.

Unlike a whole-board pass, a conflict here writes nothing to the descendant's
pull request: no label, no comment. The judgement is yours, because the fix
being carried is the one this session just made.

## The judgement a conflict asks for

This is a **parent to descendant** collision, and it has a correct answer: the
parent's side is the fix, and it belongs in the descendant. Resolve it in the
descendant's favour only where the descendant's own work genuinely supersedes
what the fix changed — never by dropping the fix to make the merge easy, and
never by weakening it on the parent.

That is not the judgement `/integration-conflict-triage` makes. It weighs
**sibling** collisions on an integration branch, where neither branch is wrong
and the fix belongs in whichever feature branch caused it. The vocabulary
carries over; the verdicts do not.

Resolve it on the descendant's branch, push, and re-run the command so what is
stacked above it takes the resolved result.

## When to hand it back instead

Stop and put it to the user when resolving would change what the descendant
does rather than mechanically adopting the fix — both sides changed the same
logic, and picking either loses behaviour. Say which branch, which paths, and
what each side wants; leave the descendant untouched rather than guessing.

Whatever is left uncarried goes in the resolve's own report, and on the
descendant's pull request only when its owner has to act on it.
