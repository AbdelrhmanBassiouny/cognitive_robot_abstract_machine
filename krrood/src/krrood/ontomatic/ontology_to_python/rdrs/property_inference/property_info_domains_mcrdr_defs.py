from typing_extensions import List
from ...owl_to_python import PropertyInfo
from ripple_down_rules import *


def conditions_242528959128342177219038343241488671315(case) -> bool:
    def conditions_for_property_info_domains_of_type(case: PropertyInfo) -> bool:
        """Get conditions on whether it's possible to conclude a value for PropertyInfo.domains  of type ."""
        return len(case.onto.original_properties[case.name].domains) > 0

    return conditions_for_property_info_domains_of_type(case)


def conclusion_242528959128342177219038343241488671315(case) -> List[str]:
    def property_info_domains_of_type(case: PropertyInfo) -> List[str]:
        """Get possible value(s) for PropertyInfo.domains  of type ."""
        return case.domains

    return property_info_domains_of_type(case)


def conditions_131862233058757724332483155067564752803(case) -> bool:
    def conditions_for_property_info_domains_of_type(case: PropertyInfo) -> bool:
        """Get conditions on whether it's possible to conclude a value for PropertyInfo.domains  of type ."""
        return len(case.equivalent_properties) == 1

    return conditions_for_property_info_domains_of_type(case)


def conclusion_131862233058757724332483155067564752803(case) -> List[str]:
    def property_info_domains_of_type(case: PropertyInfo) -> List[str]:
        """Get possible value(s) for PropertyInfo.domains  of type ."""
        return case.onto.properties[case.equivalent_properties[0]].domains

    return property_info_domains_of_type(case)


def conditions_332303581359497817999113289006995196440(case) -> bool:
    def conditions_for_property_info_domains_of_type(case: PropertyInfo) -> bool:
        """Get conditions on whether it's possible to conclude a value for PropertyInfo.domains  of type ."""
        return len(case.inverses) == 1

    return conditions_for_property_info_domains_of_type(case)


def conclusion_332303581359497817999113289006995196440(case) -> List[str]:
    def property_info_domains_of_type(case: PropertyInfo) -> List[str]:
        """Get possible value(s) for PropertyInfo.domains  of type ."""
        return case.onto.properties[case.inverses[0]].ranges

    return property_info_domains_of_type(case)


def conditions_42929463811989244197654060026029734761(case) -> bool:
    def conditions_for_property_info_domains_of_type(case: PropertyInfo) -> bool:
        """Get conditions on whether it's possible to conclude a value for PropertyInfo.domains  of type ."""
        return (
            (
                len(case.inverses) == 0
                or all(
                    len(case.onto.original_properties[i].ranges) == 0
                    for i in case.inverses
                )
            )
            and len(case.onto.original_properties[case.name].domains) == 0
            and len(case.superproperties) > 0
        )

    return conditions_for_property_info_domains_of_type(case)


def conclusion_42929463811989244197654060026029734761(case) -> List[str]:
    def property_info_domains_of_type(case: PropertyInfo) -> List[str]:
        """Get possible value(s) for PropertyInfo.domains  of type ."""
        domains = set()
        for sp in case.superproperties:
            domains.update(set(case.onto.properties[sp].domains))
        return list(domains)

    return property_info_domains_of_type(case)


def conditions_60381397922141724254614712707096552699(case) -> bool:
    def conditions_for_property_info_domains_of_type(case: PropertyInfo) -> bool:
        """Get conditions on whether it's possible to conclude a value for PropertyInfo.domains  of type ."""
        return (
            len(case.onto.original_properties[case.name].domains) == 0
            and len(case.superproperties) == 0
            and len(case.inverses) == 0
            and len(case.equivalent_properties) == 0
        )

    return conditions_for_property_info_domains_of_type(case)


def conclusion_60381397922141724254614712707096552699(case) -> List[str]:
    def property_info_domains_of_type(case: PropertyInfo) -> List[str]:
        """Get possible value(s) for PropertyInfo.domains  of type ."""
        return case.onto.base_cls_name

    return property_info_domains_of_type(case)


def conditions_272707851413176399338327613086271601265(case) -> bool:
    def conditions_for_property_info_domains_of_type(case: PropertyInfo) -> bool:
        """Get conditions on whether it's possible to conclude a value for PropertyInfo.domains  of type ."""
        return (
            len(case.onto.original_properties[case.name].domains) == 0
            and (
                len(case.inverses) == 0
                or all(
                    len(case.onto.original_properties[i].ranges) == 0
                    for i in case.inverses
                )
            )
            and len(case.equivalent_properties) == 0
        )

    return conditions_for_property_info_domains_of_type(case)


def conclusion_272707851413176399338327613086271601265(case) -> List[str]:
    def property_info_domains_of_type(case: PropertyInfo) -> List[str]:
        """Get possible value(s) for PropertyInfo.domains  of type ."""
        domains = []
        for sp in reversed(case.sorted_superproperties):
            if len(case.onto.original_properties[sp].domains) > 0:
                domains.extend(case.onto.original_properties[sp].domains)
                break
        return domains

    return property_info_domains_of_type(case)
