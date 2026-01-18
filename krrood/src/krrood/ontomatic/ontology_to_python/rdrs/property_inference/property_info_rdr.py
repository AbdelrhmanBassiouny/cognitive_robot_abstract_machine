from ripple_down_rules.datastructures.case import Case, create_case
from ...owl_to_python import PropertyInfo
from typing_extensions import Any, Dict
from ripple_down_rules.helpers import general_rdr_classify
from . import property_info_domains_mcrdr as domains_classifier
from . import property_info_ranges_mcrdr as ranges_classifier

name = "domains"
case_type = PropertyInfo
case_name = "PropertyInfo"
classifiers_dict = dict()
classifiers_dict["domains"] = domains_classifier
classifiers_dict["ranges"] = ranges_classifier


def classify(case: PropertyInfo, **kwargs) -> Dict[str, Any]:
    if not isinstance(case, Case):
        case = create_case(case, max_recursion_idx=3)
    return general_rdr_classify(classifiers_dict, case, **kwargs)
