"""CORPMAP core engine.

Data model
----------
A dataset is JSON with two arrays:

    {
      "entities": [
        {"id": "ACME", "name": "Acme Holdings Ltd", "type": "company",
         "jurisdiction": "GB"},
        ...
      ],
      "ownership": [
        {"owner": "JANE", "owned": "ACME", "pct": 60.0},
        ...
      ]
    }

- `type` is free text but "person" marks a natural person (a terminal
  beneficial owner). Everything else is treated as an intermediate entity to
  look through.
- `pct` is a direct ownership percentage (0..100).

The engine computes *effective* (beneficial) ownership of a target entity by
multiplying ownership fractions along every path from a natural person (or an
external/unowned entity) down to the target, summing across paths. Circular
holdings are detected and broken so the computation terminates.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Dict, List, Tuple

# Regulatory-ish thresholds (configurable by callers if desired).
DISCLOSURE_THRESHOLD = 5.0   # typical SEC 13D/G beneficial-ownership flag
CONTROL_THRESHOLD = 25.0     # typical AML "beneficial owner" / control flag
MAJORITY_THRESHOLD = 50.0    # de-facto control


class CorpmapError(Exception):
    """Raised on malformed datasets or unknown entities."""


@dataclass
class Entity:
    id: str
    name: str
    type: str = "company"
    jurisdiction: str = ""

    @property
    def is_person(self) -> bool:
        return self.type.strip().lower() == "person"

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "type": self.type,
            "jurisdiction": self.jurisdiction,
            "is_person": self.is_person,
        }


@dataclass
class OwnershipEdge:
    owner: str
    owned: str
    pct: float

    def to_dict(self) -> dict:
        return {"owner": self.owner, "owned": self.owned, "pct": self.pct}


@dataclass
class BeneficialOwner:
    id: str
    name: str
    type: str
    effective_pct: float
    direct: bool
    flags: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "type": self.type,
            "effective_pct": round(self.effective_pct, 4),
            "direct": self.direct,
            "flags": self.flags,
        }


def _classify_flags(pct: float) -> List[str]:
    flags: List[str] = []
    if pct >= MAJORITY_THRESHOLD:
        flags.append("MAJORITY")
    if pct >= CONTROL_THRESHOLD:
        flags.append("CONTROL")
    if pct >= DISCLOSURE_THRESHOLD:
        flags.append("DISCLOSABLE")
    return flags


class OwnershipGraph:
    """Directed ownership graph with beneficial-ownership resolution."""

    def __init__(self, entities: List[Entity], edges: List[OwnershipEdge]):
        self.entities: Dict[str, Entity] = {e.id: e for e in entities}
        self.edges: List[OwnershipEdge] = edges
        # owned -> list of (owner_id, fraction)
        self._owners_of: Dict[str, List[Tuple[str, float]]] = {}
        # owner -> list of (owned_id, fraction)
        self._owned_by: Dict[str, List[Tuple[str, float]]] = {}
        for e in edges:
            if e.owner not in self.entities:
                raise CorpmapError(f"ownership references unknown owner: {e.owner!r}")
            if e.owned not in self.entities:
                raise CorpmapError(f"ownership references unknown entity: {e.owned!r}")
            frac = e.pct / 100.0
            self._owners_of.setdefault(e.owned, []).append((e.owner, frac))
            self._owned_by.setdefault(e.owner, []).append((e.owned, frac))

    # -- introspection --------------------------------------------------
    def get_entity(self, eid: str) -> Entity:
        if eid not in self.entities:
            raise CorpmapError(f"unknown entity: {eid!r}")
        return self.entities[eid]

    def direct_owners(self, eid: str) -> List[Tuple[str, float]]:
        self.get_entity(eid)
        return list(self._owners_of.get(eid, []))

    def total_direct_pct(self, eid: str) -> float:
        return sum(frac for _, frac in self._owners_of.get(eid, [])) * 100.0

    # -- cycle detection ------------------------------------------------
    def find_cycles(self) -> List[List[str]]:
        """Return ownership cycles (cross-holdings) as node lists."""
        cycles: List[List[str]] = []
        seen_signatures = set()
        WHITE, GRAY, BLACK = 0, 1, 2
        color: Dict[str, int] = {e: WHITE for e in self.entities}
        stack: List[str] = []

        def dfs(node: str):
            color[node] = GRAY
            stack.append(node)
            for owned, _ in self._owned_by.get(node, []):
                if color[owned] == GRAY:
                    idx = stack.index(owned)
                    cyc = stack[idx:]
                    sig = tuple(sorted(cyc))
                    if sig not in seen_signatures:
                        seen_signatures.add(sig)
                        cycles.append(list(cyc))
                elif color[owned] == WHITE:
                    dfs(owned)
            stack.pop()
            color[node] = BLACK

        for node in self.entities:
            if color[node] == WHITE:
                dfs(node)
        return cycles

    # -- beneficial ownership look-through ------------------------------
    def beneficial_owners(
        self, target: str, min_pct: float = 0.0, persons_only: bool = False
    ) -> List[BeneficialOwner]:
        """Resolve effective ownership of `target`.

        Walks UP the ownership chain from `target` to ultimate owners,
        multiplying fractions along each path and summing across paths.
        Cycles are broken by refusing to revisit a node already on the
        current path (the leaked fraction is dropped, which is the
        conservative treatment for cross-holdings).
        """
        self.get_entity(target)
        accumulated: Dict[str, float] = {}
        direct_ids = {owner for owner, _ in self._owners_of.get(target, [])}
        _MAX_DEPTH = 500  # guard against stack overflow on pathological datasets

        def walk(node: str, frac: float, path: frozenset, depth: int = 0):
            if depth > _MAX_DEPTH:
                # Treat over-deep paths as terminal; attribute to the current node.
                accumulated[node] = accumulated.get(node, 0.0) + frac
                return
            owners = self._owners_of.get(node, [])
            if not owners:
                # `node` is a terminal owner (no further owners on record).
                if node != target:
                    accumulated[node] = accumulated.get(node, 0.0) + frac
                return
            for owner, ofrac in owners:
                contribution = frac * ofrac
                owner_ent = self.entities[owner]
                if owner_ent.is_person:
                    # Natural person: terminal beneficial owner.
                    accumulated[owner] = accumulated.get(owner, 0.0) + contribution
                    # Persons can also be owned (rare) — but stop the walk here.
                    continue
                if owner in path:
                    # Circular holding — stop to terminate; credit the entity.
                    accumulated[owner] = accumulated.get(owner, 0.0) + contribution
                    continue
                # Intermediate entity: also record its aggregate stake, then
                # continue looking through to find ultimate owners.
                accumulated[owner] = accumulated.get(owner, 0.0) + contribution
                walk(owner, contribution, path | {owner}, depth + 1)

        walk(target, 1.0, frozenset({target}))

        results: List[BeneficialOwner] = []
        for eid, frac in accumulated.items():
            pct = frac * 100.0
            if pct + 1e-9 < min_pct:
                continue
            ent = self.entities[eid]
            if persons_only and not ent.is_person:
                continue
            results.append(
                BeneficialOwner(
                    id=ent.id,
                    name=ent.name,
                    type=ent.type,
                    effective_pct=pct,
                    direct=eid in direct_ids,
                    flags=_classify_flags(pct),
                )
            )
        results.sort(key=lambda b: (-b.effective_pct, b.id))
        return results

    def to_dict(self) -> dict:
        return {
            "entities": [e.to_dict() for e in self.entities.values()],
            "ownership": [e.to_dict() for e in self.edges],
        }


# -- loading ------------------------------------------------------------
def parse_dataset(data: dict) -> OwnershipGraph:
    if not isinstance(data, dict):
        raise CorpmapError("dataset must be a JSON object")
    raw_entities = data.get("entities")
    raw_ownership = data.get("ownership")
    if not isinstance(raw_entities, list) or not raw_entities:
        raise CorpmapError("dataset.entities must be a non-empty array")
    if not isinstance(raw_ownership, list):
        raise CorpmapError("dataset.ownership must be an array")

    entities: List[Entity] = []
    seen = set()
    for i, raw in enumerate(raw_entities):
        if not isinstance(raw, dict):
            raise CorpmapError(f"entities[{i}] must be an object")
        if "id" not in raw:
            raise CorpmapError(f"entities[{i}] missing required field 'id'")
        raw_id = raw["id"]
        if raw_id is None or str(raw_id).strip() == "":
            raise CorpmapError(f"entities[{i}].id must not be null or empty")
        eid = str(raw_id).strip()
        if eid in seen:
            raise CorpmapError(f"duplicate entity id: {eid!r}")
        seen.add(eid)
        raw_name = raw.get("name", eid)
        name = str(raw_name) if raw_name is not None else eid
        entities.append(
            Entity(
                id=eid,
                name=name,
                type=str(raw.get("type") or "company"),
                jurisdiction=str(raw.get("jurisdiction") or ""),
            )
        )

    edges: List[OwnershipEdge] = []
    for i, raw in enumerate(raw_ownership):
        if not isinstance(raw, dict):
            raise CorpmapError(f"ownership[{i}] must be an object")
        for k in ("owner", "owned", "pct"):
            if k not in raw:
                raise CorpmapError(f"ownership[{i}] missing required field {k!r}")
        try:
            pct = float(raw["pct"])
        except (TypeError, ValueError):
            raise CorpmapError(f"ownership[{i}].pct is not a number")
        if not (0.0 <= pct <= 100.0):
            raise CorpmapError(f"ownership[{i}].pct out of range 0..100: {pct}")
        edges.append(OwnershipEdge(owner=str(raw["owner"]), owned=str(raw["owned"]), pct=pct))

    return OwnershipGraph(entities, edges)


def load_dataset(path: str) -> OwnershipGraph:
    if not path or not path.strip():
        raise CorpmapError("dataset path must not be empty")
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except FileNotFoundError:
        raise CorpmapError(f"dataset file not found: {path}")
    except PermissionError:
        raise CorpmapError(f"permission denied reading dataset: {path}")
    except IsADirectoryError:
        raise CorpmapError(f"dataset path is a directory, not a file: {path}")
    except OSError as exc:
        raise CorpmapError(f"could not read dataset {path}: {exc}")
    except json.JSONDecodeError as exc:
        raise CorpmapError(f"invalid JSON in {path}: {exc}")
    except UnicodeDecodeError as exc:
        raise CorpmapError(f"dataset file is not valid UTF-8: {path}: {exc}")
    return parse_dataset(data)
