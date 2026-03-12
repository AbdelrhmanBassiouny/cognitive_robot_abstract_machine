from dataclasses import dataclass

from krrood.symbol_graph.symbol_graph import Symbol


@dataclass(eq=False)
class PersonAsRoleTakerInAnotherModule(Symbol):
    name: str

    def __hash__(self):
        return hash(self.name)
