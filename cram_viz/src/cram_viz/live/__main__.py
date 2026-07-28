"""``cram-viz-live path/to/demo.py`` — run a demo with the live bridge."""

import os
import runpy
import sys
import time

from cram_viz.live import start


def main():
    if len(sys.argv) < 2:
        sys.exit("usage: cram-viz-live path/to/demo.py  (runs the demo with the live bridge)")
    demo = os.path.abspath(sys.argv[1])
    start()
    sys.path.insert(0, os.path.dirname(demo))
    # repo-level helper packages (test.conftest), same as onboard_demo
    d = os.path.dirname(demo)
    while d != os.path.dirname(d):
        if os.path.isdir(os.path.join(d, "coraplex")) and os.path.isdir(os.path.join(d, "test")):
            sys.path.insert(0, d)
            break
        d = os.path.dirname(d)
    print("[cram_viz.live] running demo:", demo, flush=True)
    runpy.run_path(demo, run_name="__main__")
    print("[cram_viz.live] demo finished — bridge stays up for inspection (Ctrl-C to quit)", flush=True)
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        os._exit(0)


if __name__ == "__main__":
    main()
