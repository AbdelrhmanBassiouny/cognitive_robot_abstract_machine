"""
Bounding a measured quantity, and turning experiment results into the table a scientific
article presents.

The rows here are built directly rather than measured, so each test pins one property of
the presentation -- which columns a row has, and how a value of a given type is written
-- independently of what any experiment happens to measure.
"""

from __future__ import annotations

import enum
import json
import pathlib
import shutil
import subprocess
from dataclasses import dataclass

import pytest

from experiments.experiment_definitions import (
    ConfidenceInterval,
    ExperimentResult,
    ExperimentsTable,
    IncompatibleUnitConversionError,
    LatexRenderer,
    MeanAndStandardDeviation,
    NoMeasurementsError,
    PercentageBound,
    RowIsNotAnExperimentResult,
    RowsOfDifferingTypes,
    TypstRenderer,
    Unit,
    VolumeBound,
)

# %% rows the tests present


class MeasuredQuality(enum.Enum):
    """
    A property a row reports by name rather than by value.
    """

    FULLY_ESTABLISHED = "established by the experiment"
    NOT_ESTABLISHED = "left open by the experiment"


@dataclass
class NestedMeasurement(ExperimentResult):
    """
    A result reported as part of another result rather than as a row of its own.
    """

    trials: int
    """
    Number of trials the measurement was taken over.
    """


@dataclass
class MeasurementRow(ExperimentResult):
    """
    A row reporting a named quality, a quantity, and a quantity that may not have been
    established.
    """

    quality: MeasuredQuality
    """
    The quality the row reports.
    """

    score: float
    """
    The quantity measured.
    """

    unestablished_score: float | None
    """
    A quantity the experiment may have failed to establish.
    """


def rendered(*rows: ExperimentResult) -> str:
    """
    :param rows: The results to present.
    :return: The Typst markup presenting them as a table.
    """
    return TypstRenderer(ExperimentsTable(list(rows))).render_table()


def row(
    quality: MeasuredQuality = MeasuredQuality.FULLY_ESTABLISHED,
    score: float = 1.0,
    unestablished_score: float | None = 1.0,
) -> MeasurementRow:
    """
    :param quality: The quality the row reports.
    :param score: The quantity measured.
    :param unestablished_score: The quantity that may not have been established.
    :return: A row reporting those values.
    """
    return MeasurementRow(
        quality=quality, score=score, unestablished_score=unestablished_score
    )


# %% MeanAndStandardDeviation


def test_str_has_no_suffix_for_an_untagged_unit():
    value = MeanAndStandardDeviation.from_measurements([1.0, 3.0])

    assert str(value) == "2.0 ± 1.41"


def test_str_appends_the_unit_suffix():
    value = MeanAndStandardDeviation.from_measurements([1.0, 3.0], unit=Unit.SECONDS)

    assert str(value) == "2.0 ± 1.41 s"


def test_converting_seconds_to_milliseconds_scales_by_a_thousand():
    seconds = MeanAndStandardDeviation.from_measurements(
        [0.01, 0.03], unit=Unit.SECONDS
    )

    milliseconds = seconds.to(Unit.MILLISECONDS)

    assert milliseconds.mean == seconds.mean * 1000
    assert milliseconds.standard_deviation == seconds.standard_deviation * 1000
    assert milliseconds.unit is Unit.MILLISECONDS


def test_converting_an_untagged_value_is_rejected():
    value = MeanAndStandardDeviation.from_measurements([1.0, 3.0])

    with pytest.raises(IncompatibleUnitConversionError):
        value.to(Unit.MILLISECONDS)


# %% ConfidenceInterval


def test_the_interval_brackets_the_mean_by_its_standard_error():
    # five measurements of mean 3 and standard deviation 1.5811, so a standard error of
    # 0.7071, which the 95% quantile of 1.96 widens to 1.3859 on either side.
    interval = ConfidenceInterval.for_mean([1.0, 2.0, 3.0, 4.0, 5.0])

    assert interval.lower == pytest.approx(1.6141, abs=1e-4)
    assert interval.upper == pytest.approx(4.3859, abs=1e-4)


