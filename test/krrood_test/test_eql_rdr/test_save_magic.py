"""
Tests for the on-demand ``%save`` magic.

The magic persists the model through the RDR's own
:class:`~krrood.entity_query_language.rdr.serialization.ModelSaver`: what a model does
with its own state is the RDR's concern, so the shell only asks for it. The saver
strategies themselves are covered where they live, in ``test_serialization.py`` and
``test_fit_convergence.py``.
"""

import contextlib
import io
import unittest

from krrood.entity_query_language.rdr.interactive import IPythonInterface, Palette
from krrood.entity_query_language.rdr.magics import _make_save_magic
from krrood.entity_query_language.rdr.single_class import EQLSingleClassRDR

from .animal import Animal
from .test_fit_convergence import RecordingModelSaver


def _palette() -> Palette:
    """:return: A colourless palette, so assertions read the text and not the escapes."""
    return Palette(use_color=False)


# %% the magic persists through the RDR's saver


class TestSaveMagicPersistsThroughTheModelSaver(unittest.TestCase):
    """
    ``%save`` is a thin adapter over the RDR's saver: it saves the *model*, so the model
    is what it asks.
    """

    def test_magic_asks_the_rdrs_saver_to_persist_it(self):
        """
        The saver is handed the very RDR the interface is attached to.
        """
        saver = RecordingModelSaver()
        rdr = EQLSingleClassRDR(Animal, "species", model_saver=saver)
        magic = _make_save_magic(IPythonInterface(rdr=rdr), _palette())

        magic("")

        self.assertEqual(saver.saved, [rdr])

    def test_magic_saves_once_per_invocation(self):
        """
        Each ``%save`` is one save; the magic keeps no state of its own.
        """
        saver = RecordingModelSaver()
        rdr = EQLSingleClassRDR(Animal, "species", model_saver=saver)
        magic = _make_save_magic(IPythonInterface(rdr=rdr), _palette())

        magic("")
        magic("")

        self.assertEqual(saver.saved, [rdr, rdr])

    def test_magic_ignores_its_line_argument(self):
        """
        ``%save`` takes no argument; anything typed after it is not a saver path.
        """
        saver = RecordingModelSaver()
        rdr = EQLSingleClassRDR(Animal, "species", model_saver=saver)
        magic = _make_save_magic(IPythonInterface(rdr=rdr), _palette())

        magic("ignored line argument")

        self.assertEqual(saver.saved, [rdr])

    def test_magic_sees_an_rdr_attached_after_it_was_built(self):
        """
        The magic closes over the interface, so an RDR attached later is still saved.
        """
        saver = RecordingModelSaver()
        rdr = EQLSingleClassRDR(Animal, "species", model_saver=saver)
        interface = IPythonInterface()
        magic = _make_save_magic(interface, _palette())

        interface.rdr = rdr
        magic("")

        self.assertEqual(saver.saved, [rdr])


# %% the magic with no model to save


class TestSaveMagicWithoutAnRDR(unittest.TestCase):
    """
    A shell used without an RDR has nothing to persist, and says so rather than raising
    — the expert is mid-session and the shell must stay open.
    """

    def test_magic_prints_a_hint_when_no_model_is_attached(self):
        """
        The magic says there is nothing to save rather than raising.
        """
        magic = _make_save_magic(IPythonInterface(), _palette())
        printed = io.StringIO()

        with contextlib.redirect_stdout(printed):
            magic("")

        self.assertIn("No model is attached", printed.getvalue())


if __name__ == "__main__":
    unittest.main()
