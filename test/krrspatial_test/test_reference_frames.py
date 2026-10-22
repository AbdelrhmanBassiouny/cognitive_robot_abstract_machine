from __future__ import annotations

import pytest

from krrood.patterns.exceptions import InterfaceInstantiationError
from krrspatial.exceptions import MissingReferenceFrameResolver
from krrspatial.reference_frame import ReferenceFrame, ReferenceFrameReference

from .dataset.frames import KnownFrames

# %% the frame interface


def test_a_reference_frame_cannot_be_instantiated():
    with pytest.raises(InterfaceInstantiationError):
        ReferenceFrame()


# %% referring to a frame in a serialized value


def test_a_reference_resolves_to_the_readers_frame(table_frame):
    reference = ReferenceFrameReference("reference_frame")
    data = {}
    reference.write(data, table_frame)
    known_frames = KnownFrames()
    known_frames.add(table_frame.id, table_frame)

    assert reference.resolve(data, **known_frames.create_kwargs()) is table_frame


def test_a_reference_cannot_be_resolved_without_a_resolver(table_frame):
    reference = ReferenceFrameReference("reference_frame")
    data = {}
    reference.write(data, table_frame)

    with pytest.raises(MissingReferenceFrameResolver):
        reference.resolve(data)
