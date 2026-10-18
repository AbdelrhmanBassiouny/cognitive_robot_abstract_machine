from __future__ import annotations

import shutil
from pathlib import Path

from cram_development_tools.command_line import CommandLine, ExitStatus, Subcommand
from cram_development_tools.docstring_formatting import (
    BlackOption,
    DocstringFormatter,
    Formatter,
)

from .dataset_files import DatasetFile

# %% single file outcomes


def test_formats_code_and_docstrings_when_the_tools_agree(
    copy_into_temporary_directory,
) -> None:
    path = copy_into_temporary_directory(DatasetFile.UNFORMATTED_MODULE, "module.py")

    outcome = DocstringFormatter().format_file(path)

    assert outcome.final_content == DatasetFile.FORMATTED_MODULE.value.read_text()
    assert outcome.docstrings_reformatted


def test_keeps_black_output_when_docformatter_conflicts_with_black(
    copy_into_temporary_directory, tmp_path: Path
) -> None:
    path = copy_into_temporary_directory(
        DatasetFile.DOCSTRING_CONFLICTING_MODULE, "module.py"
    )
    black_only_path = tmp_path / "black_only.py"
    shutil.copyfile(path, black_only_path)
    Formatter.BLACK.run(list(BlackOption), black_only_path)

    outcome = DocstringFormatter().format_file(path)

    assert outcome.final_content == black_only_path.read_text()
    assert not outcome.docstrings_reformatted


def test_leaves_a_file_black_rejects_unchanged(copy_into_temporary_directory) -> None:
    path = copy_into_temporary_directory(DatasetFile.INVALID_SYNTAX_MODULE, "module.py")

    outcome = DocstringFormatter().format_file(path)

    assert outcome.final_content == outcome.original_content
    assert not outcome.docstrings_reformatted


def test_formatting_a_file_does_not_write_it(copy_into_temporary_directory) -> None:
    path = copy_into_temporary_directory(DatasetFile.UNFORMATTED_MODULE, "module.py")

    DocstringFormatter().format_file(path)

    assert path.read_text() == DatasetFile.UNFORMATTED_MODULE.value.read_text()


# %% command line


def test_format_command_writes_changes_and_reports_failure(
    copy_into_temporary_directory,
) -> None:
    path = copy_into_temporary_directory(DatasetFile.UNFORMATTED_MODULE, "module.py")

    exit_status = CommandLine.main([Subcommand.FORMAT, str(path)])

    assert exit_status == ExitStatus.FAILURE
    assert path.read_text() == DatasetFile.FORMATTED_MODULE.value.read_text()


def test_format_command_succeeds_on_formatted_files(
    copy_into_temporary_directory,
) -> None:
    path = copy_into_temporary_directory(DatasetFile.FORMATTED_MODULE, "module.py")

    exit_status = CommandLine.main([Subcommand.FORMAT, str(path)])

    assert exit_status == ExitStatus.SUCCESS
    assert path.read_text() == DatasetFile.FORMATTED_MODULE.value.read_text()
