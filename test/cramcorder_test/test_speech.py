"""
Tests for :mod:`cramcorder.speech`: sound written and read as a wave file, speech
trimmed and levelled, and the Kokoro voice kept on disk.
"""

from __future__ import annotations

import sys
import types
from datetime import timedelta
from pathlib import Path

import numpy as np
import pytest

from cramcorder.cache import SceneCache
from cramcorder.narration import Line
from cramcorder.speech import KokoroVoice, Speech

from .voices import EvenlyPacedVoice, ToneSpeechModel

RATE = 24_000
SILENCE_LEVEL = 0.01
BREATH_BEFORE = timedelta(seconds=0.03)
BREATH_AFTER = timedelta(seconds=0.12)
PEAK = 0.89


def test_speech_lasts_its_samples_over_its_rate() -> None:
    samples = 2400
    assert Speech(np.zeros(samples, dtype=np.float32), RATE).duration == timedelta(
        seconds=samples / RATE
    )


def test_sound_written_to_a_wave_file_reads_back_the_same(tmp_path: Path) -> None:
    samples = np.linspace(-1.0, 1.0, 480, dtype=np.float32)
    path = Speech(samples, RATE).written_to(tmp_path / "line.wav")
    read = Speech.read_from(path)
    assert isinstance(read, Speech)
    assert read.rate == RATE
    assert read.samples == pytest.approx(samples, abs=1e-4)


def test_speech_is_trimmed_to_its_sound_keeping_a_breath_before_and_after() -> None:
    rate = 1000
    sound_length = 1
    samples = np.zeros(3 * rate, dtype=np.float32)
    samples[rate : (1 + sound_length) * rate] = 0.5
    trimmed = Speech(samples, rate).trimmed(SILENCE_LEVEL, BREATH_BEFORE, BREATH_AFTER)
    assert isinstance(trimmed, Speech)
    assert (
        trimmed.duration
        == timedelta(seconds=sound_length) + BREATH_BEFORE + BREATH_AFTER
    )


def test_speech_with_no_sound_is_kept_whole_when_trimmed() -> None:
    silence = Speech(np.zeros(100, dtype=np.float32), 100)
    assert silence.trimmed(SILENCE_LEVEL, BREATH_BEFORE, BREATH_AFTER) is silence


def test_speech_is_levelled_so_its_loudest_sample_reaches_the_peak() -> None:
    samples = np.array([0.1, -0.25, 0.2], dtype=np.float32)
    levelled = Speech(samples, 100).levelled(PEAK)
    assert levelled.samples == pytest.approx(samples * PEAK / 0.25)


def test_silence_is_left_as_it_is_when_levelled() -> None:
    silence = Speech(np.zeros(10, dtype=np.float32), 100)
    assert silence.levelled(PEAK) is silence


def test_a_line_at_half_pace_takes_twice_as_long_to_say() -> None:
    voice = EvenlyPacedVoice()
    half_pace = 0.5
    at_its_pace = Line("one two three").spoken_by(voice)
    slowed = Line("one two three", pace=half_pace).spoken_by(voice)
    assert slowed.duration == at_its_pace.duration / half_pace


def test_the_kokoro_voice_says_a_line_at_its_pace_trimmed_and_levelled(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    speech_model = types.ModuleType("kokoro_onnx")
    speech_model.Kokoro = ToneSpeechModel
    monkeypatch.setitem(sys.modules, "kokoro_onnx", speech_model)
    voice = KokoroVoice(speed=1.0, cache=SceneCache("narration", root=tmp_path))
    half_pace = 0.5
    slowed = Line("one two", pace=half_pace).spoken_by(voice)
    at_its_pace = Line("one two").spoken_by(voice)
    breath = voice.breath_before + voice.breath_after
    tone = ToneSpeechModel.TIME_PER_WORD * 2
    tolerance = timedelta(seconds=1 / ToneSpeechModel.RATE)
    assert abs(slowed.duration - (tone / half_pace + breath)) <= tolerance
    assert abs(at_its_pace.duration - (tone + breath)) <= tolerance
    assert np.abs(slowed.samples).max() == pytest.approx(voice.peak, abs=1e-4)


def test_a_line_said_twice_is_synthesized_once(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    created = []

    class CountingModel(ToneSpeechModel):
        def create(self, text, voice, speed, lang):
            created.append(text)
            return super().create(text, voice, speed, lang)

    speech_model = types.ModuleType("kokoro_onnx")
    speech_model.Kokoro = CountingModel
    monkeypatch.setitem(sys.modules, "kokoro_onnx", speech_model)
    voice = KokoroVoice(cache=SceneCache("narration", root=tmp_path))
    line = Line("one two")
    line.spoken_by(voice)
    line.spoken_by(voice)
    assert created == [line.said]