def test_a_higher_confidence_level_widens_the_interval():
    measurements = [1.0, 2.0, 3.0, 4.0, 5.0]

    almost_certain = ConfidenceInterval.for_mean(measurements, confidence_level=0.99)
    usual = ConfidenceInterval.for_mean(measurements)

    assert almost_certain.lower < usual.lower
    assert almost_certain.upper > usual.upper


def test_one_measurement_has_no_spread_to_report():
    interval = ConfidenceInterval.for_mean([4.0])

    assert interval.lower == 4.0
    assert interval.upper == 4.0


def test_an_interval_over_nothing_is_rejected():
    with pytest.raises(NoMeasurementsError):
        ConfidenceInterval.for_mean([])


# %% PercentageBound


def test_ratio_of_pairs_worst_case_ends():
    numerator = VolumeBound(lower=8.0, upper=10.0)
    denominator = VolumeBound(lower=20.0, upper=40.0)

    bound = PercentageBound.ratio_of(numerator, denominator)

    # lower: smallest numerator over largest denominator; upper: largest numerator
    # over smallest denominator.
    assert bound.lower == pytest.approx(100.0 * 8.0 / 40.0)
    assert bound.upper == pytest.approx(100.0 * 10.0 / 20.0)


def test_ratio_of_clips_at_one_hundred_percent():
    numerator = VolumeBound(lower=9.0, upper=10.0)
    denominator = VolumeBound(lower=9.0, upper=10.0)

    bound = PercentageBound.ratio_of(numerator, denominator)

    assert bound.upper == 100.0


def test_ratio_of_a_fully_covered_exact_match_is_exactly_one_hundred_percent():
    exact = VolumeBound(lower=5.0, upper=5.0)

    bound = PercentageBound.ratio_of(exact, exact)

    assert bound.lower == pytest.approx(100.0)
    assert bound.upper == pytest.approx(100.0)


# %% which columns a row has


def test_quantity_that_may_be_unestablished_is_a_column():
    """
    An experiment that cannot establish a quantity still reports the column, so a result
    is free to say a measurement is missing rather than inventing a value for it.
    """
    assert MeasurementRow.get_column_names() == [
        "quality",
        "score",
        "unestablished_score",
    ]


def test_result_reported_within_another_contributes_its_own_columns():
    """
    A result held by another is presented as part of the same row, so a table stays flat
    however the results are composed.
    """

    @dataclass
    class ComposedRow(ExperimentResult):
        """
        A row holding another result.
        """

        nested: NestedMeasurement
        """
        The result reported as part of this one.
        """

        score: float
        """
        The quantity measured.
        """

    assert ComposedRow.get_column_names() == ["trials", "score"]


# %% how a value is written


def test_named_quality_is_written_as_a_label():
    """
    A reader of the table sees the quality's name, not the notation the experiment
    happens to hold it in.
    """
    assert "[Fully Established]" in rendered(row())


def test_quantity_is_written_to_two_decimals():
    """
    A measured quantity is reported at the precision a reader can act on, rather than at
    the precision the arithmetic happened to produce.
    """
    assert "[75.71]" in rendered(row(score=75.70977917981072))


def test_unestablished_quantity_is_written_as_absent():
    """
    A quantity the experiment did not establish is marked absent, so it is never read as
    a measurement that came out at zero.
    """
    markup = rendered(row(unestablished_score=None))

    assert "[--]" in markup
    assert "[0.0]" not in markup


def test_table_presented_to_a_reader_carries_its_caption():
    """
    Every table a reader sees explains what it shows, so the figure holds the caption
    around the same table the renderer produces.
    """
    renderer = TypstRenderer(ExperimentsTable([row()]))

    figure = renderer.render_figure("What the experiment measured.")

    assert renderer.render_table() in figure
    assert "caption: [What the experiment measured.]" in figure


