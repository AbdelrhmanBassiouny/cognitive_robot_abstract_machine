from dataclasses import dataclass


@dataclass
class ExternalType:
    """
    A type defined in an external module.
    """

    name: str
