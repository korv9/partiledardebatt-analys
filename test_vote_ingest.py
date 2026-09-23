import unittest

from vote_ingest import parse_status


class VoteIngestTests(unittest.TestCase):
    def test_only_motion_cited_in_voted_point_is_linked(self):
        doc = {"dok_id": "HC01SoU5", "beteckning": "SoU5", "titel": "Ungdomsvård"}
        payload = {
            "dokutskottsforslag": {"utskottsforslag": [
                {"punkt": "1", "votering_id": "abc-123", "rubrik": "Förslag 1",
                 "forslag": "Bifall propositionen och avslag motion 2024/25:3260."},
                {"punkt": "2", "rubrik": "Förslag 2", "forslag": "Motion 2024/25:3261."},
            ]},
            "dokreferens": {"referens": [
                {"referenstyp": "behandlar", "ref_dok_typ": "mot", "ref_dok_rm": "2024/25",
                 "ref_dok_bet": "3260", "ref_dok_id": "HC023260", "ref_dok_titel": "Motion A"},
                {"referenstyp": "behandlar", "ref_dok_typ": "mot", "ref_dok_rm": "2024/25",
                 "ref_dok_bet": "3261", "ref_dok_id": "HC023261", "ref_dok_titel": "Motion B"},
            ]},
        }
        decisions, links = parse_status("2024/25", doc, payload)
        self.assertEqual([row["vote_id"] for row in decisions], ["ABC-123"])
        self.assertEqual([row["motion_id"] for row in links], ["HC023260"])
        self.assertEqual(decisions[0]["source_url"], "https://data.riksdagen.se/dokument/HC01SoU5")


if __name__ == "__main__":
    unittest.main()
