import unittest

from policy_ingest import claim_numbers, parse_committee_status


class PolicyIngestTests(unittest.TestCase):
    def test_claim_numbers_with_list_and_range(self):
        self.assertEqual(claim_numbers("yrkandena 1, 2, 4 och 5"), [1, 2, 4, 5])
        self.assertEqual(claim_numbers("yrkandena 7–9"), [7, 8, 9])

    def test_explicit_point_citations_and_reservation(self):
        payload = {
            "dokument": {"dok_id": "HC01TU1", "rm": "2024/25", "beteckning": "TU1", "titel": "Test"},
            "dokaktivitet": {"aktivitet": {"kod": "BES", "datum": "2025-02-12 00:00:00"}},
            "dokreferens": {"referens": [
                {"referenstyp": "behandlar", "ref_dok_typ": "mot", "ref_dok_rm": "2024/25",
                 "ref_dok_bet": "42", "ref_dok_id": "HC0242", "ref_dok_titel": "Motion"},
                {"referenstyp": "behandlar", "ref_dok_typ": "prop", "ref_dok_rm": "2024/25",
                 "ref_dok_bet": "10", "ref_dok_id": "HC0310", "ref_dok_titel": "Proposition"},
                {"referenstyp": "behandlar", "ref_dok_typ": "mot", "ref_dok_rm": "2024/25",
                 "ref_dok_bet": "99", "ref_dok_id": "HC0299", "ref_dok_titel": "Uncited"},
            ]},
            "dokutskottsforslag": {"utskottsforslag": [
                {"punkt": "1", "forslag": "Riksdagen avslår motion 2024/25:42 yrkandena 1 och 2 "
                                           "och bifaller proposition 2024/25:10.",
                 "votering_id": "abc", "beslutstyp": "röstning"},
                {"punkt": "2", "forslag": "Riksdagen avslår motion 2024/25:42.",
                 "beslutstyp": "beslut"},
            ]},
            "dokmotforslag": {"motforslag": {"nummer": "1", "partier": '"S","V"',
                                            "typ": "reservation", "utskottsforslag_punkt": "1"}},
        }
        points, citations, reservations = parse_committee_status(payload)
        self.assertEqual(len(points), 2)
        self.assertEqual(points[0]["decision_date"], "2025-02-12")
        self.assertEqual(points[1]["vote_id"], "")
        self.assertEqual({(c["point_id"], c["document_id"], c["claim_number"]) for c in citations}, {
            ("HC01TU1:1", "HC0242", 1), ("HC01TU1:1", "HC0242", 2),
            ("HC01TU1:1", "HC0310", None), ("HC01TU1:2", "HC0242", None),
        })
        self.assertEqual({r["party"] for r in reservations}, {"S", "V"})


if __name__ == "__main__":
    unittest.main()
