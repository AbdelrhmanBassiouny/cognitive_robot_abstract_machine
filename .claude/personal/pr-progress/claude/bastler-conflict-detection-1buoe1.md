# design-overlap: planning session

This branch is a **coordinating** branch, not an item branch. It carries no code
and will not get a pull request of its own. Re-cut from `main` on 2026-09-06
(it had descended from `integration`, which `check-setup.sh` refuses as a base).

## What this session did

- Diagnosed the duplication problem the user described: the pipeline has detection
  at both ends (`check_scope_overlap.py` at item creation, `integration.py build`
  at merge time) and nothing in the middle, where two branches defining the same
  abstraction in differently named files are invisible to both. Second half:
  `reconcile` is the only integration verdict with no machinery behind it.
- Got the design approved in plan mode, with three decisions settled by the user:
  scripted apply after a mandatory dry run; interactive CDN graph library;
  freshness tied to the dashboard publish rather than the unlanded refresh Action.
- Created the `design-overlap` plan: 5 items, 2 waves, 3 tracks, tracking issue
  #102 (reused rather than minted - seven workflow plans already share it).
- Published its dashboard and refreshed the master index (which was also stale by
  one other plan, `probabilistic-knowledge-perception`, now restored).
- Announced the plan on #102 with the collision hazards found by running the
  scope check on the plan's own creation.

## What's next

`definition-catalogue` is the only item ready to start; everything else depends on
it directly or transitively. Start it with
`/plan-item-kickoff design-overlap definition-catalogue`, from a branch cut off
`main`, not off this one.

Check #185's state first - it moves every `.claude/` Python module into `bastler`,
and every Python item in this plan lands in files it moves.

## Hazards recorded on the plan

- **#185** moves the files items 1, 2 and 4 create.
- **`templates/dashboard.html` has four open editors** (#218, #206, #157, #111),
  so `plan-graphs` should wait for as many as possible; #253 changes its edge data.
- **#282** already comments on branches an integration build leaves out; the
  post-review re-check in `skill-wiring` may belong there instead.

Dashboard: https://claude.ai/code/artifact/5c2274c2-ceed-40aa-ae9e-eaa0a77abb80
Index: https://claude.ai/code/artifact/094b785f-fe16-45d6-9ecf-5555d1aae487
