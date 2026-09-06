"""
Tests for ``RDRFileStore``: where it puts a decorated function's model file, and the
save/load lifecycle of that file.
"""

from __future__ import annotations

import dataclasses
import inspect
from pathlib import Path

import pytest

from krrood.code_generation.function_case import FunctionCaseGenerator
from krrood.entity_query_language.rdr.answer_vocabulary import AnswerName
from krrood.entity_query_language.rdr.exceptions import ModelFileMissing
from krrood.entity_query_language.rdr.expert import Expert
from krrood.entity_query_language.rdr.file_store import (
    MODELS_DIRECTORY_NAME,
    RDRFileStore,
)
from krrood.entity_query_language.rdr.function_case import FunctionCase
from krrood.entity_query_language.rdr.interface import FunctionInterface
from krrood.entity_query_language.rdr.serialization import ModelSaver, load_rdr
from krrood.entity_query_language.rdr.single_class import EQLSingleClassRDR

CONCLUSION_ATTRIBUTE_NAME = "_output"
"""
The attribute a generated :class:`FunctionCase` holds the return value in.
"""

TRAINED_CONCLUSION = 3.0
"""
The conclusion the one rule in :func:`fitted_rdr` concludes.
"""

# %% the decorated function and the RDR fitted over it


def distance(x: float, y: float) -> float:
    """
    A fully annotated function whose signature drives the generated case type.

    It stands in for a decorated function, so it is defined where one would be: at
    module level, importable by the model file the store writes.

    :param x: Distance along the first axis.
    :param y: Distance along the second axis.
    :return: The distance from the origin.
    """
    return (x**2 + y**2) ** 0.5


@pytest.fixture
def generated_case_type():
    """
    The ``Distance`` case type generated from :func:`distance`.

    The generated source is executed rather than written to a file, so a test that has
    no interest in the file does not need one.
    """
    source = FunctionCaseGenerator(base_class=FunctionCase).generate(distance)
    namespace: dict = {}
    exec(compile(source, "<generated_distance>", "exec"), namespace)
    return namespace["Distance"]


@pytest.fixture
def fitted_rdr(generated_case_type):
    """
    An RDR over the generated case type with a single rule, firing when ``x > 0``.
    """

    def answer(context, requests):
        """
        :return: The one condition the scripted expert offers for every case.
        """
        return {AnswerName.CONDITIONS: context.case_variable.x > 0}

    rdr = EQLSingleClassRDR(generated_case_type, CONCLUSION_ATTRIBUTE_NAME)
    expert = Expert(interface=FunctionInterface(answer_function=answer))
    case = generated_case_type(x=1.0, y=2.0, _output=None)
    rdr.fit_case(case, TRAINED_CONCLUSION, expert)
    return rdr


@pytest.fixture
def file_store(tmp_path):
    """
    A store writing to an absolute path under ``tmp_path``, for tests about the file
    rather than about where the file goes.
    """
    return RDRFileStore(function=distance, filename=str(tmp_path / "distance_model.py"))


# %% where the model file goes


class TestRelativeFilenameResolution:
    """
    A relative filename is resolved beside the function's module.
    """

    def test_parent_is_the_models_directory_beside_the_module(self):
        """
        The file lands in the models directory next to the function's source file.
        """
        store = RDRFileStore(function=distance, filename="model.py")
        module_directory = Path(inspect.getfile(distance)).parent
        assert Path(store.path).parent == module_directory / MODELS_DIRECTORY_NAME

    def test_name_is_the_supplied_filename(self):
        """
        Resolution changes the directory, never the filename itself.
        """
        store = RDRFileStore(function=distance, filename="my_rules.py")
        assert Path(store.path).name == "my_rules.py"


class TestAbsoluteFilenameResolution:
    """
    An absolute filename is used exactly as given.
    """

    def test_absolute_filename_is_used_verbatim(self, tmp_path):
        """
        No models directory is inserted into a path the caller already resolved.
        """
        absolute_filename = str(tmp_path / "direct_model.py")
        store = RDRFileStore(function=distance, filename=absolute_filename)
        assert store.path == absolute_filename


# %% whether the model file is there yet


class TestExistence:
    """
    ``exists`` reports whether the model file has been written.
    """

    def test_does_not_exist_before_the_first_save(self, file_store):
        """
        A store names a path; it does not create one.
        """
        assert file_store.exists() is False

    def test_exists_after_a_save(self, file_store, fitted_rdr):
        """
        Saving is what brings the file into being.
        """
        file_store.save(fitted_rdr)
        assert file_store.exists() is True


