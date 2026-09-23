import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from sfs_bridge import import_document


class SfsBridgeTests(unittest.TestCase):
    def test_verified_provision_keeps_snapshot_and_blocks_direction(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            path = root / "data/bronze/sfs/sfs-1982-80.json"
            path.parent.mkdir(parents=True)
            path.write_text(json.dumps({"document_id": "sfs-1982-80", "html": "<p>source</p>",
                                        "title": "Law", "version": "t.o.m. SFS 2022:836",
                                        "retrieved_at": "2026-08-20T00:00:00Z"}), encoding="utf-8")
            parser = lambda _html, _id: [{"provision_suffix": "P1", "kind": "paragraph",
                                          "label": "1 §", "chapter": "", "heading": "",
                                          "order": 1, "text": "A rule."}]
            resolver = lambda _id, _root, _spec: SimpleNamespace(
                text="A rule.", source_sha256="source-hash", source_url="https://example.test/#P1")
            rows = import_document("sfs-1982-80", root, resolver, parser)
        self.assertEqual(rows[0]["provision_id"], "sfs-1982-80:P1")
        self.assertEqual(rows[0]["snapshot_version"], "t.o.m. SFS 2022:836")
        self.assertEqual(rows[0]["temporal_status"], "unverified_snapshot")
        self.assertIsNone(rows[0]["valid_from"])

    def test_parser_resolver_mismatch_fails(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            path = root / "data/bronze/sfs/sfs-1982-80.json"
            path.parent.mkdir(parents=True)
            path.write_text(json.dumps({"document_id": "sfs-1982-80", "html": "source",
                                        "title": "Law", "version": "v1",
                                        "retrieved_at": "2026-08-20T00:00:00Z"}), encoding="utf-8")
            parser = lambda _html, _id: [{"provision_suffix": "P1", "text": "A rule."}]
            resolver = lambda _id, _root, _spec: SimpleNamespace(text="Different text")
            with self.assertRaisesRegex(ValueError, "changed during verification"):
                import_document("sfs-1982-80", root, resolver, parser)


if __name__ == "__main__":
    unittest.main()
