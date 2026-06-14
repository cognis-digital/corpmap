"""Hardening tests — error paths, edge cases, and bad-input handling."""
from __future__ import annotations

import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from corpmap.cli import _print_table, main  # noqa: E402
from corpmap.core import CorpmapError, load_dataset, parse_dataset  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _run_main(argv):
    """Return (exit_code, stdout_text, stderr_text)."""
    out_buf = io.StringIO()
    err_buf = io.StringIO()
    with redirect_stdout(out_buf), redirect_stderr(err_buf):
        rc = main(argv)
    return rc, out_buf.getvalue(), err_buf.getvalue()


def _write_json(d, suffix=".json"):
    """Write *d* as JSON to a temp file, return the path."""
    fh = tempfile.NamedTemporaryFile(
        mode="w", suffix=suffix, delete=False, encoding="utf-8"
    )
    json.dump(d, fh)
    fh.close()
    return fh.name


# ---------------------------------------------------------------------------
# load_dataset — file I/O errors
# ---------------------------------------------------------------------------

class TestLoadDatasetErrors(unittest.TestCase):
    def test_missing_file_raises(self):
        with self.assertRaises(CorpmapError) as ctx:
            load_dataset("/no/such/path/dataset.json")
        self.assertIn("not found", str(ctx.exception))

    def test_is_directory_raises(self):
        # Opening a directory path should raise CorpmapError with a clear message.
        # On Windows this surfaces as PermissionError, on POSIX as IsADirectoryError.
        with self.assertRaises(CorpmapError) as ctx:
            load_dataset(tempfile.gettempdir())
        msg = str(ctx.exception).lower()
        # Must contain either "directory" or "permission" — never a raw traceback.
        self.assertTrue(
            "directory" in msg or "permission" in msg,
            f"unexpected error message: {ctx.exception}",
        )

    def test_malformed_json_raises(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8"
        ) as fh:
            fh.write("{not valid json")
            path = fh.name
        try:
            with self.assertRaises(CorpmapError) as ctx:
                load_dataset(path)
            self.assertIn("invalid JSON", str(ctx.exception))
        finally:
            os.unlink(path)

    def test_empty_path_raises(self):
        with self.assertRaises(CorpmapError):
            load_dataset("")

    def test_whitespace_path_raises(self):
        with self.assertRaises(CorpmapError):
            load_dataset("   ")


# ---------------------------------------------------------------------------
# parse_dataset — structural validation
# ---------------------------------------------------------------------------

class TestParseDatasetValidation(unittest.TestCase):
    def _good(self):
        return {
            "entities": [
                {"id": "A", "name": "Alpha", "type": "person"},
                {"id": "B", "name": "Beta", "type": "company"},
            ],
            "ownership": [
                {"owner": "A", "owned": "B", "pct": 50.0},
            ],
        }

    def test_null_entity_id_raises(self):
        d = self._good()
        d["entities"][0]["id"] = None
        with self.assertRaises(CorpmapError) as ctx:
            parse_dataset(d)
        self.assertIn("null or empty", str(ctx.exception))

    def test_empty_entity_id_raises(self):
        d = self._good()
        d["entities"][0]["id"] = "   "
        with self.assertRaises(CorpmapError) as ctx:
            parse_dataset(d)
        self.assertIn("null or empty", str(ctx.exception))

    def test_entity_not_dict_raises(self):
        d = self._good()
        d["entities"][0] = "not a dict"
        with self.assertRaises(CorpmapError) as ctx:
            parse_dataset(d)
        self.assertIn("must be an object", str(ctx.exception))

    def test_null_name_uses_id_fallback(self):
        d = self._good()
        d["entities"][0]["name"] = None
        g = parse_dataset(d)
        # Should not raise; entity name falls back to its id.
        ent = g.get_entity("A")
        self.assertEqual(ent.name, "A")

    def test_null_type_uses_default(self):
        d = self._good()
        d["entities"][1]["type"] = None
        g = parse_dataset(d)
        ent = g.get_entity("B")
        self.assertEqual(ent.type, "company")

    def test_null_jurisdiction_uses_empty(self):
        d = self._good()
        d["entities"][0]["jurisdiction"] = None
        g = parse_dataset(d)
        ent = g.get_entity("A")
        self.assertEqual(ent.jurisdiction, "")

    def test_empty_ownership_array_is_valid(self):
        d = self._good()
        d["ownership"] = []
        g = parse_dataset(d)
        self.assertEqual(g.edges, [])

    def test_pct_nan_raises(self):
        d = self._good()
        d["ownership"][0]["pct"] = float("nan")
        # float("nan") passes float() but should fail range check since nan
        # comparisons are always False; confirm it raises or produces
        # a clear error rather than silent corruption.
        # (0.0 <= nan <= 100.0) is False, so CorpmapError expected.
        with self.assertRaises(CorpmapError):
            parse_dataset(d)

    def test_pct_inf_raises(self):
        d = self._good()
        d["ownership"][0]["pct"] = float("inf")
        with self.assertRaises(CorpmapError):
            parse_dataset(d)


