"""Import selected, hash-verified SFS snapshots using Allegoria's existing parser.

This is a law-text layer, not a speech-to-provision match or a direction score.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import re
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

import duckdb
import pandas as pd

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"


def load_allegoria(allegoria_root: Path):
    if not (allegoria_root / "simulacria" / "domains" / "sfs.py").is_file():
        raise FileNotFoundError(f"Allegoria SFS adapter not found in {allegoria_root}")
    sys.path.insert(0, str(allegoria_root))
    resolver = importlib.import_module("simulacria.domains.sfs").resolve
    parser = importlib.import_module("products.allegoria.sfs_parser").parse_sfs_html
    return resolver, parser


def import_document(document_id: str, allegoria_root: Path, resolver, parser) -> list[dict]:
    if not re.fullmatch(r"sfs-\d{4}-\d+", document_id):
        raise ValueError(f"Invalid SFS document id: {document_id}")
    bronze_path = allegoria_root / "data" / "bronze" / "sfs" / f"{document_id}.json"
    bronze = json.loads(bronze_path.read_text(encoding="utf-8"))
    if bronze["document_id"] != document_id:
        raise ValueError(f"Bronze document id mismatch: {document_id}")
    parsed = parser(bronze["html"], document_id)
    result = []
    for provision in parsed:
        provision_id = f'{document_id}:{provision["provision_suffix"]}'
        source = resolver(provision_id, allegoria_root, {})  # Verifies original XML and bronze.
        if source.text != provision["text"]:
            raise ValueError(f"Parsed provision changed during verification: {provision_id}")
        result.append({
            "provision_id": provision_id,
            "sfs_document_id": document_id,
            "provision_suffix": provision["provision_suffix"],
            "kind": provision["kind"],
            "label": provision["label"],
            "chapter": provision["chapter"],
            "heading": provision["heading"],
            "provision_order": provision["order"],
            "text": source.text,
            "text_sha256": hashlib.sha256(source.text.encode("utf-8")).hexdigest(),
            "document_title": bronze["title"],
            "snapshot_version": bronze["version"],
            "snapshot_retrieved_at": bronze["retrieved_at"],
            "source_sha256": source.source_sha256,
            "source_url": source.source_url,
            "valid_from": None,
            "valid_to": None,
            "temporal_status": "unverified_snapshot",
        })
    return result


def main() -> None:
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--allegoria-root", type=Path, default=ROOT.parent / "allegoria")
    cli.add_argument("--document-id", action="append", required=True,
                     help="Existing Allegoria bronze document, e.g. sfs-1982-80")
    args = cli.parse_args()
    allegoria_root = args.allegoria_root.resolve()
    resolver, parser = load_allegoria(allegoria_root)
    rows = []
    for document_id in dict.fromkeys(args.document_id):
        rows.extend(import_document(document_id, allegoria_root, resolver, parser))
    frame = pd.DataFrame(rows)
    if frame.empty or frame.provision_id.duplicated().any():
        raise ValueError("SFS import produced no provisions or duplicate provision ids")
    with sqlite3.connect(DATA / "sfs.sqlite") as db:
        frame.to_sql("sfs_provisions", db, if_exists="replace", index=False)
    with duckdb.connect(str(DATA / "analytics.duckdb")) as db:
        db.execute("create schema if not exists raw")
        db.register("source_frame", frame)
        db.execute("create or replace table raw.sfs_provisions as select * from source_frame")
    coverage = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "documents": list(dict.fromkeys(args.document_id)), "provisions": len(frame),
        "temporal_status": "unverified_snapshot",
        "note": "Exact source bytes and parsed provisions are verified by Allegoria. "
                "A snapshot version is not a provision-level effective date; no direction score is computed.",
    }
    (DATA / "sfs_coverage.json").write_text(
        json.dumps(coverage, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(coverage, ensure_ascii=False))


if __name__ == "__main__":
    main()
