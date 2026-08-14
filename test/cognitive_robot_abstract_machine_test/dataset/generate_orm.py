"""
Stand-in for the ORM interface generator of a workspace package.

Records what the checkout looked like when it ran and then fills its own package's
interface, so a test can observe in which order and against which state the generators
were driven.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing_extensions import List

GENERATION_LOG_NAME = "generation_log.txt"
"""
Name of the file in the checkout root that every generator appends one record to.
"""


def interface_of(package_root: Path) -> Path:
    """
    Locate the generated ORM interface of a package.

    :param package_root: Root folder of the package.
    :return: Path of the package's ``ormatic_interface.py``.
    """
    return package_root / "src" / package_root.name / "orm" / "ormatic_interface.py"


def interface_content(package_name: str) -> str:
    """
    Build the interface this generator writes for a package.

    :param package_name: Name of the package being generated.
    :return: The generated content.
    """
    return f"# ORM interface of {package_name}\n"


@dataclass
class GenerationRecord:
    """
    What a single generator saw of the checkout when it ran.
    """

    package_name: str
    """
    Name of the package the generator belongs to.
    """

    generated_packages: List[str]
    """
    Names of the packages whose interface already held content, in alphabetical order.
    """

    @classmethod
    def from_line(cls, line: str) -> GenerationRecord:
        """
        Read a record back from its line in the log.

        :param line: One line of the generation log.
        :return: The record the line holds.
        """
        package_name, generated = line.split(":")
        return cls(package_name, generated.split(",") if generated else [])

    def to_line(self) -> str:
        """
        Render this record as one line of the generation log.

        :return: The line, terminated by a line break.
        """
        return f"{self.package_name}:{','.join(self.generated_packages)}\n"


def read_generation_log(repository_root: Path) -> List[GenerationRecord]:
    """
    Read every record the generators of a checkout appended, in the order they ran.

    :param repository_root: Root of the checkout.
    :return: The records of all generator runs.
    """
    log = repository_root / GENERATION_LOG_NAME
    if not log.exists():
        return []
    return [
        GenerationRecord.from_line(line)
        for line in log.read_text(encoding="utf-8").splitlines()
    ]


def generated_packages(repository_root: Path) -> List[str]:
    """
    Names of the packages of a checkout whose interface already holds content.

    :param repository_root: Root of the checkout.
    :return: The package names in alphabetical order.
    """
    return sorted(
        package_root.name
        for package_root in repository_root.iterdir()
        if package_root.is_dir()
        and interface_of(package_root).exists()
        and interface_of(package_root).stat().st_size > 0
    )


def main() -> None:
    """
    Log what the checkout holds so far and generate this package's interface.
    """
    package_root = Path(__file__).resolve().parents[1]
    repository_root = package_root.parent
    record = GenerationRecord(package_root.name, generated_packages(repository_root))
    with (repository_root / GENERATION_LOG_NAME).open("a", encoding="utf-8") as log:
        log.write(record.to_line())
    interface_of(package_root).write_text(
        interface_content(package_root.name), encoding="utf-8"
    )


if __name__ == "__main__":
    main()
