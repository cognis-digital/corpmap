"""CORPMAP command-line interface."""
from __future__ import annotations

import argparse
import json
import sys
from typing import List, Optional

from . import TOOL_NAME, TOOL_VERSION
from .core import CorpmapError, OwnershipGraph, load_dataset


def _print_json(obj) -> None:
    print(json.dumps(obj, indent=2, sort_keys=False))


def _print_table(rows: List[List[str]], headers: List[str]) -> None:
    cols = list(zip(*([headers] + rows))) if rows else [[h] for h in headers]
    widths = [max(len(str(c)) for c in col) for col in cols]
    line = "  ".join(str(h).ljust(widths[i]) for i, h in enumerate(headers))
    print(line)
    print("  ".join("-" * widths[i] for i in range(len(headers))))
    for row in rows:
        print("  ".join(str(c).ljust(widths[i]) for i, c in enumerate(row)))


def _cmd_owners(graph: OwnershipGraph, args) -> int:
    owners = graph.beneficial_owners(
        args.entity, min_pct=args.min_pct, persons_only=args.persons_only
    )
    target = graph.get_entity(args.entity)
    if args.format == "json":
        _print_json(
            {
                "target": target.to_dict(),
                "min_pct": args.min_pct,
                "persons_only": args.persons_only,
                "beneficial_owners": [o.to_dict() for o in owners],
            }
        )
    else:
        print(f"Beneficial owners of {target.name} ({target.id}):")
        rows = [
            [
                o.id,
                o.name,
                o.type,
                f"{o.effective_pct:.2f}%",
                "direct" if o.direct else "indirect",
                ",".join(o.flags) or "-",
            ]
            for o in owners
        ]
        _print_table(rows, ["ID", "NAME", "TYPE", "EFFECTIVE", "VIA", "FLAGS"])
        if not rows:
            print("(no owners above threshold)")
    return 0


def _cmd_cycles(graph: OwnershipGraph, args) -> int:
    cycles = graph.find_cycles()
    if args.format == "json":
        _print_json({"cycle_count": len(cycles), "cycles": cycles})
    else:
        if not cycles:
            print("No circular cross-holdings detected.")
        else:
            print(f"{len(cycles)} circular cross-holding(s):")
            for cyc in cycles:
                print("  " + " -> ".join(cyc) + " -> " + cyc[0])
    return 0


def _cmd_entity(graph: OwnershipGraph, args) -> int:
    ent = graph.get_entity(args.entity)
    direct = graph.direct_owners(args.entity)
    payload = {
        "entity": ent.to_dict(),
        "direct_owners": [
            {"owner": o, "pct": round(f * 100.0, 4)} for o, f in direct
        ],
        "total_direct_pct": round(graph.total_direct_pct(args.entity), 4),
    }
    if args.format == "json":
        _print_json(payload)
    else:
        print(f"{ent.name} ({ent.id}) — type={ent.type} jurisdiction={ent.jurisdiction or '?'}")
        rows = [[o, f"{f * 100.0:.2f}%"] for o, f in direct]
        _print_table(rows, ["DIRECT OWNER", "PCT"])
        print(f"Total direct ownership on record: {payload['total_direct_pct']:.2f}%")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog=TOOL_NAME,
        description="Corporate structure & beneficial-ownership mapper.",
    )
    p.add_argument("--version", action="version", version=f"{TOOL_NAME} {TOOL_VERSION}")
    p.add_argument(
        "--format", choices=["table", "json"], default="table",
        help="output format (default: table)",
    )
    sub = p.add_subparsers(dest="command", required=True)

    sp = sub.add_parser("owners", help="resolve beneficial owners of an entity")
    sp.add_argument("dataset", help="path to ownership dataset (JSON)")
    sp.add_argument("entity", help="entity id to resolve")
    sp.add_argument("--min-pct", type=float, default=0.0, help="only show owners >= this effective %%")
    sp.add_argument("--persons-only", action="store_true", help="only natural-person owners")
    sp.set_defaults(func=_cmd_owners)

    sc = sub.add_parser("cycles", help="detect circular cross-holdings")
    sc.add_argument("dataset", help="path to ownership dataset (JSON)")
    sc.set_defaults(func=_cmd_cycles)

    se = sub.add_parser("entity", help="show an entity and its direct owners")
    se.add_argument("dataset", help="path to ownership dataset (JSON)")
    se.add_argument("entity", help="entity id")
    se.set_defaults(func=_cmd_entity)

    return p


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        graph = load_dataset(args.dataset)
        return args.func(graph, args)
    except CorpmapError as exc:
        print(f"corpmap: error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
