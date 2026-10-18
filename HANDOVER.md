# Handover: RoboCasa experiments with the PR2 (written 2026-10-18)

Read this first. It replaces the note of 2026-10-16 and keeps its open items that are still
open.

- **Session transcripts:**
  - The session that did the part decomposition work below, for Abdelrhman Bassiouny:
    https://claude.ai/code/session_01GA355bqZFZykHV5A8UKjob
  - Tom's session before it: https://claude.ai/code/session_01WEy5o24LzuvULht7bb5n4Z
- **Dashboard** of the handle segmentation benchmark, the splitting sweep and the
  decomposition of the RoboCasa objects, with renders of every object:
  https://claude.ai/artifact/TAdmdSgXXwPHMa81wnNhtL. It was published from the local machine of
  the last session. The renders and numbers come from `/root/work/part_decomposition/report`
  and `/root/work/part_split_benchmark/report`.

## Where things are
- Host `neem-4.informatik.uni-bremen.de`, container `tom-cram-robocasa-experiments`.
- **Repo:** `/raid/users/tom_sch/repos/cram-robocasa-experiments` on the host, which is
  `/opt/cram` in the container. Branch `robocasa-experiments`, at the commit that adds this
  note.
  - **Pushed to** Abdelrhman's fork
    `git@github.com:AbdelrhmanBassiouny/cognitive_robot_abstract_machine.git`, branch
    `robocasa-experiments`.
  - **Not pushed to** Tom's fork `tomsch420/...`. Its `robocasa-experiments` lacks the
    commits from 4a0ed61a3a on. The container's branch has them all, so a push from a
    bundle of it brings Tom's fork up to date.
- **Worktrees:**
  - `.pr_worktree`: branch `pr2-mujoco-physics`, which is PR #752.
  - `.collision_wt`: a scratch copy of cram2 main used for PR #756. It can be deleted.
- **Persistent data:** `/root/work` is the Docker volume `cram-robocasa-experiments-work`
  (`/raid/docker/volumes/cram-robocasa-experiments-work/_data` on the host). It survives the
  container.
- **Environment:** activate it with
  `source /opt/ros/cram-env/bin/activate; source /opt/ros/overlay_ws/install/setup.bash; export MUJOCO_GL=egl; ulimit -v 120000000`
  Env scripts per worktree are in `/root/scripts/{main,pr,collision}_env.sh`.
- **Import order:** import a `semantic_digital_twin.adapters.robocasa_dataset` module *before*
  `robocasa`. The loader spoofs the MuJoCo and numpy versions; otherwise RoboCasa's version
  assertion fails.
- **Session scripts** are committed under `experiments/scripts/robocasa_session/`. They are
  unreviewed and do not follow AGENTS.md.
  - `part_decomposition/`: locating, splitting and storing the RoboCasa objects. They run
    from `/root/work/part_decomposition/code`.
  - `part_split_benchmark/`: the splitting sweep. It runs from
    `/root/work/part_split_benchmark/code`.
  - The rest are the PR2 probe and recording scripts, also in the container's
    `/root/scripts`.

## The part-finding server (VLM)
- Container `part-finding-robocasa`, at `http://172.17.0.7:8790`, with the routes `/parts`
  and `/status`. It runs Qwen3-VL-8B and SAM 2.1 on an 11-view camera ring.
- It runs the code of this branch: the repo is mounted read-only at `/opt/cram`. Restart
  the container to serve code changes.
- It was started with
  `docker run -d --name part-finding-robocasa --restart unless-stopped --gpus all -v /raid/users/tom_sch/repos/cram-robocasa-experiments:/opt/cram:ro -v part-finding-cache:/root/.cache cram-part-finding:pr728-review6 semantic-digital-twin-part-finding-server`.
- Answers are cached in the volume `part-finding-cache`.
- The older server container `part-finding` is stopped, not removed. It ran older code that
  rejected `Pan`, `Kettle` and `Cup` queries; it is kept to roll back to.

## Rules
Rules both users insist on. The Git and commit rules depend on whose session it is.
- **Git and GitHub:**
  - neem-4 has *no GitHub credentials*. Move commits to the local machine with a git bundle,
    fetch it into `refs/remotes/bundle/...` there, and push that ref. Don't touch the local
    working tree.
  - Push only to the fork of whoever runs the session, never to upstream cram2 (remote
    `cram2`). Read the full `git remote -v` before pushing.
- **Commits:**
  - Commit as whoever runs the session: Tom Schierenbeck <tom_sch@uni-bremen.de>, or
    AbdelrhmanBassiouny <abdelrhman_bassuny@hotmail.com>.
  - No AI co-author trailer and never name the model; "Made with AI assistance" is fine.
