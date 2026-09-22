import unittest

from budget_ingest import number, parse_document


class BudgetIngestTests(unittest.TestCase):
    def test_number_handles_swedish_budget_format(self):
        self.assertEqual(number("−1\u00a0289"), -1289)
        self.assertEqual(number("±0"), 0)
        self.assertIsNone(number(".."))

    def test_parses_government_and_party_deviation(self):
        body = "".join(
            f"<tr><td>{i}</td><td>Område {i}</td><td>1 000</td><td>−10</td><td>20</td></tr>"
            for i in range(1, 21)
        )
        html = ("<p>Regeringens och motionärernas förslag till utgiftsramar 2026</p>"
                "<table><tr><td></td><td></td><td>förslag</td><td>S</td><td>V</td></tr>"
                + body + "</table>")
        rows = parse_document(html, "2025/26", "HD01FiU1", "https://example.test")
        self.assertEqual(len(rows), 60)
        social_democrats = next(row for row in rows if row["actor"] == "S" and row["expenditure_area"] == 1)
        self.assertEqual(social_democrats["amount_msek"], 990)
        self.assertEqual(social_democrats["deviation_msek"], -10)


if __name__ == "__main__":
    unittest.main()
