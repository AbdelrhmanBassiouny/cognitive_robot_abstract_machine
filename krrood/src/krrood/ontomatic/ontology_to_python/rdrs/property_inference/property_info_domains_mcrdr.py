from ripple_down_rules.helpers import (
    update_case_and_conclusions_with_rule_output,
)
from typing_extensions import Set
from ripple_down_rules.utils import copy_case
from ripple_down_rules.datastructures.case import Case, create_case
from .property_info_domains_mcrdr_defs import *
from ...ontology_info import PropertyInfo

attribute_name = "domains"
conclusion_type = (str,)
mutually_exclusive = False
name = "domains"
case_type = PropertyInfo
case_name = "PropertyInfo"


def classify(case: PropertyInfo, **kwargs) -> Set[str]:
    if not isinstance(case, Case):
        case = create_case(case, max_recursion_idx=3)
    else:
        case = copy_case(case)
    conclusions = set()

    if conditions_242528959128342177219038343241488671315(case):
        update_case_and_conclusions_with_rule_output(
            case,
            conclusions,
            conclusion_242528959128342177219038343241488671315(case),
            attribute_name,
            conclusion_type,
            mutually_exclusive,
        )

    if conditions_131862233058757724332483155067564752803(case):
        update_case_and_conclusions_with_rule_output(
            case,
            conclusions,
            conclusion_131862233058757724332483155067564752803(case),
            attribute_name,
            conclusion_type,
            mutually_exclusive,
        )

    if conditions_332303581359497817999113289006995196440(case):
        update_case_and_conclusions_with_rule_output(
            case,
            conclusions,
            conclusion_332303581359497817999113289006995196440(case),
            attribute_name,
            conclusion_type,
            mutually_exclusive,
        )

    if conditions_42929463811989244197654060026029734761(case):
        update_case_and_conclusions_with_rule_output(
            case,
            conclusions,
            conclusion_42929463811989244197654060026029734761(case),
            attribute_name,
            conclusion_type,
            mutually_exclusive,
        )

    if conditions_60381397922141724254614712707096552699(case):
        update_case_and_conclusions_with_rule_output(
            case,
            conclusions,
            conclusion_60381397922141724254614712707096552699(case),
            attribute_name,
            conclusion_type,
            mutually_exclusive,
        )

    if conditions_272707851413176399338327613086271601265(case):
        update_case_and_conclusions_with_rule_output(
            case,
            conclusions,
            conclusion_272707851413176399338327613086271601265(case),
            attribute_name,
            conclusion_type,
            mutually_exclusive,
        )
    return conclusions