- **PRs:** drafts only. Bug PRs carry the `bug` label, are focused and based on main.
  Put the session link in the description. Never watch or babysit PRs.
- **Tests:**
  - pytest, TDD (failing test first). Never change a test to make it pass without asking.
  - Pass `--orm-build never`, cap memory with `ulimit -v 120000000` (32 GB made MuJoCo hang),
    run one directory at a time, and never run tests concurrently with video recordings.
- **The ORM:**
  - `semantic_digital_twin/orm/ormatic_interface.py` is generated and untracked.
  - Regenerate it with `scripts/regenerate_all_orm.py` after changing a mapped dataclass.
  - It needs `ulimit -v 64000000` or more. Under 32 GB it fails.
- **Before committing:** run `scripts/format_docstrings.py` on modified files (in the container).
- **Generated noise:** test runs rewrite
  `test/krrood_test/test_eql/test_verbalization/verbalization_results.py`. Restore it with
  `git checkout`.
- Leave `test.srdf` and `.collision_wt` alone.
- Follow AGENTS.md: dataclasses, no try/except, no module constants, no ClassVar,
  RST docstrings, ask before new dependencies.
- **Waits:** keep them short and bounded and check logs. Both users dislike long blind
  waits.

## State of the work

### Parts of RoboCasa objects and appliances (all on `robocasa-experiments`)
- **4a0ed61a3a:** `Knob`, `Button`, `Lever` and `Faucet` annotations, attached to the RoboCasa
  appliances by body name.
- **460d9c8844:**
  - **Default decomposer:** `AnnotationPartFinder` decomposes split pieces with V-HACD, at
    most 32 hulls per piece. The splitting sweep chose it: about 7 s per object, 3.6 mm p95
    from the surface. The COACD default took minutes and gave thousands of hulls.
  - **Handle fields:** `Pan`, `Kettle` and `Cup` have an optional handle.
  - **Loader fixes:** the loader hides RoboCasa's transparent region geoms and names
    unnamed bodies. The `load_object(PAN)` crash is fixed.
- **Every RoboCasa object held by a handle is decomposed.**
  - **Coverage:** 18 mugs, 15 pots, 23 pans and 42 kettles, from the objaverse and
    lightwheel groups. The 4 cups were correctly left without a handle.
  - **Time per object:** median 3–14 s.
  - **Fit, p95 distance between the visual surface and the hulls:**
    - Mugs, pots and pans: 2–9 mm.
    - Kettles: 19 mm outside the surface. Their bodies are large and round, and 32 hulls
      cut corners on them.
- **f20d259386: stored decompositions are reused on load.**
  - **Store:** `part_finding/decomposed_objects.py`.
    - `DecomposedObject` is the decomposed world, kept through the ORM with its
      annotations.
    - `ShapeFingerprint` is a hash of the triangles plus the moments of the vertices
      normalised to the bounding box. It matches copies stretched along each axis;
      RoboCasa scales objects per category in tasks.
    - `DecomposedObjectStore` is a SQLAlchemy session plus a mesh directory.
  - **Step:** `UseDecomposedObjects` gives each object of a stored shape the stored parts,
    stretched to fit. It keeps the object's own root body and any liquid cylinder.
  - **Loader:** `RoboCasaDatasetLoader.preprocessing` is a pipeline applied after every
    `load_*`.
  - **Task annotations:** a task object is now annotated at the body holding its shape. A
    pan's `pan_main` shows only the liquid.
  - **Check on real tasks:** 19 of 19 mugs, kettles, pans and pots in 13 task loads got
    their parts. The first database query in a process takes about 14 s, which is
    SQLAlchemy configuring its mappers. After that the step adds 0.3–2.5 s per task.
- **ebe9e6a36b: at most two handles on an object.**
  - **Rule:** `IsPartWholeRelationship.maximum_parts`, and `HasHandles.handles` holds 2 at
    most.
  - **Enforcement:** `add()` raises `TooManyParts`.
  - **Finder:** `AnnotationPartFinder` keeps the parts the VLM is most sure of.
  - **Why:** before, the finder made every separate piece the VLM marked into its own
    handle, up to 17 on one pot.

### Using the store
The store is in `/root/work/part_decomposition`: `decomposed_objects.sqlite` and
`decomposed_meshes/`, about 450 MB, with 98 objects.
- The database keeps a mesh's absolute file name, so the two must stay together at this
  path.
- To rebuild it, run `code/store_all.py`. It takes about 20 minutes and re-splits each
  object from the VLM answers in `located/`, with no VLM call.

