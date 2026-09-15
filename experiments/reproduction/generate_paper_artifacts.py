"""
One script that takes a fresh machine from nothing to the paper's figures: restores the
database, exports the real (and, if asked, simulated) corpus, scores every real
episode's working-memory rows again under the current scoring rules and asks it the
long-term-memory question set, regenerates every table (as LaTeX) and query card (as
pictures), and leaves them in one directory per corpus.

Real episodes are always done; pass --simulated to also do the simulated corpus. Every
step is checked before it is done, so running this again on a machine that already has
some of it set up only does what is still missing.

Usage:
    python3 experiments/reproduction/generate_paper_artifacts.py \
        --repository <this repository> \
        --reproduction-package <the unpacked reproduction package> \
        --figures-directory <where the tables and cards are left> \
        [--simulated] [--skip-database-setup] [--ask-the-control-program]

Needs the ``psql``/``createdb``/``pg_restore`` client tools, and a graphical polkit
agent for the two steps that need root (starting the ``postgresql`` service, and
provisioning the role and database as the ``postgres`` superuser) -- both run through
``pkexec``, which prompts for it there rather than over this terminal.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Sequence

DATABASE_NAME = "montessori_sorting_results"
"""
The database this package's dump restores into, and every step below reads from.
"""

ROLE_NAME = "semantic_digital_twin"
"""
The role every step connects as, already provisioned for the rest of the workspace's own
experiments.
"""

ROLE_PASSWORD = "montessori"
"""
That role's password, matching ``DEFAULT_DATABASE_URI`` in
``experiments.montessori.results_database``.
"""

DATABASE_HOST = "localhost"
DATABASE_PORT = "5432"

DATABASE_URI = "postgresql+psycopg://%s:%s@%s:%s/%s" % (
    ROLE_NAME,
    ROLE_PASSWORD,
    DATABASE_HOST,
    DATABASE_PORT,
    DATABASE_NAME,
)
"""
Where every step below reads the restored corpus from.
"""

PROVISIONING_SCRIPT = (
    "semantic_digital_twin/scripts/create_postgres_database_and_user_if_not_exists.sql"
)
"""
Where the repository keeps the SQL that creates :data:`ROLE_NAME` and
:data:`DATABASE_NAME`, relative to the repository's own root.
"""

REAL_EPISODES: Dict[str, str] = {
    "508e367a6fd04cc2ba657f991e3f4bd9": "rectangular_prism_0",
    "0a793ded6dd54da7b64171ab78638d38": "cube_2",
    "57bbcbb2c919404e9cd729d7e766bf66": "rectangular_prism_0",
    "25f5161da5584bac9554b686711a01fe": "cube_2",
    "e9b1eef3d2f34a57a95e2b897ec63cdd": "cube_3",
    "25ccb55ba8ab4d90aabe54c5800cedb8": "cube_3",
    "3bfe66c1afe644379180e9950081dbc5": "cube_3",
}
"""
The real episodes kept after filtering, as the repository's README records and explains
them, each mapped to the object its recorded working-memory questions single
out ("Was the cube_2 recently picked up?"), which is what its long-term-memory questions
are asked about.
"""

ASK_EPISODE_SCRIPT = "experiments/scripts/ask_episode.py"
"""
The repository's own script that scores an episode's rows again and asks it the long-
term-memory set, relative to the repository's root.
"""

ASK_THE_CONTROL_PROGRAM = "--ask-the-control-program"
"""
The ``ask_episode.py`` option that adds the questions about the control program to the
long-term-memory set.
"""

REAL_WITH_THE_CONTROL_PROGRAM = "real_with_control_program"
"""
What the real corpus is called when its episodes are also asked about the control
program, which is the directory its tables and cards are left in.
"""

PAPER_FILE_SUFFIXES = (".tex", ".json", ".png")
"""
What the paper is given of a corpus: its tables as LaTeX, the rows behind each table,
and the query cards' pictures.
"""

MESH_PATH_SYMLINKS = {
    Path("/home/tracy"): None,
    Path("/home/tracy/workspace/ros"): Path.home() / "ros2_ws",
}
"""
Absolute paths a recorded world's meshes refer to by the machine that recorded them,
mapped to where this machine keeps the same thing -- ``None`` where the reproduction
package's own directory serves it, filled in with the repository's actual location once
that is known.
"""

EXPORT_SCRIPT = Path(__file__).with_name("export_filtered_corpus.py")
"""
The script that splits the restored database into one SQLite database per corpus.
"""

# %% one shell command, reported as it runs


@dataclass
class CommandFailed(Exception):
    """
    Raised when a step this script runs exits with a non-zero status.
    """

    command: Sequence[str]
    returncode: int

    def __str__(self) -> str:
        return "%s exited with %d" % (" ".join(self.command), self.returncode)


def run(command: Sequence[str], **kwargs) -> None:
    """
    Run one step, printing it first, raising if it fails.

    :param command: The command and its arguments.
    :param kwargs: Passed on to :func:`subprocess.run`.
    """
    print("+ %s" % " ".join(command))
    result = subprocess.run(command, **kwargs)
    if result.returncode != 0:
        raise CommandFailed(command=command, returncode=result.returncode)


def command_output(command: Sequence[str]) -> str:
    """
    Run one step and return what it printed, stripped.
    """
    return subprocess.run(
        command, capture_output=True, text=True, check=True
    ).stdout.strip()


# %% database setup


def postgresql_is_running() -> bool:
    return (
        subprocess.run(
            ["pg_isready", "-h", DATABASE_HOST, "-p", DATABASE_PORT],
            capture_output=True,
        ).returncode
        == 0
    )


def start_postgresql() -> None:
    """
    Start the local ``postgresql`` service, prompting for root through a graphical
    polkit agent.
    """
    print("PostgreSQL is not running; starting it needs root -- watch for a prompt.")
    run(["pkexec", "systemctl", "start", "postgresql"])


def role_and_database_exist() -> bool:
    return (
        subprocess.run(
            [
                "psql",
                "-h",
                DATABASE_HOST,
                "-p",
                DATABASE_PORT,
                "-U",
                ROLE_NAME,
                "-d",
                DATABASE_NAME,
                "-c",
                "\\q",
            ],
            capture_output=True,
            env={"PGPASSWORD": ROLE_PASSWORD, **_current_env()},
        ).returncode
        == 0
    )


def _current_env() -> dict:
    import os

    return dict(os.environ)


def provision_role_and_database(repository: Path) -> None:
    """
    Create :data:`ROLE_NAME` and :data:`DATABASE_NAME`, prompting for root through a
    graphical polkit agent.

    :param repository: The repository :data:`PROVISIONING_SCRIPT` is read from.
    """
    print(
        "The %s role or the %s database do not exist yet; provisioning them needs "
        "root -- watch for a prompt." % (ROLE_NAME, DATABASE_NAME)
    )
    script = repository / PROVISIONING_SCRIPT
    with script.open("rb") as script_file:
        run(
            [
                "pkexec",
                "--user",
                "postgres",
                "psql",
                "-v",
                "db_name=%s" % DATABASE_NAME,
                "-v",
                "user_name=%s" % ROLE_NAME,
                "-v",
                "user_password=%s" % ROLE_PASSWORD,
            ],
            stdin=script_file,
        )


def database_has_data() -> bool:
    count = command_output(
        [
            "psql",
            "-h",
            DATABASE_HOST,
            "-p",
            DATABASE_PORT,
            "-U",
            ROLE_NAME,
            "-d",
            DATABASE_NAME,
            "-t",
            "-c",
            'select count(*) from "EpisodeDAO";',
        ]
    )
    return int(count) > 0


def restore_dump(reproduction_package: Path) -> None:
    """
    Restore this package's dump into the already-provisioned, empty database.

    :param reproduction_package: The reproduction package the dump is read from.
    """
    dump = reproduction_package / "database" / "montessori_sorting_results.dump"
    print("Restoring %s (no data found in %s yet) ..." % (dump, DATABASE_NAME))
    run(
        [
            "pg_restore",
            "-h",
            DATABASE_HOST,
            "-p",
            DATABASE_PORT,
            "-U",
            ROLE_NAME,
            "-d",
            DATABASE_NAME,
            "--no-owner",
            "--role=%s" % ROLE_NAME,
            str(dump),
        ],
        env={"PGPASSWORD": ROLE_PASSWORD, **_current_env()},
    )


def ensure_database_ready(repository: Path, reproduction_package: Path) -> None:
    """
    Bring the database up to a state every other step can read from: running,
    provisioned, and holding this package's dump.

    :param repository: Where :data:`PROVISIONING_SCRIPT` is read from.
    :param reproduction_package: Where the dump to restore is read from.
    """
    if not postgresql_is_running():
        start_postgresql()
    if not role_and_database_exist():
        provision_role_and_database(repository)
    if not database_has_data():
        restore_dump(reproduction_package)
    else:
        print("%s already holds data; not restoring the dump." % DATABASE_NAME)


# %% mesh and description paths a recorded world refers to


def ensure_mesh_paths_resolve(reproduction_package: Path) -> None:
    """
    Symlink the absolute paths a recorded world's meshes refer to, on the machine that
    recorded them, to where this machine actually keeps the same thing.

    A recorded world's mesh files are read from an absolute path baked in at record
    time (``experiments.episodes.artifacts.keep_meshes_of``), so a world recorded on
    another machine is unreadable until the same absolute path resolves here too.

    :param reproduction_package: Stands in for ``/home/tracy`` itself.
    """
    targets = dict(MESH_PATH_SYMLINKS)
    targets[Path("/home/tracy")] = reproduction_package
    needs_root = [
        (link, target)
        for link, target in targets.items()
        if not link.is_symlink() and not link.exists()
    ]
    if not needs_root:
        return
    print(
        "%d mesh path symlink(s) are missing; creating them needs root -- watch for "
        "a prompt." % len(needs_root)
    )
    for link, target in needs_root:
        run(["pkexec", "mkdir", "-p", str(link.parent)])
        run(["pkexec", "ln", "-s", str(target), str(link)])


# %% exporting and regenerating one corpus


@dataclass
class Corpus:
    """
    One of the two corpora the paper's figures are regenerated from.
    """

    name: str
    """
    What this corpus is called in this script's own output.
    """

    database_path: Path
    """
    The derived SQLite database this corpus is exported into.
    """

    export_arguments: List[str]
    """
    The ``export_filtered_corpus.py`` arguments that pick out this corpus's trials.
    """

    asked_about: Dict[str, str]
    """
    Each episode that is scored again and asked the long-term-memory set, mapped to the
    object those questions are about.
    """

    export_output_option: str
    """
    The ``export_filtered_corpus.py`` option naming where this corpus's database goes.
    """

    asks_the_control_program: bool = False
    """
    Whether the long-term-memory set asked of each episode includes the questions about
    the control program -- what the recorded motions asked the controller for.
    """


def real_corpus(work_directory: Path, asks_the_control_program: bool = False) -> Corpus:
    """
    The real episodes kept after filtering.

    :param work_directory: Where the corpus's derived database goes.
    :param asks_the_control_program: Whether its episodes are also asked about the
        control program; such a corpus is named apart, so its tables and cards are left
        next to the ones without those questions rather than over them.
    """
    name = REAL_WITH_THE_CONTROL_PROGRAM if asks_the_control_program else "real"
    return Corpus(
        name=name,
        database_path=work_directory / ("montessori_%s_filtered.db" % name),
        export_arguments=["--real-episode", *REAL_EPISODES],
        asked_about=REAL_EPISODES,
        export_output_option="--real-output",
        asks_the_control_program=asks_the_control_program,
    )


def simulated_corpus(work_directory: Path) -> Corpus:
    return Corpus(
        name="simulated",
        database_path=work_directory / "montessori_simulated.db",
        export_arguments=[],
        asked_about={},
        export_output_option="--simulated-output",
    )


def export_corpus(corpus: Corpus, episode_artifacts_directory: Path) -> None:
    """
    Split the source database into this corpus's own derived SQLite database.

    :param corpus: Which corpus, and its own export arguments.
    :param episode_artifacts_directory: What ``EPISODE_ARTIFACTS_DIRECTORY`` is set to.
    """
    run(
        [
            sys.executable,
            str(EXPORT_SCRIPT),
            "--source-database-uri",
            DATABASE_URI,
            corpus.export_output_option,
            str(corpus.database_path),
            *corpus.export_arguments,
        ],
        env={
            "EPISODE_ARTIFACTS_DIRECTORY": str(episode_artifacts_directory),
            **_current_env(),
        },
    )


def generate_figures(
    corpus: Corpus,
    repository: Path,
    output_directory: Path,
    episode_artifacts_directory: Path,
) -> None:
    """
    Regenerate this corpus's tables and query cards with the repository's own,
    unmodified script.

    :param corpus: Which corpus to read.
    :param repository: The repository ``generate_paper_figures.py`` is read from.
    :param output_directory: Where the tables and cards are written.
    :param episode_artifacts_directory: What ``EPISODE_ARTIFACTS_DIRECTORY`` is set to.
    """
    run(
        [
            sys.executable,
            str(repository / "experiments" / "scripts" / "generate_paper_figures.py"),
            "--database-uri",
            "sqlite:///%s" % corpus.database_path,
            "--output-directory",
            str(output_directory),
        ],
        env={
            "EPISODE_ARTIFACTS_DIRECTORY": str(episode_artifacts_directory),
            **_current_env(),
        },
    )


def score_again_and_ask(
    corpus: Corpus, repository: Path, episode_artifacts_directory: Path
) -> None:
    """
    Score each episode's working-memory rows again under the scoring rules the
    repository holds now, and ask it the long-term-memory question set, keeping both in
    the corpus's derived database.

    A run records its scores as it happens, so an episode recorded before a scoring fix
    keeps the older score until it is scored again; and the long-term-memory set is only
    ever asked after the fact, so without this the tables carry no remembering rows.

    :param corpus: Which corpus, and the object each of its episodes is asked about.
    :param repository: The repository ``ask_episode.py`` is read from.
    :param episode_artifacts_directory: Where the joint traces the rows are scored
        against are kept.
    """
    database_uri = "sqlite:///%s" % corpus.database_path
    script = str(repository / ASK_EPISODE_SCRIPT)
    environment = {
        "EPISODE_ARTIFACTS_DIRECTORY": str(episode_artifacts_directory),
        **_current_env(),
    }
    for identifier, object_name in corpus.asked_about.items():
        run(
            [
                sys.executable,
                script,
                "--episode",
                identifier,
                "--database-uri",
                database_uri,
                "--rescore-working-memory",
            ],
            env=environment,
        )
        run(
            [
                sys.executable,
                script,
                "--episode",
                identifier,
                "--object-name",
                object_name,
                "--database-uri",
                database_uri,
                *([ASK_THE_CONTROL_PROGRAM] if corpus.asks_the_control_program else []),
            ],
            env=environment,
        )


def copy_into_figures_directory(
    output_directory: Path, figures_directory: Path, corpus_name: str
) -> None:
    """
    Replace the corpus's directory in the figures directory with every LaTeX table, the
    row manifest behind it, and every query card picture.

    :param output_directory: Where ``generate_figures`` wrote the corpus's files.
    :param figures_directory: Where every corpus's finished files are left.
    :param corpus_name: Which corpus these files belong to, naming their directory.
    """
    import shutil

    destination_root = figures_directory / corpus_name
    if destination_root.is_dir():
        shutil.rmtree(destination_root)
    kept = [
        path
        for path in output_directory.rglob("*")
        if path.suffix in PAPER_FILE_SUFFIXES
    ]
    for source in kept:
        destination = destination_root / source.relative_to(output_directory)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
    print("Copied %d file(s) into %s." % (len(kept), destination_root))


def build_corpus(
    corpus: Corpus,
    repository: Path,
    reproduction_package: Path,
    figures_directory: Path,
    work_directory: Path,
) -> None:
    """
    Export, regenerate, compile, and hand off one corpus's figures, start to finish.

    :param corpus: Which corpus to build.
    :param repository: The workspace checkout every script below is read from.
    :param reproduction_package: Where the source data is read from.
    :param figures_directory: Where the finished files are left.
    :param work_directory: Where intermediate files (the derived database, the raw
        tables and cards) are written.
    """
    print("\n== %s corpus ==" % corpus.name)
    episode_artifacts_directory = reproduction_package / "episode-artifacts"
    if corpus.database_path.exists():
        corpus.database_path.unlink()
    export_corpus(corpus, episode_artifacts_directory)
    score_again_and_ask(corpus, repository, episode_artifacts_directory)
    output_directory = work_directory / ("figures_%s" % corpus.name)
    if output_directory.is_dir():
        import shutil

        shutil.rmtree(output_directory)
    generate_figures(corpus, repository, output_directory, episode_artifacts_directory)
    copy_into_figures_directory(output_directory, figures_directory, corpus.name)


# %% the whole run


def main(argument_list: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--reproduction-package",
        type=Path,
        required=True,
        help="The unpacked reproduction package: the database dump and the episode "
        "artifacts.",
    )
    parser.add_argument(
        "--repository",
        type=Path,
        required=True,
        help="A checkout of this repository (this branch or later).",
    )
    parser.add_argument(
        "--figures-directory",
        type=Path,
        required=True,
        help="Where each corpus's tables and cards are left, one directory per corpus.",
    )
    parser.add_argument(
        "--work-directory",
        type=Path,
        default=Path("/tmp/paper_artifacts"),
        help="Where intermediate databases and raw figures are written.",
    )
    parser.add_argument(
        "--simulated",
        action="store_true",
        help="Also build the simulated corpus, in addition to the real one.",
    )
    parser.add_argument(
        "--skip-database-setup",
        action="store_true",
        help="Skip checking/starting PostgreSQL, provisioning, and restoring the "
        "dump -- use when the database is already ready.",
    )
    parser.add_argument(
        ASK_THE_CONTROL_PROGRAM,
        action="store_true",
        help="Also ask the real episodes what their motions asked the controller for, "
        "leaving that corpus's tables and cards in <figures directory>/%s instead of "
        "<figures directory>/real." % REAL_WITH_THE_CONTROL_PROGRAM,
    )
    arguments = parser.parse_args(argument_list)

    if not arguments.skip_database_setup:
        ensure_database_ready(arguments.repository, arguments.reproduction_package)
    ensure_mesh_paths_resolve(arguments.reproduction_package)
    arguments.work_directory.mkdir(parents=True, exist_ok=True)

    corpora = [real_corpus(arguments.work_directory, arguments.ask_the_control_program)]
    if arguments.simulated:
        corpora.append(simulated_corpus(arguments.work_directory))

    for corpus in corpora:
        build_corpus(
            corpus,
            arguments.repository,
            arguments.reproduction_package,
            arguments.figures_directory,
            arguments.work_directory,
        )

    print(
        "\nDone. The tables (labelled tab:<name>) and the cards' pictures are in %s."
        % arguments.figures_directory
    )
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except CommandFailed as error:
        print("error: %s" % error, file=sys.stderr)
        sys.exit(1)
