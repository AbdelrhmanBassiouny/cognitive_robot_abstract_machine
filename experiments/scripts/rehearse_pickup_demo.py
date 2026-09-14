"""
Rehearse the real pickup demo without the robot and the camera, and check what it
recorded.

Usage:
    python3 rehearse_pickup_demo.py [--record] [--perturbation <choice> --piece <piece>]
        [--ask-about <piece>] [--capture <name>] [--capture-after <name>]
        [--pieces-placed <piece> ...] [--database-uri <uri>]

See :mod:`experiments.tracy_experiments.pickup.pickup_demo_rehearsal` for what each
option does.
"""

from __future__ import annotations

import sys

from experiments.tracy_experiments.pickup.pickup_demo_rehearsal import main

if __name__ == "__main__":
    sys.exit(main())
