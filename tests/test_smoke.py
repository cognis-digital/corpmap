"""Smoke tests for CORPMAP — no network, stdlib only."""
import io
import json
import os
import sys
import unittest
from contextlib import redirect_stdout

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from corpmap import TOOL_NAME, TOOL_VERSION, parse_dataset  # noqa: E402
from corpmap.cli import main  # noqa: E402
from corpmap.core import CorpmapError  # noqa: E402

DEMO = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "demos", "01-basic", "ownership.json",
)

DATA = {
    "entities": [
        {"id": "JANE", "name": "Jane", "type": "person"},
        {"id": "T", "name": "Trust", "type": "trust"},
        {"id": "H", "name": "Holdco", "type": "company"},
        {"id": "M", "name": "Midco", "type": "company"},
        {"id": "OP", "name": "Opco", "type": "company"},
        {"id": "RAVI", "name": "Ravi", "type": "person"},
        {"id": "FUND", "name": "Fund", "type": "fund"},
    ],
    "ownership": [
        {"owner": "JANE", "owned": "T", "pct": 100},
        {"owner": "T", "owned": "H", "pct": 80},
        {"owner": "RAVI", "owned": "H", "pct": 20},
        {"owner": "H", "owned": "M", "pct": 90},
        {"owner": "RAVI", "owned": "M", "pct": 10},
        {"owner": "M", "owned": "OP", "pct": 75},
        {"owner": "FUND", "owned": "OP", "pct": 25},
    ],
}


class TestMeta(unittest.TestCase):
    def test_meta(self):
        self.assertEqual(TOOL_NAME, "corpmap")
        self.assertTrue(TOOL_VERSION)


class TestEngine(unittest.TestCase):
    def setUp(self):
        self.g = parse_dataset(DATA)

    def test_lookthrough_persons(self):
        owners = self.g.beneficial_owners("OP", persons_only=True)
        by = {o.id: o.effective_pct for o in owners}
        # Jane: 1.0 * .8 * .9 * .75 = 54%
        self.assertAlmostEqual(by["JANE"], 54.0, places=4)
        # Ravi: (.2*.9*.75) + (.1*.75) = 13.5 + 7.5 = 21%
        self.assertAlmostEqual(by["RAVI"], 21.0, places=4)

    def test_flags(self):
        owners = {o.id: o for o in self.g.beneficial_owners("OP", persons_only=True)}
        self.assertIn("MAJORITY", owners["JANE"].flags)
        self.assertIn("CONTROL", owners["JANE"].flags)
        self.assertNotIn("CONTROL", owners["RAVI"].flags)
        self.assertIn("DISCLOSABLE", owners["RAVI"].flags)

    def test_min_pct_filter(self):
        owners = self.g.beneficial_owners("OP", min_pct=30.0, persons_only=True)
        self.assertEqual([o.id for o in owners], ["JANE"])

    def test_direct_owners(self):
        d = dict(self.g.direct_owners("OP"))
        self.assertAlmostEqual(d["M"], 0.75)
        self.assertAlmostEqual(d["FUND"], 0.25)

    def test_cycle_detection(self):
        data = {
            "entities": [
                {"id": "A", "type": "company"},
                {"id": "B", "type": "company"},
            ],
            "ownership": [
                {"owner": "A", "owned": "B", "pct": 60},
                {"owner": "B", "owned": "A", "pct": 60},
            ],
        }
        g = parse_dataset(data)
        cycles = g.find_cycles()
        self.assertEqual(len(cycles), 1)
        self.assertEqual(set(cycles[0]), {"A", "B"})
        # beneficial-owner walk must terminate despite the cycle
        owners = g.beneficial_owners("A")
        self.assertTrue(any(o.id == "B" for o in owners))

    def test_unknown_entity(self):
        with self.assertRaises(CorpmapError):
            self.g.beneficial_owners("NOPE")

    def test_bad_dataset(self):
        with self.assertRaises(CorpmapError):
            parse_dataset({"entities": [], "ownership": []})
        with self.assertRaises(CorpmapError):
            parse_dataset({"entities": [{"id": "X"}],
                           "ownership": [{"owner": "X", "owned": "Y", "pct": 10}]})
        with self.assertRaises(CorpmapError):
            parse_dataset({"entities": [{"id": "X"}],
                           "ownership": [{"owner": "X", "owned": "X", "pct": 200}]})


class TestCLI(unittest.TestCase):
    def _run(self, argv):
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = main(argv)
        return rc, buf.getvalue()

    def test_json_owners(self):
        rc, out = self._run(
            ["--format", "json", "owners", DEMO, "OPCO", "--persons-only"]
        )
        self.assertEqual(rc, 0)
        payload = json.loads(out)
        by = {o["id"]: o["effective_pct"] for o in payload["beneficial_owners"]}
        self.assertAlmostEqual(by["JANE"], 54.0, places=2)
        self.assertAlmostEqual(by["RAVI"], 21.0, places=2)

    def test_table_owners(self):
        rc, out = self._run(["owners", DEMO, "OPCO"])
        self.assertEqual(rc, 0)
        self.assertIn("Jane Okafor", out)

    def test_cycles_clean(self):
        rc, out = self._run(["--format", "json", "cycles", DEMO])
        self.assertEqual(rc, 0)
        self.assertEqual(json.loads(out)["cycle_count"], 0)

    def test_entity_cmd(self):
        rc, out = self._run(["--format", "json", "entity", DEMO, "OPCO"])
        self.assertEqual(rc, 0)
        self.assertAlmostEqual(json.loads(out)["total_direct_pct"], 100.0, places=2)

    def test_failure_exit_code(self):
        rc, _ = self._run(["owners", DEMO, "DOESNOTEXIST"])
        self.assertEqual(rc, 2)


if __name__ == "__main__":
    unittest.main()
