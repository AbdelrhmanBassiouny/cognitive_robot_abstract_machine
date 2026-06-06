"""Unit tests for the ProgressReporter abstraction in progress.py.

Tests cover:
    - Abstract base class contract (cannot instantiate, must override all four)
    - IPythonProgressBar tqdm wrapping (creation, update, reset, finish, no-colour mode)
    - SpyProgressReporter test-double call recording
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from krrood.entity_query_language.rdr.progress import (
    IPythonProgressBar,
    ProgressReporter,
    SpyProgressReporter,
)


# -- ABC contract ----------------------------------------------------------


class TestProgressReporterProtocol:
    """Verify the abstract interface contract of ProgressReporter."""

    def test_cannot_instantiate_abc_directly(self) -> None:
        """ProgressReporter is abstract and cannot be instantiated directly."""
        with pytest.raises(TypeError, match="Can't instantiate abstract class"):
            ProgressReporter()

    def test_subclass_must_implement_all_four_abstract_methods(self) -> None:
        """A subclass that omits any abstract method still cannot be instantiated."""
        class MissingMethods(ProgressReporter):
            pass

        with pytest.raises(TypeError, match="Can't instantiate abstract class"):
            MissingMethods()


# -- IPythonProgressBar (tqdm wrapper) ------------------------------------


class TestIPythonProgressBar:
    """Tests for the tqdm-wrapping concrete progress reporter.

    All tests patch ``tqdm.tqdm`` so no real progress bar is created.
    The mock lets us verify construction arguments and lifecycle calls.
    """

    # -- construction -------------------------------------------------------

    @patch("tqdm.tqdm")
    def test_start_creates_tqdm_bar(
        self, mock_tqdm: MagicMock
    ) -> None:
        """start(total, description) creates a tqdm.tqdm with the expected kwargs."""
        bar = IPythonProgressBar()
        bar.start(10, "test")

        mock_tqdm.assert_called_once_with(
            total=10,
            desc="test",
            colour="green",
            ascii=False,
            unit="case",
            leave=True,
            dynamic_ncols=True,
        )

    # -- lifecycle ----------------------------------------------------------

    @patch("tqdm.tqdm")
    def test_update_increments_counter(self, mock_tqdm: pytest.MagicMock) -> None:
        """Calling update(n) delegates to tqdm.update(n) on the underlying bar."""
        bar = IPythonProgressBar()
        bar.start(10)
        bar.update(3)

        mock_tqdm.return_value.update.assert_called_once_with(3)

    @patch("tqdm.tqdm")
    def test_update_defaults_to_one(self, mock_tqdm: pytest.MagicMock) -> None:
        """Calling update() with no argument advances by 1."""
        bar = IPythonProgressBar()
        bar.start(10)
        bar.update()

        mock_tqdm.return_value.update.assert_called_once_with(1)

    @patch("tqdm.tqdm")
    def test_reset_adjusts_total(self, mock_tqdm: pytest.MagicMock) -> None:
        """reset(total) delegates to tqdm.reset(total) on the underlying bar."""
        bar = IPythonProgressBar()
        bar.start(10)
        bar.update(5)
        bar.reset(8)

        mock_tqdm_instance = mock_tqdm.return_value
        # update and reset should both have been called on the same instance
        mock_tqdm_instance.update.assert_called_once_with(5)
        mock_tqdm_instance.reset.assert_called_once_with(8)

    @patch("tqdm.tqdm")
    def test_finish_closes_bar(self, mock_tqdm: pytest.MagicMock) -> None:
        """finish() closes the tqdm bar and sets _progress_bar to None."""
        bar = IPythonProgressBar()
        bar.start(10)
        bar.finish()

        mock_tqdm.return_value.close.assert_called_once_with()
        assert bar._progress_bar is None

    @patch("tqdm.tqdm")
    def test_start_replaces_old_bar(self, mock_tqdm: pytest.MagicMock) -> None:
        """Calling start() a second time creates a fresh tqdm instance without
        closing the previous one (the old bar is simply replaced)."""
        bar = IPythonProgressBar()
        bar.start(10)
        first_instance = mock_tqdm.return_value

        bar.start(20)

        # tqdm.tqdm was called twice, producing two different instances
        assert mock_tqdm.call_count == 2
        # the old instance was NOT closed by start
        first_instance.close.assert_not_called()

    # -- no-colour mode -----------------------------------------------------

    @patch("tqdm.tqdm")
    def test_no_color_mode(self, mock_tqdm: pytest.MagicMock) -> None:
        """When use_color is False, pass ascii=True and colour=None to tqdm."""
        bar = IPythonProgressBar(use_color=False)
        bar.start(10, "test")

        mock_tqdm.assert_called_once_with(
            total=10,
            desc="test",
            colour=None,
            ascii=True,
            unit="case",
            leave=True,
            dynamic_ncols=True,
        )

    # -- safety with missing _progress_bar ------------------------------------------

    def test_update_before_start_is_safe(self) -> None:
        """Calling update() without a prior start() does not raise."""
        bar = IPythonProgressBar()
        # _progress_bar is None — should be a no-op
        bar.update()
        bar.update(5)

    def test_reset_before_start_is_safe(self) -> None:
        """Calling reset() without a prior start() does not raise."""
        bar = IPythonProgressBar()
        bar.reset(10)

    def test_finish_twice_is_safe(self) -> None:
        """Calling finish() twice does not raise (idempotent close)."""
        bar = IPythonProgressBar()
        bar.start(10)
        bar.finish()
        # second finish should be a no-op (_progress_bar is already None)
        bar.finish()


# -- SpyProgressReporter (test double) -----------------------------------


class TestSpyProgressReporter:
    """Tests for the SpyProgressReporter test double.

    Each test verifies that the correct (method_name, args, kwargs) tuple is
    appended to ``self.events``.
    """

    def test_spy_records_start(self) -> None:
        """start(total, description) records (\"start\", (total,), {\"description\": ...})."""
        spy = SpyProgressReporter()
        spy.start(5, "fitting")

        assert spy.events == [("start", (5,), {"description": "fitting"})]

    def test_spy_records_update_default(self) -> None:
        """update() records (\"update\", (1,), {})."""
        spy = SpyProgressReporter()
        spy.update()

        assert spy.events == [("update", (1,), {})]

    def test_spy_records_update_with_n(self) -> None:
        """update(3) records (\"update\", (3,), {})."""
        spy = SpyProgressReporter()
        spy.update(3)

        assert spy.events == [("update", (3,), {})]

    def test_spy_records_reset(self) -> None:
        """reset(total) records (\"reset\", (total,), {})."""
        spy = SpyProgressReporter()
        spy.reset(8)

        assert spy.events == [("reset", (8,), {})]

    def test_spy_records_finish(self) -> None:
        """finish() records (\"finish\", (), {})."""
        spy = SpyProgressReporter()
        spy.finish()

        assert spy.events == [("finish", (), {})]

    def test_spy_accumulates_events(self) -> None:
        """Multiple lifecycle calls are appended in order."""
        spy = SpyProgressReporter()
        spy.start(5)
        spy.update()
        spy.reset(3)
        spy.finish()

        assert spy.events == [
            ("start", (5,), {"description": ""}),
            ("update", (1,), {}),
            ("reset", (3,), {}),
            ("finish", (), {}),
        ]
