"""
Runs :mod:`~experiments.montessori.franka_montessori_demo` for many iterations by
restarting it every few iterations in a fresh subprocess, instead of one process running
every iteration.

Each rebuilt world's MuJoCo model and Bullet collision shapes (see
:class:`~semantic_digital_twin.collision_checking.pybullet_collision_detector.BulletCollisionDetector`)
free their own native allocations correctly, but the process's RSS still climbs by
roughly 130-200MB per iteration -- glibc's allocator not returning freed-but-fragmented
heap to the OS accounts for most of it (``gc.collect()`` plus ``malloc_trim(0)`` after
each iteration, see
:func:`~experiments.montessori.franka_montessori_demo._reclaim_native_heap_fragmentation`,
recovers 150-230MB of it), but a smaller genuine native leak remains underneath that
trimming doesn't reach. Over hundreds of iterations either way, RSS eventually reaches
the machine's OOM threshold (~12GB observed on a 15GB machine, both before and after
the trim fix) and the kernel OOM-killer ends the process outright, losing whatever
tail of the run hadn't been committed. Restarting the process every ``--batch-size``
iterations bounds peak RSS by construction, independent of the leak's exact rate or
root cause: each subprocess starts cold and is torn down (returning all of its memory
to the OS) well before it could approach that ceiling.

Every iteration's result is committed to ``--database-uri`` as it finishes (see
:func:`~experiments.montessori.franka_montessori_demo._open_results_session`)
regardless of which subprocess ran it, so a batch that dies partway through still
leaves its completed iterations recorded; only that batch is retried, not the whole
run.

Run with (the ``experiments`` package must be importable)::

    python -m experiments.montessori.batch_runner --world2 --no-rviz \\
        --total-iterations 500 --batch-size 20 \\
        --database-uri sqlite:///franka_montessori_500_run.db
"""

from __future__ import annotations

import argparse
import logging
import subprocess
import sys

logger = logging.getLogger(__name__)

DEFAULT_BATCH_SIZE = 20
DEFAULT_MAX_RETRIES_PER_BATCH = 3


def _parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--world2", action="store_true")
    parser.add_argument("--no-rviz", action="store_true")
    parser.add_argument("--database-uri", required=True)
    parser.add_argument("--total-iterations", type=int, required=True)
    parser.add_argument(
        "--start-iteration",
        type=int,
        default=1,
        help=(
            "1-based index recorded on the first iteration this run performs, "
            "counting up from there. Lets a run resume where an earlier, separately "
            "run batch of iterations left off, e.g. after that batch was interrupted, "
            "instead of renumbering from 1 and colliding with its already-recorded "
            "iterations."
        ),
    )
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE)
    parser.add_argument(
        "--max-retries-per-batch", type=int, default=DEFAULT_MAX_RETRIES_PER_BATCH
    )
    return parser.parse_args()


def _run_batch(
    start_iteration: int, batch_size: int, arguments: argparse.Namespace
) -> int:
    """
    Run one batch of ``batch_size`` iterations, starting at ``start_iteration``, in a
    fresh subprocess with real-time physics pacing forced (see
    :mod:`~experiments.montessori.headless_realtime_pacing_runner`).

    :return: The subprocess's exit code; ``0`` means every iteration in the batch
        completed and was committed.
    """
    command = [
        sys.executable,
        "-m",
        "experiments.montessori.headless_realtime_pacing_runner",
        "--iterations",
        str(batch_size),
        "--start-iteration",
        str(start_iteration),
        "--exit-after-sorting",
        "--database-uri",
        arguments.database_uri,
    ]
    if arguments.world2:
        command.append("--world2")
    if arguments.no_rviz:
        command.append("--no-rviz")

    result = subprocess.run(command)
    return result.returncode


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    arguments = _parse_arguments()

    completed = 0
    while completed < arguments.total_iterations:
        batch_size = min(arguments.batch_size, arguments.total_iterations - completed)
        start_iteration = arguments.start_iteration + completed

        for attempt in range(1, arguments.max_retries_per_batch + 1):
            logger.info(
                "=== Batch: iterations %d-%d (attempt %d/%d) ===",
                start_iteration,
                start_iteration + batch_size - 1,
                attempt,
                arguments.max_retries_per_batch,
            )
            exit_code = _run_batch(start_iteration, batch_size, arguments)
            if exit_code == 0:
                break
            logger.warning(
                "Batch starting at iteration %d exited with code %d (attempt %d/%d).",
                start_iteration,
                exit_code,
                attempt,
                arguments.max_retries_per_batch,
            )
        else:
            logger.error(
                "Batch starting at iteration %d failed %d times; giving up.",
                start_iteration,
                arguments.max_retries_per_batch,
            )
            sys.exit(1)

        completed += batch_size

    logger.info("=== All %d iterations completed. ===", arguments.total_iterations)


if __name__ == "__main__":
    main()
