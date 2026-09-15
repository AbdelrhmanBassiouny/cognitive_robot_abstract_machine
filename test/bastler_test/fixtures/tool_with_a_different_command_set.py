#!/usr/bin/env python3
"""
Stands in for a version of the tool whose commands are not the ones a pass started with.

A pass switches branches in the checkout it runs from, so the tool is a file that
version control moves like any other. This is what a caller meets on the other side of
such a switch: the same path, a command set that has since been renamed, and argparse's
own usage status for anything it no longer answers.
"""

from __future__ import annotations

import argparse

A_COMMAND_THIS_VERSION_STILL_ANSWERS = "status"
"""
The one command kept, so a refusal is a command set that differs rather than a parser
that answers nothing at all.
"""


def main() -> None:
    """
    Parse the command line the way the real tool does, and refuse anything else.
    """
    parser = argparse.ArgumentParser(prog="stack.py")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser(A_COMMAND_THIS_VERSION_STILL_ANSWERS)
    parser.parse_args()


if __name__ == "__main__":
    main()
