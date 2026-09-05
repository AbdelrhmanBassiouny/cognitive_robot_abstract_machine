"""
Tests for the command line each of these scripts declares.

What is under test is the one thing the wrapper exists for: an option is spelled once,
in the enum, and the attribute a parsed run is read back through follows from it rather
than from a second spelling.
"""

from enum import StrEnum

import pytest

from script_arguments import ScriptArgumentParser

DESCRIPTION = "What the script does."
GIVEN_VALUE = "a value"
DEFAULT_VALUE = "what it stands for"


class ExampleOption(StrEnum):
    """
    A script's options, standing in for a real script's.
    """

    OUTPUT_DIRECTORY = "--output-directory"
    """
    A multi-word option, which is where the attribute's spelling could diverge.
    """

    REMOTE = "--remote"
    """
    A single-word one.
    """


def test_an_option_is_read_back_under_the_attribute_its_own_flag_derives():
    """
    The flag is the single spelling: the attribute follows from it rather than being
    named a second time at the parser call.
    """
    parser = ScriptArgumentParser(DESCRIPTION)
    parser.add(ExampleOption.OUTPUT_DIRECTORY, "where")

    parsed = parser.parser.parse_args([ExampleOption.OUTPUT_DIRECTORY, GIVEN_VALUE])

    assert parsed.output_directory == GIVEN_VALUE


def test_an_option_with_a_default_may_be_left_out():
    """
    An option that stands for something when unnamed is optional; the default is what a
    run that omits it gets.
    """
    parser = ScriptArgumentParser(DESCRIPTION)
    parser.add(ExampleOption.REMOTE, "which remote", default=DEFAULT_VALUE)

    assert parser.parser.parse_args([]).remote == DEFAULT_VALUE


def test_an_option_without_a_default_is_required():
    """
    An option nothing can stand in for must be given, so a run missing it fails at the
    command line rather than part-way through the work.
    """
    parser = ScriptArgumentParser(DESCRIPTION)
    parser.add(ExampleOption.REMOTE, "which remote")

    with pytest.raises(SystemExit):
        parser.parser.parse_args([])


def test_declarations_chain():
    """
    A script declares its whole command line in one expression rather than repeating the
    parser at each option.
    """
    parser = (
        ScriptArgumentParser(DESCRIPTION)
        .add(ExampleOption.OUTPUT_DIRECTORY, "where")
        .add(ExampleOption.REMOTE, "which remote", default=DEFAULT_VALUE)
    )

    parsed = parser.parser.parse_args([ExampleOption.OUTPUT_DIRECTORY, GIVEN_VALUE])

    assert (parsed.output_directory, parsed.remote) == (GIVEN_VALUE, DEFAULT_VALUE)
