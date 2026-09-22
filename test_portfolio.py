import csv
import json
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


if __name__ == "__main__":
    unittest.main()
