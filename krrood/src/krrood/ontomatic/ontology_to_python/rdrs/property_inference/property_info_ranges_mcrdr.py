from ripple_down_rules.helpers import (
    update_case_and_conclusions_with_rule_output,
)
from ripple_down_rules.utils import copy_case
from ripple_down_rules.datastructures.case import Case, create_case
from typing_extensions import Set

from .property_info_ranges_mcrdr_defs import *
from ...ontology_info import PropertyInfo

attribute_name = "ranges"
conclusion_type = (
    set,
    str,
    list,
)
mutually_exclusive = False
name = "ranges"
case_type = PropertyInfo
case_name = "PropertyInfo"


def classify(case: PropertyInfo, **kwargs) -> Set[str]:
    if not isinstance(case, Case):
        case = create_case(case, max_recursion_idx=3)
    else:
        case = copy_case(case)
    conclusions = set()

    if conditions_16387116833966311081044051350807017204(case):
        update_case_and_conclusions_with_rule_output(
            case,
            conclusions,
            conclusion_16387116833966311081044051350807017204(case),
            attribute_name,
            conclusion_type,
            mutually_exclusive,
        )

    if conditions_278968314445449186927647948203137055838(case):
        update_case_and_conclusions_with_rule_output(
            case,
            conclusions,
            conclusion_278968314445449186927647948203137055838(case),
            attribute_name,
            conclusion_type,
            mutually_exclusive,
        )

    if conditions_289449543556339629720445623912622786519(case):
        update_case_and_conclusions_with_rule_output(
            case,
            conclusions,
            conclusion_289449543556339629720445623912622786519(case),
            attribute_name,
            conclusion_type,
            mutually_exclusive,
        )

    if conditions_185021833760373592529284117887051484781(case):
        update_case_and_conclusions_with_rule_output(
            case,
            conclusions,
            conclusion_185021833760373592529284117887051484781(case),
            attribute_name,
            conclusion_type,
            mutually_exclusive,
        )

    if conditions_276827957023682938371215336609099145051(case):
        update_case_and_conclusions_with_rule_output(
            case,
            conclusions,
            conclusion_276827957023682938371215336609099145051(case),
            attribute_name,
            conclusion_type,
            mutually_exclusive,
        )
    return conclusions
