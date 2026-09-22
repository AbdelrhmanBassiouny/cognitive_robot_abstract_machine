# Reproducing the experiments

This branch holds the code behind the paper's experiments: a dual-arm robot ("Tracy":
two UR arms with Robotiq grippers and a table-mounted RGB-D camera) sorting the pieces of
a Montessori shape-sorting board, recording every run as an *episode*, and answering
questions about those episodes from working memory (during a run) and long-term memory
(afterwards, from the results database).

## Supplementary video

[supplementary_video.mp4](experiments/doc/video/supplementary_video.mp4)

The video (three minutes, 16 MB, subtitled) shows the plan of the paper's framework figure resolved by one backend
after another and carried out on the real robot, the action attribution and temporal
queries answered during two trials, the perturbed episodes, and long-term memory
answering the same query over the recorded corpus. It is the video submitted with the
paper.

There are three ways to reproduce the results, from least to most effort:

| | What you get | Needs |
|---|---|---|
| [A. Recompute the tables from the recorded corpus](#a-recompute-the-tables-from-the-recorded-corpus) | Every table and query card in the paper, for the simulated and the real corpus | The reproduction package, PostgreSQL. No robot, no ROS |
| [B. Re-run the experiments in simulation](#b-re-run-the-experiments-in-simulation) | New simulated episodes, the framework-figure plan carried out in MuJoCo, tables over your own corpus | ROS 2 workspace, MuJoCo |
| [C. Re-run the experiments on the real robot](#c-re-run-the-experiments-on-the-real-robot) | New real episodes | The robot, its camera, the board and pieces, the ROS 2 robot stack |

The paper's figures were produced with path A over the corpus recorded with paths B and C.

## Contents

- [Supplementary video](#supplementary-video)
- [Setup](#setup)
- [A. Recompute the tables from the recorded corpus](#a-recompute-the-tables-from-the-recorded-corpus)
- [B. Re-run the experiments in simulation](#b-re-run-the-experiments-in-simulation)
- [C. Re-run the experiments on the real robot](#c-re-run-the-experiments-on-the-real-robot)
- [Which real episodes the paper uses, and why](#which-real-episodes-the-paper-uses-and-why)
- [Where things are](#where-things-are)

## Setup

Tested on Ubuntu 24.04 with Python 3.12 and ROS 2 Jazzy.

```bash
# system packages
sudo apt install -y python3-virtualenv virtualenvwrapper graphviz graphviz-dev \
    postgresql postgresql-client

# a virtual environment that can see the ROS Python packages
source /usr/share/virtualenvwrapper/virtualenvwrapper.sh
mkvirtualenv cram-env --system-site-packages
workon cram-env

# every package of this repository, installed editable
curl -LsSf https://astral.sh/uv/install.sh | sh
uv sync --active

# the ORM interfaces are generated, not tracked: build them once after installing
python scripts/regenerate_all_orm.py
```

Paths B and C additionally need a ROS 2 Jazzy workspace with the robot description, the
gripper driver and the camera driver. The repository builds one for you:

```bash
sudo bash .github/docker/setup_ros_workspace.sh && source ~/.bashrc
```

The list of repositories it clones is in `.github/docker/setup_workspace.py`.

### Environment variables

| Variable | Meaning | Default |
|---|---|---|
| `MONTESSORI_SORTING_DATABASE_URI` | Results database episodes are recorded to and read from (any SQLAlchemy URI; PostgreSQL or SQLite) | `postgresql+psycopg://semantic_digital_twin:montessori@localhost:5432/montessori_sorting_results` |
| `EPISODE_ARTIFACTS_DIRECTORY` | Where each episode's transcript, joint trace, meshes and (real runs) camera bag are kept | `~/episode-artifacts` |

Every script also accepts `--database-uri`, which wins over the environment variable.

## A. Recompute the tables from the recorded corpus

### The reproduction package

Download and unpack the reproduction package:
**<https://osf.io/sc38m/?view_only=6d981619c6e24aea92df64df5e1f13d7>**
(`reproduction_package_2.zip`, 3.5 GB, unpacking to `reproduction_package/`).

```
reproduction_package/
├── database/montessori_sorting_results.dump   # pg_dump -Fc of the results database: 75 simulated + 17 real episodes
├── episode-artifacts/<identifier>/            # per episode: transcript, joint traces, and for real runs the camera bag and video
├── episode-artifacts/meshes/                  # every mesh a recorded world refers to
└── doc/figures/                               # the tables and cards as submitted, to compare against
```

### One command

`experiments/reproduction/generate_paper_artifacts.py` goes from a fresh machine to the
paper's tables. It

1. starts PostgreSQL, creates the `semantic_digital_twin` role and the
   `montessori_sorting_results` database, and restores the dump (each step only if still
   needed);
2. links the absolute mesh paths the recorded worlds refer to (`/home/tracy/...`) to the
   package, since a world recorded on the robot's computer stores them that way;
3. splits the database into a simulated and a real SQLite corpus
   (`experiments/reproduction/export_filtered_corpus.py`), keeping the
   [7 real episodes the paper uses](#which-real-episodes-the-paper-uses-and-why);
4. scores every real episode's working-memory answers again under the current scoring
   rules and asks each one the long-term-memory question set
   (`experiments/scripts/ask_episode.py`);
5. writes every table (Typst, LaTeX and the rows behind it as JSON) and every query card
   (`experiments/scripts/generate_paper_figures.py`).

```bash
export PACKAGE=/path/to/reproduction_package

python experiments/reproduction/generate_paper_artifacts.py \
    --repository "$(pwd)" \
    --reproduction-package "$PACKAGE" \
    --figures-directory ~/paper_figures \
    --simulated
```

Steps 1 and 2 need root and ask for it through `pkexec` (a graphical prompt). If your
database is already restored, pass `--skip-database-setup`.

The results land in `~/paper_figures/real/` and `~/paper_figures/simulated/`. Add
`--ask-the-control-program` to also ask each real episode what its motions requested of
the controller; that corpus is written to `~/paper_figures/real_with_control_program/`
instead.

### Step by step

The same, by hand, if you would rather not run `pkexec` or want to look at each stage:

```bash
# 1. restore the database
sudo -u postgres psql -v db_name=montessori_sorting_results \
    -v user_name=semantic_digital_twin -v user_password=montessori \
    < semantic_digital_twin/scripts/create_postgres_database_and_user_if_not_exists.sql
PGPASSWORD=montessori pg_restore -h localhost -U semantic_digital_twin \
    -d montessori_sorting_results --no-owner --role=semantic_digital_twin \
    "$PACKAGE/database/montessori_sorting_results.dump"

# 2. make the recorded mesh paths resolve
sudo ln -s "$PACKAGE" /home/tracy
export EPISODE_ARTIFACTS_DIRECTORY="$PACKAGE/episode-artifacts"

# 3. split into a simulated and a real corpus
python experiments/reproduction/export_filtered_corpus.py \
    --source-database-uri postgresql+psycopg://semantic_digital_twin:montessori@localhost:5432/montessori_sorting_results \
    --simulated-output /tmp/montessori_simulated.db \
    --real-output /tmp/montessori_real.db \
    --real-episode 508e367a6fd04cc2ba657f991e3f4bd9 0a793ded6dd54da7b64171ab78638d38 \
        57bbcbb2c919404e9cd729d7e766bf66 25f5161da5584bac9554b686711a01fe \
        e9b1eef3d2f34a57a95e2b897ec63cdd 25ccb55ba8ab4d90aabe54c5800cedb8 \
        3bfe66c1afe644379180e9950081dbc5

# 4. score each real episode again and ask it the long-term-memory set
#    (repeat for every episode, with the object it is asked about - see the table below)
python experiments/scripts/ask_episode.py --episode 508e367a6fd04cc2ba657f991e3f4bd9 \
    --database-uri sqlite:////tmp/montessori_real.db --rescore-working-memory
python experiments/scripts/ask_episode.py --episode 508e367a6fd04cc2ba657f991e3f4bd9 \
    --object-name rectangular_prism_0 --database-uri sqlite:////tmp/montessori_real.db

# 5. the tables and the query cards, once per corpus
python experiments/scripts/generate_paper_figures.py \
    --database-uri sqlite:////tmp/montessori_simulated.db --output-directory ~/paper_figures/simulated
python experiments/scripts/generate_paper_figures.py \
    --database-uri sqlite:////tmp/montessori_real.db --output-directory ~/paper_figures/real
```

To check a recorded episode's rows, artifacts and scores on their own:

```bash
python experiments/scripts/check_episode.py --episode <identifier> --database-uri <uri>
python experiments/scripts/check_episode.py --real --database-uri <uri>
```

## B. Re-run the experiments in simulation

In simulation, MuJoCo stands in for the robot and the table; plans are made by Giskard
against a copy of the world and played back on MuJoCo's actuators. See
[`experiments/src/experiments/tracy_experiments/README.md`](experiments/src/experiments/tracy_experiments/README.md)
for how the simulated rig is built.

### The framework figure's plan

The plan in the paper's framework figure: look at the table, pick the cube off the board's
lid, and insert it through the hole the rules conclude it belongs in. Each open slot of
the plan is answered by a backend (perception, rules, probabilistic model), and the run
reports which backend answered which slot.

```bash
python -m experiments.tracy_experiments.framework_demo --headless --film-directory films
# --watch to run in real time, drop --headless to open the MuJoCo viewer
```

### Sorting the pieces the robot saw

```bash
python -m experiments.tracy_experiments.pickup.pickup_demo_mujoco --headless --video-directory films
```

### The simulated corpus

`run_corpus.py` records one episode for every scenario × layout × perturbation, headless,
and once the corpus stands asks each episode the long-term-memory question set
(`--repetitions` times, default 3). Episode identifiers are written to a manifest as they
are recorded, so an interrupted corpus still names what it recorded.

```bash
export MONTESSORI_SORTING_DATABASE_URI=sqlite:////tmp/my_corpus.db
export EPISODE_ARTIFACTS_DIRECTORY=/tmp/my_episode_artifacts

python experiments/scripts/run_corpus.py [--repetitions 3] [--seed 0]
python experiments/scripts/generate_paper_figures.py --output-directory ~/my_figures
```

A single episode:

```bash
python experiments/scripts/record_episode.py --headless \
    --scenario scene-stands-still \
    --layout randomized \
    --perturbation piece-shoved --piece cube
```

| Option | Values |
|---|---|
| `--scenario` | `scene-stands-still`, `robot-sorts-a-piece`, `piece-pushed-while-idle`, `piece-held-when-asked`, `robot-looks-at-the-scene` |
| `--layout` | `randomized`, `partial`, `nearly-ambiguous` (built scenes); `as-found` (perceived scenes) |
| `--perturbation` | `target-hole-moved`, `piece-shoved`, `perceived-pose-offset`, `detection-relabelled` |
| `--perturbation-step` | the sorting step the perturbation strikes before (default `settle`) |
| `--piece` | the piece the perturbation is aimed at (default `cube`) |
| `--seed`, `--repetitions` | the layout draw's seed, and how many trials the episode holds |

Then ask it and read it back as in path A, steps 4 and 5.

### Tests

The simulated demos are covered by tests that run them headless end to end:

```bash
pytest test/experiments_test/test_framework_demo.py
pytest test/experiments_test/test_tracy_pickup_demo_mujoco.py
pytest test/experiments_test
```

## C. Re-run the experiments on the real robot

This needs the physical setup: the robot with its Giskard/world-fetcher ROS 2 stack, the
Robotiq action servers and the RGB-D camera running, the Montessori board and its pieces on
the table, and a person at the table who places pieces and carries out perturbations when
the console asks. On the robot, the scene is always the one the camera finds, and every
answer is scored against what the person at the table says they set up, not against the
robot's own model of the table.

Record the episodes with a bag (`--record` / `--record-bag`) to keep the camera streams
alongside the joint trace; the query cards are drawn from them.

**The scene stands still** (3 trials per episode; the robot only looks and answers):

```bash
python experiments/scripts/record_episode.py --execution real --record-bag --repetitions 3 \
    --scenario scene-stands-still
python experiments/scripts/record_episode.py --execution real --record-bag --repetitions 3 \
    --scenario scene-stands-still --perturbation piece-shoved --piece cube
python experiments/scripts/record_episode.py --execution real --record-bag --repetitions 3 \
    --scenario scene-stands-still --perturbation target-hole-moved
```

**The robot sorts the pieces it saw** (the camera finds the board and every loose piece,
the left arm sorts each into its hole; a perturbation is asked of the person before the
sort, then looked at again):

```bash
python -m experiments.tracy_experiments.pickup.pickup_demo_real --record
python -m experiments.tracy_experiments.pickup.pickup_demo_real --record \
    --perturbation piece-shoved --piece cube
python -m experiments.tracy_experiments.pickup.pickup_demo_real --record \
    --perturbation target-hole-moved
```

**The framework figure's plan, on the robot:**

```bash
python -m experiments.tracy_experiments.framework_demo --execution real --record
```

Each run writes its episode to the results database and its artifacts to
`EPISODE_ARTIFACTS_DIRECTORY`, and prints the episode identifier. Ask it the
long-term-memory set and regenerate the tables as in path A, steps 4 and 5.

## Which real episodes the paper uses, and why

17 real episodes are in the database; the paper uses 7.

| Episode | Scenario | Perturbation | Trials | Asked about |
|---|---|---|---|---|
| `508e367a6fd04cc2ba657f991e3f4bd9` | the scene stands still | none | 3 | `rectangular_prism_0` |
| `0a793ded6dd54da7b64171ab78638d38` | the scene stands still | piece shoved (cube) | 3 | `cube_2` |
| `57bbcbb2c919404e9cd729d7e766bf66` | the scene stands still | target hole moved (board) | 3 | `rectangular_prism_0` |
| `25f5161da5584bac9554b686711a01fe` | the robot sorts the pieces it saw | none | 1 | `cube_2` |
| `e9b1eef3d2f34a57a95e2b897ec63cdd` | the robot sorts the pieces it saw | piece shoved (cube) | 1 | `cube_3` |
| `25ccb55ba8ab4d90aabe54c5800cedb8` | the robot sorts the pieces it saw | target hole moved (board) | 1 | `cube_3` |
| `3bfe66c1afe644379180e9950081dbc5` | the robot carries out the plan the framework figure shows | none | 1 | `cube_3` |

The 10 left out:

- **Recorded before scoring was fixed to use what the person at the table says**, rather
  than the robot's simulated twin of the table (all "the scene stands still", each showing
  the same one wrong answer in 14): `2c6c42943eaa437cb0c9f715e8deb199`,
  `99a3454aa1164093ad06c10a75df9f13`, `4aebad2d18e5425c8e46705206785a79`,
  `d0953ca1550848ceae88094ef054d11e`, `16177269e93c477c9786a1b174e8df91`.
- **Superseded by a later rerun of the same condition:**
  `2f37062677c94eb1bd51ea6d3f496f06` (by `508e367a…`),
  `d37b712da5434f7cac205cd477d9e868` (by `0a793ded…`),
  `6ffe9ec2ef3c4f0b8d7d5b44adf94d33` and `c2efb7db9f45406ba5a42b54f8d1e0ac`
  (by `57bbcbb2…`), `cb2af2ffca354e3d97273ee3898ecbc9` (by `e9b1eef3…`).

All 17 remain in the dump; pass other identifiers to `export_filtered_corpus.py
--real-episode` to include them.

## Where things are

| Path | What |
|---|---|
| `experiments/reproduction/` | The two scripts of path A |
| `experiments/scripts/` | Command-line entry points: `record_episode.py`, `run_corpus.py`, `ask_episode.py`, `check_episode.py`, `generate_paper_figures.py` |
| `experiments/src/experiments/montessori/` | Scenarios, perturbations, perception, the results database |
| `experiments/src/experiments/episodes/` | Recording an episode, its artifacts, long-term memory |
| `experiments/src/experiments/questions/` | The working-memory and long-term-memory question sets |
| `experiments/src/experiments/open_slots/` | The framework figure's plan and the backends that answer its open slots |
| `experiments/src/experiments/tracy_experiments/` | The simulated (`*_mujoco.py`) and real (`*_real.py`) robot rigs and demos |
| `experiments/src/experiments/paper/` | Tables, query cards and plan timelines |
| `experiments/doc/figures/framework/` | The framework figure (`python experiments/doc/figures/framework/build.py`, needs `pip install typst`) |
| `experiments/doc/video/` | The supplementary video |
| `test/experiments_test/` | Tests for all of the above |
| `MONOREPO.md` | The general README of the monorepo this branch lives in |
