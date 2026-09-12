"""
Record one episode of a Montessori sorting scenario.

Usage:
    python3 record_episode.py [--scenario <name>] [--scene built|perceived]
        [--layout <name>] [--perturbation <name>] [--perturbation-step <step>]
        [--execution simulated|real] [--piece <shape>] [--seed <n>] [--repetitions <n>]
        [--record-bag] [--headless] [--database-uri <uri>]

On the robot, with the camera and the world-fetcher ROS stack running, the scene is
the one its camera finds, and a perturbation is asked of the person at the table and
then looked at::

    python3 record_episode.py --execution real \
        --scenario scene-stands-still --perturbation piece-shoved --piece cube

See :mod:`experiments.montessori.record_episode` for what each option does.
"""

from __future__ import annotations

import sys

from experiments.montessori.record_episode import main

if __name__ == "__main__":
    sys.exit(main())
