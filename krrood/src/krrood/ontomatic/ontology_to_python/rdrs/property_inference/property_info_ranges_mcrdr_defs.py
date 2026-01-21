from typing_extensions import List
from ...owl_to_python import PropertyInfo
from ripple_down_rules import *


def conditions_16387116833966311081044051350807017204(case) -> bool:
    def conditions_for_property_info_ranges_of_type(case: PropertyInfo) -> bool:
        """Get conditions on whether it's possible to conclude a value for PropertyInfo.ranges  of type ."""
        return len(case.onto.original_properties[case.name].ranges) > 0

    return conditions_for_property_info_ranges_of_type(case)


def conclusion_16387116833966311081044051350807017204(case) -> List[str]:
    def property_info_ranges_of_type(case: PropertyInfo) -> List[str]:
        """Get possible value(s) for PropertyInfo.ranges  of type ."""
        return case.ranges

    return property_info_ranges_of_type(case)


def conditions_278968314445449186927647948203137055838(case) -> bool:
    def conditions_for_property_info_ranges_of_type(case: PropertyInfo) -> bool:
        """Get conditions on whether it's possible to conclude a value for PropertyInfo.ranges  of type ."""
        return len(case.equivalent_properties) > 0

    return conditions_for_property_info_ranges_of_type(case)


def conclusion_278968314445449186927647948203137055838(case) -> List[str]:
    def property_info_ranges_of_type(case: PropertyInfo) -> List[str]:
        """Get possible value(s) for PropertyInfo.ranges  of type ."""
        return case.onto.properties[case.equivalent_properties[0]].ranges

    return property_info_ranges_of_type(case)


def conditions_289449543556339629720445623912622786519(case) -> bool:
    def conditions_for_property_info_ranges_of_type(case: PropertyInfo) -> bool:
        """Get conditions on whether it's possible to conclude a value for PropertyInfo.ranges  of type ."""
        return len(case.inverses) > 0

    return conditions_for_property_info_ranges_of_type(case)


def conclusion_289449543556339629720445623912622786519(case) -> List[str]:
    def property_info_ranges_of_type(case: PropertyInfo) -> List[str]:
        """Get possible value(s) for PropertyInfo.ranges  of type ."""
        return case.onto.properties[case.inverses[0]].domains

    return property_info_ranges_of_type(case)


def conditions_185021833760373592529284117887051484781(case) -> bool:
    def conditions_for_property_info_ranges_of_type(case: PropertyInfo) -> bool:
        """Get conditions on whether it's possible to conclude a value for PropertyInfo.ranges  of type ."""
        return (
            len(case.onto.original_properties[case.name].ranges) == 0
            and (
                len(case.inverses) == 0
                or all(
                    len(case.onto.original_properties[i].domains) == 0
                    for i in case.inverses
                )
            )
            and len(case.equivalent_properties) == 0
        )

    return conditions_for_property_info_ranges_of_type(case)


def conclusion_185021833760373592529284117887051484781(case) -> List[str]:
    def property_info_ranges_of_type(case: PropertyInfo) -> List[str]:
        """Get possible value(s) for PropertyInfo.ranges  of type ."""
        ranges = []
        for sp in reversed(case.sorted_superproperties):
            if len(case.onto.original_properties[sp].ranges) > 0:
                ranges.extend(case.onto.original_properties[sp].ranges)
                break
        return ranges

    return property_info_ranges_of_type(case)


def conditions_276827957023682938371215336609099145051(case) -> bool:
    def conditions_for_property_info_ranges_of_type(case: PropertyInfo) -> bool:
        """Get conditions on whether it's possible to conclude a value for PropertyInfo.ranges  of type ."""
        return (
            len(case.onto.original_properties[case.name].ranges) == 0
            and len(case.superproperties) == 0
            and len(case.inverses) == 0
            and len(case.equivalent_properties) == 0
        )

    return conditions_for_property_info_ranges_of_type(case)


def conclusion_276827957023682938371215336609099145051(case) -> List[str]:
    def property_info_ranges_of_type(case: PropertyInfo) -> List[str]:
        """Get possible value(s) for PropertyInfo.ranges  of type ."""
        return case.onto.base_cls_name

    return property_info_ranges_of_type(case)
