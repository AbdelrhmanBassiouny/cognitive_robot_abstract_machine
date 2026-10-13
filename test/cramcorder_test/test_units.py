"""
Tests for :mod:`cramcorder.units`: amounts of data and how fast they flow.
"""

from __future__ import annotations

from datetime import timedelta

from cramcorder.units import BitRate, DataSize

TEN_SECONDS = timedelta(seconds=10)

# %% amounts of data


def test_a_byte_is_eight_bits() -> None:
    assert DataSize.of_bytes(3) == DataSize(3 * DataSize.bits_per_byte)
    assert DataSize(3 * DataSize.bits_per_byte).bytes == 3


def test_amounts_of_data_add_subtract_and_compare() -> None:
    small, large = DataSize(100), DataSize(250)
    assert small + large == DataSize(350)
    assert large - small == DataSize(150)
    assert small < large


def test_an_amount_of_data_scales_to_the_nearest_bit() -> None:
    assert DataSize(10).scaled(0.25) == DataSize(2)


# %% rates


def test_a_bit_rate_over_a_duration_is_the_data_that_flows_in_it() -> None:
    assert BitRate(DataSize(8_000)).over(TEN_SECONDS) == DataSize(80_000)


def test_the_rate_filling_an_amount_in_a_duration_flows_that_amount_in_it() -> None:
    amount = DataSize.of_bytes(1_000)
    assert BitRate.filling(amount, TEN_SECONDS).over(TEN_SECONDS) == amount


def test_a_scaled_rate_is_still_a_bit_rate() -> None:
    scaled = BitRate(DataSize(1_000)).scaled(1.5)
    assert scaled == BitRate(DataSize(1_500))
    assert isinstance(scaled, BitRate)
