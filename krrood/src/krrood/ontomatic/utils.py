import re


def to_snake(name: str) -> str:
    """Convert a name like 'worksFor' or 'WorksFor' to 'works_for'"""
    s1 = re.sub(r"(.)([A-Z][a-z]+)", r"\1_\2", name)
    s2 = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", s1)
    return s2.lower()
