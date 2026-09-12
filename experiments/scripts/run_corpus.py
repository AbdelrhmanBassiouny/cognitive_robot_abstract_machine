"""
Record the corpus the paper's tables are computed over.

Usage:
    python3 run_corpus.py [--repetitions <n>] [--piece <shape>] [--seed <n>]
        [--manifest <path>] [--database-uri <uri>]

Every scenario, every layout a built scene stands its pieces by, and every
perturbation a run can apply, recorded headless in simulation and then asked the
long-term-memory question set several times over.

See :mod:`experiments.montessori.run_corpus` for what each option does.
"""

from __future__ import annotations

import sys

from experiments.montessori.run_corpus import main

if __name__ == "__main__":
    sys.exit(main())
