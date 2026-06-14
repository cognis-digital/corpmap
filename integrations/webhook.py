#!/usr/bin/env python3
"""Minimal, dependency-free webhook forwarder for Cognis findings.

Reads JSON findings on stdin and POSTs them to a URL (SIEM/Slack/Jira bridge).
Usage:  <tool> scan . --format json | python integrations/webhook.py --url URL
"""
from __future__ import annotations
import argparse
import json
import sys
import urllib.error
import urllib.request


def main() -> int:
    ap = argparse.ArgumentParser(
        description="POST JSON findings from stdin to a webhook URL."
    )
    ap.add_argument("--url", required=True, help="Destination URL")
    ap.add_argument("--header", action="append", default=[], help="Key: Value")
    ap.add_argument(
        "--timeout",
        type=int,
        default=15,
        help="HTTP timeout in seconds (default: 15)",
    )
    args = ap.parse_args()

    if args.timeout <= 0:
        print("webhook: error: --timeout must be a positive integer", file=sys.stderr)
        return 2

    raw = sys.stdin.read()
    if not raw.strip():
        print("webhook: error: stdin is empty — nothing to post", file=sys.stderr)
        return 2

    # Validate that stdin is well-formed JSON before sending.
    try:
        json.loads(raw)
    except json.JSONDecodeError as exc:
        print(f"webhook: error: stdin is not valid JSON: {exc}", file=sys.stderr)
        return 2

    payload = raw.encode("utf-8")
    req = urllib.request.Request(args.url, data=payload, method="POST")
    req.add_header("Content-Type", "application/json")
    for h in args.header:
        if ":" not in h:
            print(
                f"webhook: error: malformed --header {h!r} (expected 'Key: Value')",
                file=sys.stderr,
            )
            return 2
        k, _, v = h.partition(":")
        req.add_header(k.strip(), v.strip())

    try:
        with urllib.request.urlopen(req, timeout=args.timeout) as r:
            print(f"posted {len(payload)} bytes -> {r.status}")
        return 0
    except urllib.error.HTTPError as exc:
        print(f"webhook: HTTP error {exc.code}: {exc.reason}", file=sys.stderr)
        return 1
    except urllib.error.URLError as exc:
        print(f"webhook: connection error: {exc.reason}", file=sys.stderr)
        return 1
    except OSError as exc:
        print(f"webhook: error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