# %% writing the model file


class TestSaving:
    """
    ``save`` writes the model file, creating the directory it belongs in.
    """

    def test_missing_directory_is_created(self, fitted_rdr, tmp_path):
        """
        A save into a directory that does not exist yet creates it.
        """
        directory = tmp_path / "models_directory"
        store = RDRFileStore(function=distance, filename=str(directory / "model.py"))
        store.save(fitted_rdr)
        assert directory.is_dir()

    def test_file_is_written_at_the_resolved_path(self, file_store, fitted_rdr):
        """
        The model goes to :attr:`RDRFileStore.path` and nowhere else.
        """
        file_store.save(fitted_rdr)
        assert Path(file_store.path).is_file()

    def test_written_file_is_importable_python(self, file_store, fitted_rdr):
        """
        The file is a module, so what was saved can be read back by importing it.
        """
        file_store.save(fitted_rdr)
        compile(Path(file_store.path).read_text(), file_store.path, "exec")


# %% reading the case type back


class TestLoadingTheCaseType:
    """
    ``load_case_type`` returns the case type the saved module defines.
    """

    def test_missing_file_is_reported_as_such(self, file_store):
        """
        Loading before a save fails with the store's own error, not an import error.
        """
        with pytest.raises(ModelFileMissing):
            file_store.load_case_type()

    def test_loaded_type_is_a_function_case_subclass(self, file_store, fitted_rdr):
        """
        What comes back is a case type, ready to be instantiated and classified.
        """
        file_store.save(fitted_rdr)
        assert issubclass(file_store.load_case_type(), FunctionCase)

    def test_loaded_type_is_a_dataclass(self, file_store, fitted_rdr):
        """
        The generated case type keeps its dataclass nature across the round trip.
        """
        file_store.save(fitted_rdr)
        assert dataclasses.is_dataclass(file_store.load_case_type())

    def test_loaded_type_carries_the_functions_parameters_and_its_output(
        self, file_store, fitted_rdr
    ):
        """
        One field per annotated parameter, plus the attribute the RDR predicts.
        """
        file_store.save(fitted_rdr)
        loaded_case_type = file_store.load_case_type()
        field_names = {
            case_field.name for case_field in dataclasses.fields(loaded_case_type)
        }
        parameter_names = set(inspect.signature(distance).parameters)
        assert field_names == parameter_names | {CONCLUSION_ATTRIBUTE_NAME}


# %% saving and loading as one round trip


class TestRoundTrip:
    """
    An RDR saved through the store classifies the same way once loaded back.
    """

    def test_a_case_the_rule_covers_gets_the_trained_conclusion(
        self, file_store, fitted_rdr
    ):
        """
        The single rule fires for positive ``x``, as it did before the save.
        """
        file_store.save(fitted_rdr)
        loaded_rdr = load_rdr(file_store.path)
        case = file_store.load_case_type()(x=1.0, y=2.0, _output=None)
        assert loaded_rdr.classify(case) == pytest.approx(TRAINED_CONCLUSION)

    def test_a_case_no_rule_covers_gets_no_conclusion(self, file_store, fitted_rdr):
        """
        Negative ``x`` falls through the rule tree, as it did before the save.
        """
        file_store.save(fitted_rdr)
        loaded_rdr = load_rdr(file_store.path)
        case = file_store.load_case_type()(x=-1.0, y=2.0, _output=None)
        assert loaded_rdr.classify(case) is ...


# %% the store as the RDR's own saver


class TestStoreAsModelSaver:
    """
    The store is the saver an RDR persists through, not a second way to persist.
    """

    def test_store_is_a_model_saver(self, file_store):
        """
        Anything taking a :class:`ModelSaver` accepts a store.
        """
        assert isinstance(file_store, ModelSaver)

    def test_fitting_through_the_store_writes_the_model_file(
        self, generated_case_type, file_store
    ):
        """
        An RDR given the store persists to the store's path when a fit ends.
        """

        def answer(context, requests):
            """
            :return: The one condition the scripted expert offers for every case.
            """
            return {AnswerName.CONDITIONS: context.case_variable.x > 0}

        rdr = EQLSingleClassRDR(generated_case_type, CONCLUSION_ATTRIBUTE_NAME)
        rdr.model_saver = file_store
        expert = Expert(interface=FunctionInterface(answer_function=answer))
        rdr.fit_case(
            generated_case_type(x=1.0, y=2.0, _output=None),
            TRAINED_CONCLUSION,
            expert,
        )
        assert file_store.exists() is True
