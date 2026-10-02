"""
Tests for standard_streams.py: the package's logging, which is also what its commands
print through.
"""

import logging

import basstler
import basstler.standard_streams
from basstler.standard_streams import StandardStreamHandler

MODULE_NAME = basstler.standard_streams.__name__
"""
A module inside the package, whose logger the package's handler writes for.
"""

# %% where a record goes


def test_an_information_record_is_printed_bare_on_standard_output(capsys):
    """
    A command's output is read by its caller, so it carries no level or logger prefix.
    """
    StandardStreamHandler.logger_for(MODULE_NAME).info("some output")
    captured = capsys.readouterr()
    assert (captured.out, captured.err) == ("some output\n", "")


def test_an_error_record_is_printed_bare_on_standard_error(capsys):
    StandardStreamHandler.logger_for(MODULE_NAME).error("some failure")
    captured = capsys.readouterr()
    assert (captured.out, captured.err) == ("", "some failure\n")


# %% configuring the package logger once


def test_asking_for_loggers_twice_attaches_one_handler():
    """
    Every module asks for its logger, so a second request must not print every record a
    second time.
    """
    StandardStreamHandler.logger_for(MODULE_NAME)
    StandardStreamHandler.logger_for(MODULE_NAME)
    package_handlers = logging.getLogger(basstler.__name__).handlers
    assert (
        len([h for h in package_handlers if isinstance(h, StandardStreamHandler)]) == 1
    )
