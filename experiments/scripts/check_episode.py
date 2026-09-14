"""
Check recorded episodes: rows, artifacts, logic and scores.

Usage:
    python3 check_episode.py --episode <identifier> [<identifier> ...]
        [--database-uri <uri>]
    python3 check_episode.py --latest <n> [--real] [--database-uri <uri>]
    python3 check_episode.py --real [--database-uri <uri>]

See :mod:`experiments.montessori.check_episode` for what each option does.
"""

from __future__ import annotations

import sys

from experiments.montessori.check_episode import main

if __name__ == "__main__":
    sys.exit(main())
