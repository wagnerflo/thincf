from dataclasses import dataclass,field
from typing import Tuple
from ..util import update_hash

@dataclass
class Action:
    name: str
    content: str = field(repr=False)

    def add_to_hash(self, h):
        update_hash(h, self.name, self.content)

@dataclass(frozen=True)
class Invocation:
    name: str
    arguments: Tuple[str]

__all__ = (
    'Action',
    'Invocation',
)