def test_count_keeps_its_exact_value():
    """
    A count is exact, so it is written as it is rather than as a rounded quantity.
    """
    assert "[7]" in rendered(NestedMeasurement(trials=7))


# %% the table written for a LaTeX paper

LATEX_DOCUMENT = pathlib.Path(__file__).parent / "dataset" / "latex_table_document.tex"
"""
A document that includes nothing but the table written beside it as ``table.tex``.
"""

LATEX_COMPILER = "pdflatex"
"""
The program the written table is compiled with, the one IEEE conference papers are
built with.
"""


@dataclass
class LabelledRow(ExperimentResult):
    """
    A row reporting a label of its own wording and a measurement with its spread.
    """

    label: str
    """
    What the row is about, worded freely.
    """

    duration: MeanAndStandardDeviation
    """
    The measurement and how much it varied.
    """


def labelled(label: str = "the row") -> LabelledRow:
    """
    :param label: What the row is about.
    :return: A row reporting that label and a spread measurement.
    """
    return LabelledRow(
        label=label,
        duration=MeanAndStandardDeviation(mean=1.5, standard_deviation=0.25),
    )


def test_a_latex_table_names_its_columns_between_the_rules():
    """
    The paper's tables are ruled the way the paper already rules its own, so the column
    headings sit between the top rule and the middle rule and the rows end at the bottom
    rule.
    """
    markup = LatexRenderer(ExperimentsTable([row()])).render_table()

    assert "\\toprule\nQuality & Score & Unestablished Score \\\\\n\\midrule" in markup
    assert markup.rstrip().endswith("\\bottomrule\n\\end{tabular}")


def test_a_latex_table_writes_a_row_as_its_cells():
    markup = LatexRenderer(ExperimentsTable([row(score=0.5)])).render_table()

    assert "Fully Established & 0.50 & 1.00 \\\\" in markup


def test_a_latex_table_aligns_a_number_right_and_words_left():
    markup = LatexRenderer(ExperimentsTable([row()])).render_table()

    assert "\\begin{tabular}{@{}lrr@{}}" in markup


def test_a_latex_cell_escapes_what_latex_reads_as_markup():
    """
    A label is written as it reads, so a character LaTeX would take for markup is
    escaped rather than breaking the table.
    """
    markup = LatexRenderer(
        ExperimentsTable([labelled("50% of a_b & c")])
    ).render_table()

    assert "50\\% of a\\_b \\& c" in markup


def test_a_spread_is_written_with_the_latex_plus_minus():
    markup = LatexRenderer(ExperimentsTable([labelled()])).render_table()

    assert "%s $\\pm$ %s" % (1.5, 0.25) in markup


def test_a_latex_table_presented_to_a_reader_carries_its_caption_and_label():
    renderer = LatexRenderer(ExperimentsTable([row()]))

    table = renderer.render_figure("What 50% of it measured.", "tab:measured")

    assert renderer.render_table() in table
    assert "\\caption{What 50\\% of it measured.}" in table
    assert "\\label{tab:measured}" in table


