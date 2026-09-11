"""
Record one episode of a Montessori sorting scenario.

Usage:
    python3 record_episode.py [--scenario <name>] [--layout <name>]
        [--perturbation <name>] [--perturbation-step <step>] [--execution simulated|real]
        [--piece <shape>] [--seed <n>] [--repetitions <n>] [--record-bag] [--headless]
        [--database-uri <uri>]

See :mod:`experiments.montessori.record_episode` for what each option does.
"""

from __future__ import annotations

import sys

from experiments.montessori.record_episode import main

if __name__ == "__main__":
    sys.exit(main())
