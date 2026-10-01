"""
Synchronize the root VERSION file into all package _version.py files.
"""

from enum import StrEnum
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERSION_FILE = ROOT / "VERSION"


class Package(StrEnum):
    """
    A package whose ``_version.py`` this script writes, spelled as it is imported.
    """

    RANDOM_EVENTS = "random_events"
    KRROOD = "krrood"
    CORAPLEX = "coraplex"
    CRAMERA = "cramera"
    GISKARDPY = "giskardpy"
    PROBABILISTIC_MODEL = "probabilistic_model"
    ROBOKUDO = "robokudo"
    PHYSICS_SIMULATORS = "physics_simulators"
    EXPERIMENTS = "experiments"
    SEMANTIC_DIGITAL_TWIN = "semantic_digital_twin"
    COGNITIVE_ROBOT_ABSTRACT_MACHINE = "cognitive_robot_abstract_machine"
    BASSTLER = "basstler"

    @property
    def is_its_own_directory(self) -> bool:
        """
        :return: Whether the package *is* its own directory rather than living under a
            ``src`` one, which puts its ``_version.py`` one level up.
        """
        return self in (Package.COGNITIVE_ROBOT_ABSTRACT_MACHINE, Package.BASSTLER)

    @property
    def version_file(self) -> Path:
        """
        :return: The ``_version.py`` this package reads its version from.
        """
        if self.is_its_own_directory:
            return ROOT / self / "_version.py"
        return ROOT / self / "src" / self / "_version.py"


def main() -> None:
    version = VERSION_FILE.read_text().strip()
    for package in Package:
        package.version_file.write_text(f'__version__ = "{version}"\n')
        print(f"Updated {package.version_file}")


if __name__ == "__main__":
    main()
