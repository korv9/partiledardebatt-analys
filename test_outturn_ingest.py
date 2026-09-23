import tempfile
import unittest
import zipfile
from pathlib import Path

from outturn_ingest import parse_archive


class OutturnIngestTests(unittest.TestCase):
    def test_swedish_decimal_and_non_area_rows(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "test.zip"
            csv = ("Utgiftsområde;Utgiftsområdesnamn;Anslag;Anslagsnamn;År;Statens budget;"
                   "Ändringsbudgetar;Utfall\n"
                   ";Utgiftstak;;Utgiftstak;2025;1856000;;1856000\n"
                   "01;Rikets styrelse;0101001;Testanslag;2025;190,463;2,5;191,25\n")
            with zipfile.ZipFile(path, "w") as archive:
                archive.writestr("outturn.csv", csv)
            rows = parse_archive(path)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["approved_budget_msek"], 190.463)
        self.assertEqual(rows[0]["amendments_msek"], 2.5)
        self.assertEqual(rows[0]["outturn_msek"], 191.25)


if __name__ == "__main__":
    unittest.main()