# ---------------------------------------------------------------------------
# CLI — bad input / exit codes
# ---------------------------------------------------------------------------

class TestCLIHardening(unittest.TestCase):
    def setUp(self):
        self._good = {
            "entities": [
                {"id": "JANE", "name": "Jane", "type": "person"},
                {"id": "ACME", "name": "Acme", "type": "company"},
            ],
            "ownership": [
                {"owner": "JANE", "owned": "ACME", "pct": 100.0},
            ],
        }
        self._path = _write_json(self._good)

    def tearDown(self):
        try:
            os.unlink(self._path)
        except OSError:
            pass

    def test_missing_dataset_file_exits_2(self):
        rc, _, err = _run_main(["owners", "/no/such/file.json", "ACME"])
        self.assertEqual(rc, 2)
        self.assertIn("error", err.lower())

    def test_unknown_entity_exits_2(self):
        rc, _, err = _run_main(["owners", self._path, "GHOST"])
        self.assertEqual(rc, 2)
        self.assertIn("error", err.lower())

    def test_min_pct_negative_exits_2(self):
        rc, _, err = _run_main(["owners", self._path, "ACME", "--min-pct", "-5"])
        self.assertEqual(rc, 2)
        self.assertIn("error", err.lower())
        self.assertIn("min-pct", err.lower())

    def test_min_pct_over_100_exits_2(self):
        rc, _, err = _run_main(["owners", self._path, "ACME", "--min-pct", "105"])
        self.assertEqual(rc, 2)
        self.assertIn("min-pct", err.lower())

    def test_malformed_json_file_exits_2(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8"
        ) as fh:
            fh.write("{broken}")
            bad_path = fh.name
        try:
            rc, _, err = _run_main(["owners", bad_path, "X"])
            self.assertEqual(rc, 2)
            self.assertIn("error", err.lower())
        finally:
            os.unlink(bad_path)

    def test_valid_owners_returns_0(self):
        rc, out, _ = _run_main(["owners", self._path, "ACME"])
        self.assertEqual(rc, 0)
        self.assertIn("Jane", out)

    def test_cycles_on_clean_data_returns_0(self):
        rc, out, _ = _run_main(["cycles", self._path])
        self.assertEqual(rc, 0)

    def test_entity_cmd_returns_0(self):
        rc, out, _ = _run_main(["--format", "json", "entity", self._path, "ACME"])
        self.assertEqual(rc, 0)
        data = json.loads(out)
        self.assertIn("entity", data)


# ---------------------------------------------------------------------------
# _print_table — defensive rendering
# ---------------------------------------------------------------------------

class TestPrintTable(unittest.TestCase):
    def _capture(self, rows, headers):
        buf = io.StringIO()
        with redirect_stdout(buf):
            _print_table(rows, headers)
        return buf.getvalue()

    def test_empty_rows(self):
        out = self._capture([], ["ID", "NAME"])
        self.assertIn("ID", out)
        self.assertIn("NAME", out)

    def test_short_row_padded(self):
        # A row with fewer columns than headers must not raise.
        out = self._capture([["only-one"]], ["COL1", "COL2", "COL3"])
        self.assertIn("only-one", out)

    def test_normal_table(self):
        rows = [["x", "y", "z"], ["a", "b", "c"]]
        out = self._capture(rows, ["C1", "C2", "C3"])
        self.assertIn("x", out)
        self.assertIn("z", out)


if __name__ == "__main__":
    unittest.main()