```python
from pathlib import Path
from sqlalchemy.orm import Session
from krrood.ormatic.utils import create_engine
from semantic_digital_twin.adapters.robocasa_dataset.loader import RoboCasaDatasetLoader
from semantic_digital_twin.part_finding.decomposed_objects import DecomposedObjectStore
from semantic_digital_twin.pipeline.part_finding import UseDecomposedObjects
from semantic_digital_twin.pipeline.pipeline import Pipeline

directory = Path("/root/work/part_decomposition")
store = DecomposedObjectStore(
    session=Session(create_engine(f"sqlite:///{directory / 'decomposed_objects.sqlite'}")),
    mesh_directory=directory / "decomposed_meshes",
)
loader = RoboCasaDatasetLoader(preprocessing=Pipeline(steps=[UseDecomposedObjects(store=store)]))
```

To decompose a new object, record its shape before splitting it and keep it afterwards:
1. `fingerprint = ShapeFingerprint.of_body(whole.root)`
2. `AnnotationPartFinder().find_parts(whole)`
3. `store.add(DecomposedObject.of(whole, fingerprint))`

### The PR2 task (unchanged since 2026-10-16)
- **What works:** PickPlaceCounterToSink with the PR2 under CRAM plans, full MuJoCo physics,
  friction grasping, an omni base drive, and a graph of convex sets path to place into the
  basin.
- **Module:** `experiments/src/experiments/robocasa_task_execution/` (`counter_to_sink.py`,
  `placing_into_the_basin.py`).
- **Tests:** 9 counter_to_sink tests pass. `test_the_pr2_puts_the_object_into_the_sink`
  fails because the pick with collision avoidance on hits CandidateLimitReached.
- **Container-only change:** RoboCasa `counter.py` line 813 uses
  `list(dict.fromkeys(valid_geoms))` instead of `list(set(...))` to fix an ordering
  nondeterminism.
- **PR #752** (draft) holds the fixes that let the PR2 work with Giskard and MuJoCo.
- **PR #756** (draft, bug): `is_in_collision` uses `<` instead of `<=`. It is done; its PR
  progress note in CLAUDE.local.md was not written.

## Open items, roughly by priority
1. **Pots: two pieces of the same handle.**
   - In 5 of 15 pots (pot_1, 6, 7, 12, 14 in `stored.json`), the two most confident pieces
     lie on the same side, 0°–75° apart. The handle on the other side stays part of the
     pot's body.
   - `code/sides.py` measures it.
   - Proposed, awaiting the user's go: merge the pieces on each side into one handle,
     then keep at most one per side.
2. **Fixture door handles** (fridge, microwave, dishwasher, oven):
   - The VLM marks 1–12 faces or nothing on these CAD meshes, so the fixture run stopped
     after style 1.
   - RoboCasa names the handles' collision boxes (`*_door_handle_main`, `_1`, `_2`) inside
     the door body. Proposed: a part finder that splits by those names, with no VLM.
     Awaiting the user's decision.
3. **Kettles:** the hulls stick out 19 mm (p95). More hulls for kettles would fit them
   closer if their collisions matter.
4. **Store:**
   - The mesh paths are absolute, so the store can't be moved.
   - The first query costs about 14 s per process.
   - A decomposed object is replaced as a whole. An object that has some of its parts
     already is left as it is.
5. **Bugs from the parts survey, not looked at since:**
   - The fixed panel `stack_2_main_group_2_door_main` is annotated as a Door.
   - The fridge freezer drawer is not annotated.
   - `Cooktop` is not `HasDoors`, so the oven door of the range is not annotated.
6. **Small bug PR candidates on cram2 main** (one PR each, if the user asks):
   - `AllowCollisionForBodies` drops its bodies (`collision_rules.py`; `update` resets the set).
   - `MoveTCPWaypointsMotion` ignores `allow_gripper_collision` and `movement_type`
     (coraplex `motions/gripper.py`).
   - The MuJoCo `multiccd` option crashes on MuJoCo 3.11 (`mujoco_simulator.py`).
7. **The pick with collision avoidance on** still fails (CandidateLimitReached).
8. **Integrate the advanced grasp model from tomsch420 PR #32.** The patch is at
   `/raid/users/tom_sch/pr32_on_728_integration.patch` on the host.
9. **Undecided by the user:**
   - The RoboCasa ordering fix: carry it in `mujoco_compat` or in a RoboCasa fork?
   - Can `placement_pose` (used only in tests) be removed?
   - Should the base drift false success become its own PR? (Goals are bound to `robot.root`
     when the base is not full body controlled.)
10. **Smaller loose ends:** the costmap margin, the zero size array in placement_pose, and
    the PR2 base floor contact.
