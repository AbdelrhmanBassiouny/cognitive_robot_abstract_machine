"""
Ask a recorded episode the long-term-memory question set and keep the answers with it.

Usage:
    python3 ask_episode.py --episode <identifier> --object-name <name>
        [--database-uri <uri>]

See :mod:`experiments.montessori.ask_episode` for what each option does.
"""

from __future__ import annotations

import sys

from experiments.montessori.ask_episode import main

if __name__ == "__main__":
    sys.exit(main())
