import csv
import json
import sqlite3
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent
PORTFOLIO = ROOT / "portfolio-data"


class PortfolioExportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = json.loads((PORTFOLIO / "manifest.json").read_text(encoding="utf-8"))

    def test_every_manifest_file_exists_and_matches_row_count(self):
        for item in self.manifest["data"]["files"]:
            path = PORTFOLIO / item["path"]
            self.assertTrue(path.is_file(), item["path"])
            self.assertEqual(path.stat().st_size, item["bytes"], item["path"])
            if path.suffix == ".json":
                document = json.loads(path.read_text(encoding="utf-8"))
                self.assertEqual(document["schema_version"], 1)
                rows = document["data"]
                self.assertEqual(len(rows) if isinstance(rows, list) else 1, item["rows"])
            elif path.stat().st_size:
                with path.open(encoding="utf-8-sig", newline="") as file:
                    self.assertEqual(sum(1 for _ in csv.DictReader(file)), item["rows"])

    def test_umap_is_partitioned_and_bounded(self):
        umap_files = [
            item for item in self.manifest["data"]["files"]
            if item["path"].endswith("/umap.json")
        ]
        self.assertEqual(len(umap_files), 33)
        self.assertTrue(all(0 < item["rows"] <= 400 for item in umap_files))

    def test_full_debate_export_covers_every_imported_speech(self):
        index = json.loads((PORTFOLIO / "debates/index.json").read_text(encoding="utf-8"))["data"]
        with sqlite3.connect(ROOT / "data/debates.sqlite") as db:
            expected = dict(db.execute(
                "select dok_id || '-' || anforande_nummer, anforandetext from speeches"
            ))
        seen = set()
        for debate in index:
            rows = json.loads((PORTFOLIO / debate["path"]).read_text(encoding="utf-8"))["data"]
            self.assertEqual(len(rows), debate["speech_count"])
            self.assertEqual(sum(bool(row["is_reply"]) for row in rows), debate["reply_count"])
            self.assertEqual(
                [row["speech_number"] for row in rows],
                sorted(row["speech_number"] for row in rows),
            )
            for row in rows:
                speech_id = row["speech_id"]
                self.assertNotIn(speech_id, seen)
                seen.add(speech_id)
                self.assertEqual(row["speech_text"], expected[speech_id])
        self.assertEqual(seen, set(expected))

    def test_issue_export_covers_every_imported_speech(self):
        index = json.loads((PORTFOLIO / "issues/index.json").read_text(encoding="utf-8"))["data"]
        seen = set()
        with sqlite3.connect(ROOT / "data/issue_speeches.sqlite") as db:
            expected_count = db.execute("select count(*) from issue_speeches").fetchone()[0]
            for session in index:
                sections = json.loads((PORTFOLIO / session["index_path"]).read_text(encoding="utf-8"))["data"]
                self.assertEqual(len(sections), session["section_count"])
                for path in sorted({section["path"] for section in sections}):
                    rows = json.loads((PORTFOLIO / path).read_text(encoding="utf-8"))["data"]
                    protocol_id = rows[0]["protocol_id"]
                    source = dict(db.execute(
                        "select dok_id || '-' || anforande_nummer, anforandetext "
                        "from issue_speeches where dok_id=?", (protocol_id,)
                    ))
                    self.assertEqual(len(rows), len(source))
                    for row in rows:
                        self.assertNotIn(row["speech_id"], seen)
                        seen.add(row["speech_id"])
                        self.assertEqual(row["speech_text"], source[row["speech_id"]])
        self.assertEqual(len(seen), expected_count)


if __name__ == "__main__":
    unittest.main()
