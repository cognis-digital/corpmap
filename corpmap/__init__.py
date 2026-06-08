"""CORPMAP — Corporate structure & beneficial-ownership mapper.

Parses a flat entity/relationship dataset describing corporate ownership and
resolves the effective (look-through) beneficial ownership of any entity,
detects circular holdings, and flags control / disclosure thresholds.

Standard library only. Zero install.
"""
from .core import (
    Entity,
    OwnershipEdge,
    OwnershipGraph,
    BeneficialOwner,
    load_dataset,
    parse_dataset,
)

TOOL_NAME = "corpmap"
TOOL_VERSION = "1.0.0"

__all__ = [
    "Entity",
    "OwnershipEdge",
    "OwnershipGraph",
    "BeneficialOwner",
    "load_dataset",
    "parse_dataset",
    "TOOL_NAME",
    "TOOL_VERSION",
]