@pytest.mark.skipif(
    shutil.which(LATEX_COMPILER) is None, reason="%s is not installed" % LATEX_COMPILER
)
def test_a_latex_table_presented_to_a_reader_compiles(tmp_path: pathlib.Path):
    (tmp_path / "table.tex").write_text(
        LatexRenderer(
            ExperimentsTable([row(), row(quality=MeasuredQuality.NOT_ESTABLISHED)])
        ).render_figure("What 50% of it measured.", "tab:measured")
    )
    shutil.copy(LATEX_DOCUMENT, tmp_path / LATEX_DOCUMENT.name)

    compiled = subprocess.run(
        [
            LATEX_COMPILER,
            "-interaction=nonstopmode",
            "-halt-on-error",
            LATEX_DOCUMENT.name,
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )

    assert compiled.returncode == 0, compiled.stdout


# %% recording the results alongside the table


def test_manifest_records_every_row_in_a_readable_form(tmp_path: pathlib.Path):
    """
    The manifest records what the table presents, with values written in a form that
    survives being read back rather than in the notation the experiment held them in.
    """
    table = ExperimentsTable(
        [row(score=0.5), row(quality=MeasuredQuality.NOT_ESTABLISHED)]
    )

    manifest_path = table.write_manifest(tmp_path, "results.json")

    recorded = json.loads(manifest_path.read_text())
    assert [each["quality"] for each in recorded] == [
        "FULLY_ESTABLISHED",
        "NOT_ESTABLISHED",
    ]
    assert recorded[0]["score"] == 0.5


def test_manifest_records_a_nested_result_flat(tmp_path: pathlib.Path):
    """
    The manifest records the columns the table presents, so a result reported within another
    appears under its own columns rather than nested inside the field holding it.
    """

    @dataclass
    class ComposedRow(ExperimentResult):
        """
        A row holding another result.
        """

        nested: NestedMeasurement
        """
        The result reported as part of this one.
        """

        score: float
        """
        The quantity measured.
        """

    manifest_path = ExperimentsTable(
        [ComposedRow(nested=NestedMeasurement(trials=7), score=0.5)]
    ).write_manifest(tmp_path, "results.json")

    [recorded] = json.loads(manifest_path.read_text())
    assert recorded == {"trials": 7, "score": 0.5}


def test_manifest_keeps_an_unestablished_measurement_distinguishable(
    tmp_path: pathlib.Path,
):
    """
    A measurement the experiment did not establish is recorded as absent, so reading the
    manifest back never turns it into a value that was measured.
    """
    manifest_path = ExperimentsTable([row(unestablished_score=None)]).write_manifest(
        tmp_path, "results.json"
    )

    [recorded] = json.loads(manifest_path.read_text())
    assert recorded["unestablished_score"] is None


def test_manifest_records_a_measurement_reported_as_a_spread(tmp_path: pathlib.Path):
    """
    A value a row reports through a class of its own is recorded by its parts, so the
    manifest holds what was measured rather than the notation it was held in.
    """

    @dataclass
    class SpreadRow(ExperimentResult):
        """
        A row reporting a measurement as a mean and a spread around it.
        """

        duration: MeanAndStandardDeviation
        """
        The measurement and how much it varied.
        """

    manifest_path = ExperimentsTable(
        [
            SpreadRow(
                duration=MeanAndStandardDeviation(
                    mean=1.5, standard_deviation=0.25, unit=Unit.SECONDS
                )
            )
        ]
    ).write_manifest(tmp_path, "results.json")

    [recorded] = json.loads(manifest_path.read_text())
    assert recorded["duration"] == {
        "mean": 1.5,
        "standard_deviation": 0.25,
        "unit": "SECONDS",
    }


def test_manifest_records_several_measurements_of_one_column(tmp_path: pathlib.Path):
    """
    A column holding several measurements records each of them, so a row reporting a
    series is read back as that series.
    """

    @dataclass
    class SeriesRow(ExperimentResult):
        """
        A row reporting the measurements a trial produced.
        """

        durations: list[float]
        """
        Every measurement taken.
        """

    manifest_path = ExperimentsTable([SeriesRow(durations=[0.5, 1.5])]).write_manifest(
        tmp_path, "results.json"
    )

    [recorded] = json.loads(manifest_path.read_text())
    assert recorded["durations"] == [0.5, 1.5]


# %% tables the renderer refuses


def test_rows_of_differing_types_are_refused():
    """
    A table's columns come from its row type, so rows of different types have no common
    set of columns and are refused rather than presented under the first row's headers.
    """
    with pytest.raises(RowsOfDifferingTypes):
        ExperimentsTable([row(), NestedMeasurement(trials=1)])


def test_rows_that_are_not_results_are_refused():
    """
    A row is refused when it reports no columns at all, rather than failing later while
    the table is being written.
    """
    with pytest.raises(RowIsNotAnExperimentResult):
        ExperimentsTable([MeasuredQuality.FULLY_ESTABLISHED])
