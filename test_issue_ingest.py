import json
import sqlite3
import tempfile
import unittest
import zipfile
from pathlib import Path

from ingest import FIELDS
from issue_ingest import import_file, issue_kind


class IssueIngestTests(unittest.TestCase):
    def test_source_categories_and_exclusions(self):
        self.assertEqual(issue_kind({'kammaraktivitet': 'ärendedebatt'}), 'ärendedebatt')
        self.assertEqual(issue_kind({'kammaraktivitet': 'föredragning av utskottsärende med eventuell debatt'}),
                         'föredragning av utskottsärende med eventuell debatt')
        self.assertEqual(issue_kind({'avsnittsrubrik': 'Särskild debatt om skolan'}), 'särskild debatt')
        self.assertIsNone(issue_kind({'kammaraktivitet': 'interpellationsdebatt'}))
        self.assertIsNone(issue_kind({'avsnittsrubrik': 'Partiledardebatt', 'kammaraktivitet': 'ärendedebatt'}))

    def test_fulltext_reply_and_repeat_import(self):
        row = dict.fromkeys(FIELDS, '')
        row.update(dok_id='TEST', dok_rm='2025/26', anforande_nummer='7',
                   avsnittsrubrik='Skolpolitik', kammaraktivitet='ärendedebatt',
                   anforandetext='<p>Åäö och full text.</p>', replik='Y')
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'source.zip'
            with zipfile.ZipFile(path, 'w') as archive:
                archive.writestr('speech.json', json.dumps({'anforande': row}))
            with sqlite3.connect(':memory:') as db:
                db.execute('CREATE TABLE issue_speeches (' +
                           ','.join(key + ' TEXT NOT NULL' for key in FIELDS) +
                           ', debate_kind TEXT NOT NULL, source_url TEXT NOT NULL, dataset_url TEXT NOT NULL, '
                           'PRIMARY KEY(dok_id, anforande_nummer))')
                for _ in range(2):
                    self.assertEqual(import_file(db, path, 'source')['speeches'], 1)
                self.assertEqual(db.execute(
                    'select anforandetext,replik,debate_kind from issue_speeches'
                ).fetchall(), [('Åäö och full text.', 'Y', 'ärendedebatt')])


if __name__ == '__main__':
    unittest.main()
