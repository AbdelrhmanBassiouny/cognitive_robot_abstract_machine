from sqlalchemy import inspect

from ..dataset.example_classes import HoldsAnException
from ..dataset.ormatic_interface import HoldsAnExceptionDAO


def test_exception_field_is_left_unmapped():
    """
    A field typed with a builtin SQLAlchemy has no column type for gets no column.
    """
    mapper = inspect(HoldsAnExceptionDAO)
    assert "cause" not in mapper.columns
    assert "cause" not in mapper.relationships


def test_neighbouring_builtin_field_is_still_mapped():
    """
    Skipping the exception field leaves the rest of the class mapped.
    """
    mapper = inspect(HoldsAnExceptionDAO)
    assert "name" in mapper.columns


def test_reconstructed_object_forgets_the_exception():
    """
    An object rebuilt from its unmapped field's default carries no exception.
    """
    assert HoldsAnExceptionDAO(name="failed").from_dao() == HoldsAnException(
        name="failed"
    )
