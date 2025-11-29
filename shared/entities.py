from enum import IntEnum
from dataclasses import dataclass, field
from typing import Optional, Dict, Any


class EntityType(IntEnum):
    PLAYER = 0
    CONVEYOR = 1
    MINER = 2
    FURNACE = 3
    ASSEMBLER = 4
    CHEST = 5
    INSERTER = 6


class Direction(IntEnum):
    NORTH = 0
    EAST = 1
    SOUTH = 2
    WEST = 3


@dataclass
class Entity:
    id: int
    entity_type: EntityType
    x: float
    y: float
    direction: Direction = Direction.NORTH
    data: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'type': int(self.entity_type),
            'x': self.x,
            'y': self.y,
            'dir': int(self.direction),
            'data': self.data
        }

    @staticmethod
    def from_dict(d: dict) -> 'Entity':
        return Entity(
            id=d['id'],
            entity_type=EntityType(d['type']),
            x=d['x'],
            y=d['y'],
            direction=Direction(d['dir']),
            data=d.get('data', {})
        )
