from __future__ import annotations

import sys
import uuid
from dataclasses import dataclass, is_dataclass, make_dataclass, field
from functools import lru_cache

from pandas import DataFrame
from typing_extensions import Any, Optional, Dict, Type, List, TYPE_CHECKING, Tuple

from ..utils import table_rows_as_str, is_iterable, dataclass_to_dict
from ...symbol_graph.symbol_graph import Symbol

if TYPE_CHECKING:
    from ..rules import Rule


@dataclass
class GeneratedClass(Symbol):
    """
    A base class for generated dataclasses.
    """


@dataclass
class DataFrameGeneratedClass(GeneratedClass):
    """
    A dataclass generated from a pandas DataFrame.
    """
    row_id: int

    def __hash__(self):
        return self.row_id

    def __eq__(self, other):
        return isinstance(other, DataFrameGeneratedClass) and self.row_id == other.row_id


@dataclass
class HasUUID(GeneratedClass):
    """
    A dataclass that has an _id_ attribute of type UUID and implements __hash__ and __eq__.
    """
    _id_: uuid.UUID = field(init=False, default_factory=uuid.uuid4, repr=False)

    def __hash__(self):
        return hash(self._id_)

    def __eq__(self, other):
        return isinstance(other, HasUUID) and self._id_ == other._id_


def create_cases_from_dataframe(df: DataFrame, name: str) -> List[DataFrameGeneratedClass]:
    """
    Create cases from a pandas DataFrame.

    :param df: The DataFrame to create cases from.
    :param name: The name of the new dataclass that will be instantiated for each row of the DataFrame.
    :return: The cases of the DataFrame.
    """
    cases = []
    attribute_names = list(df.columns)
    for row_id, case in df.iterrows():
        case = {col_name: case[col_name].item() for col_name in attribute_names}
        case["row_id"] = row_id
        cases.append(create_dataclass_and_instance_from_dictionary(case, name, (DataFrameGeneratedClass,)))
    return cases


def create_dataclass_and_instance_from_dictionary(data: Dict[str, Any], name: str, bases: Tuple[Type, ...] = ()):
    """
    Create a dataclass from a dictionary if the dataclass does not exist yet. If the dataclass already exists, it will
    return an instance of the existing dataclass. Otherwise, it will create a new dataclass and instance.

    :param data: The dictionary to create a dataclass and instance from.
    :param name: The name of the dataclass.
    :param bases: The base classes of the dataclass.
    :return: The dataclass instance that was created from the dictionary.
    """
    module = sys.modules[__name__]

    if hasattr(module, name):
        existing_class = getattr(module, name)
        return existing_class(**data)

    new_fields = get_field_definitions_from_dictionary(data, bases)
    if not bases:
        bases = (HasUUID,)
    else:
        bases = (GeneratedClass, *bases)
    new_class =  make_dataclass(name, new_fields, bases=bases, eq=False, kw_only=True, module=__name__)
    setattr(module, name, new_class)
    return new_class(**data)


def get_field_definitions_from_dictionary(data: Dict[str, Any], bases: Tuple[Type, ...] = ()):
    """
    :param data: The dictionary to construct the field definitions from.
    :param bases: The tuple of base classes to use for the new dataclass.
    :return: A list of tuples containing the field definitions.
    """
    all_attributes_of_all_bases = get_all_attributes_of_classes(bases)
    new_fields: List[Tuple[str, Type, Any]] = []
    for attr_name, value in data.items():
        if attr_name in all_attributes_of_all_bases:
            continue
        value_type = type(value) if value is not None else Any
        if is_iterable(value):
            new_fields.append((attr_name, value_type[type(next(value, Any))], field(default_factory=value_type)))
        else:
            new_fields.append((attr_name, value_type, field(default=None)))
    return new_fields


@lru_cache
def get_all_attributes_of_classes(classes: Tuple[Type, ...]) -> Tuple[str, ...]:
    """
    :param classes: a tuple of classes.
    :return: a tuple of all attributes of all classes.
    """
    all_attributes_of_all_bases = []
    for base in classes:
        all_attributes_of_all_bases.extend(dir(base))
    return tuple(all_attributes_of_all_bases)


def show_current_and_corner_cases(case: Any, targets: Optional[Dict[str, Any]] = None,
                                  current_conclusions: Optional[Dict[str, Any]] = None,
                                  last_evaluated_rule: Optional[Rule] = None) -> str:
    """
    Get the data to show of the new case and if last evaluated rule exists also show that of the corner case.

    :param case: The new case.
    :param targets: The target attribute of the case.
    :param current_conclusions: The current conclusions of the case.
    :param last_evaluated_rule: The last evaluated rule in the RDR.
    :return: The information to show as a string.
    """
    if not is_dataclass(case):
        raise ValueError(f"Case {case} is not a dataclass.")

    targets = {f"target_{name}": value for name, value in targets.items()} if targets else {}
    current_conclusions = {name: value for name, value in current_conclusions.items()} if current_conclusions else {}
    information = ""
    if last_evaluated_rule:
        action = "Refinement" if last_evaluated_rule.fired else "Alternative"
        information += f"{action} needed for rule: {last_evaluated_rule}\n"

    corner_row_dict = None
    case_dict = dataclass_to_dict(case)
    if last_evaluated_rule and last_evaluated_rule.fired:
        corner_row_dict = dataclass_to_dict(last_evaluated_rule.corner_case)

    case_dict.update(targets)
    case_dict.update(current_conclusions)
    all_table_rows = [case_dict]
    if corner_row_dict:
        corner_conclusion = last_evaluated_rule.conclusion(case)
        corner_row_dict.update({corner_conclusion.__class__.__name__: corner_conclusion})
        all_table_rows.append(corner_row_dict)

    information += "\n" + "=" * 50 + "\n"
    information += "\n" + table_rows_as_str(all_table_rows) + "\n"
    return information
