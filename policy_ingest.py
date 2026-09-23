"""Prepare committee points, explicit document/claim citations and parliamentary activity."""
from __future__ import annotations

import argparse
import json
import re
import sqlite3
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path

import duckdb
import pandas as pd

from vote_ingest import API, DATA, fetch, plain, rows

RAW = DATA / "raw" / "policy"
PARTIES = {"S", "M", "V", "MP", "C", "L", "KD", "SD", "NYD"}
DOC_TYPES = ("fr", "ip", "prop")
CITATION = re.compile(r"\b(20\d{2}/\d{2}:\d+)\b")
CLAIMS = re.compile(r"yrkand(?:e|ena)\s+([\d,\s–-]+(?:och\s*\d+)?)", re.IGNORECASE)


def claim_numbers(fragment: str) -> list[int]:
    match = CLAIMS.search(fragment)
    if not match:
        return []
    expression = match.group(1).replace("och", ",")
    result: set[int] = set()
    for part in expression.split(","):
        part = part.strip()
        range_match = re.fullmatch(r"(\d+)\s*[–-]\s*(\d+)", part)
        if range_match:
            start, end = map(int, range_match.groups())
            if 0 < start <= end <= start + 100:
                result.update(range(start, end + 1))
        elif part.isdigit():
            result.add(int(part))
    return sorted(result)


def parse_committee_status(payload: dict) -> tuple[list[dict], list[dict], list[dict]]:
    document = payload["dokument"]
    document_id = document["dok_id"]
    session = document["rm"]
    reference_map = {
        f'{r.get("ref_dok_rm")}:{r.get("ref_dok_bet")}': r
        for r in rows((payload.get("dokreferens") or {}).get("referens"))
        if r.get("referenstyp") == "behandlar" and r.get("ref_dok_typ") in {"mot", "prop"}
    }
    points, citations, reservations = [], [], []
    source_url = f"{API}/dokument/{urllib.parse.quote(document_id)}"
    decision_dates = [str(activity.get("datum") or "")[:10]
                      for activity in rows((payload.get("dokaktivitet") or {}).get("aktivitet"))
                      if activity.get("kod") == "BES" and activity.get("datum")]
    decision_date = max(decision_dates, default="")
    for item in rows((payload.get("dokutskottsforslag") or {}).get("utskottsforslag")):
        point = str(item.get("punkt") or "").strip()
        if not point:
            continue
        point_id = f"{document_id}:{point}"
        proposal_text = plain(item.get("forslag"))
        points.append({
            "point_id": point_id, "session": session, "document_id": document_id,
            "designation": document.get("beteckning") or "", "point": point,
            "title": plain(document.get("titel")), "point_heading": plain(item.get("rubrik")),
            "proposal_text": proposal_text, "decision_type": item.get("beslutstyp") or "",
            "vote_id": str(item.get("votering_id") or "").upper(),
            "winning_side": item.get("vinnare") or "",
            "decision_date": decision_date,
            "source_url": source_url,
        })
        matches = list(CITATION.finditer(proposal_text))
        for index, match in enumerate(matches):
            ref = reference_map.get(match.group(1))
            if not ref:
                continue
            fragment = proposal_text[match.end():matches[index + 1].start() if index + 1 < len(matches) else len(proposal_text)]
            numbers = claim_numbers(fragment) if ref.get("ref_dok_typ") == "mot" else []
            for number in numbers or [None]:
                citations.append({
                    "point_id": point_id, "document_id": ref["ref_dok_id"],
                    "document_type": ref["ref_dok_typ"], "document_reference": match.group(1),
                    "claim_number": number, "claim_scope": "numbered_claim" if number is not None else "document_unspecified",
                    "document_title": plain(ref.get("ref_dok_titel")),
                    "document_author": plain(ref.get("ref_dok_subtitel")),
                    "document_url": f'{API}/dokument/{urllib.parse.quote(ref["ref_dok_id"])}',
                })
    for item in rows((payload.get("dokmotforslag") or {}).get("motforslag")):
        point = str(item.get("utskottsforslag_punkt") or "").strip()
        number = str(item.get("nummer") or "").strip()
        if not point or not number:
            continue
        parties = re.findall(r'"([A-Z]+)"', item.get("partier") or "")
        for party in parties or [""]:
            reservations.append({
                "point_id": f"{document_id}:{point}", "reservation_number": number,
                "party": party, "proposal_type": item.get("typ") or "",
                "heading": plain(item.get("rubrik")), "source_url": source_url,
            })
    return points, citations, reservations


def listing(session: str, doc_type: str, refresh: bool) -> list[dict]:
    result = []
    page = 1
    while True:
        path = RAW / f"list-{session.replace('/', '')}-{doc_type}-{page}.json"
        if refresh or not path.exists():
            query = urllib.parse.urlencode({"doktyp": doc_type, "rm": session, "sz": 500,
                                            "p": page, "utformat": "json"})
            path.write_bytes(fetch(f"{API}/dokumentlista/?{query}"))
        payload = json.loads(path.read_text(encoding="utf-8-sig"))["dokumentlista"]
        result.extend(rows(payload.get("dokument")))
        if page >= int(payload.get("@sidor") or 1):
            break
        page += 1
    return result


def parse_activity(doc: dict) -> dict:
    doc_type = doc["doktyp"]
    party = (doc.get("organ") or "").upper() if doc_type in {"fr", "ip"} else ""
    return {
        "document_id": doc["dok_id"], "session": doc["rm"], "document_type": doc_type,
        "designation": doc.get("beteckning") or "", "document_date": (doc.get("datum") or "")[:10],
        "title": plain(doc.get("titel")), "subtitle": plain(doc.get("undertitel")),
        "actor_party": party if party in PARTIES else "",
        "government_department": (doc.get("organ") or "") if doc_type == "prop" else "",
        "status": doc.get("status") or "",
        "source_url": f'{API}/dokument/{urllib.parse.quote(doc["dok_id"])}',
    }


def write_table(db: duckdb.DuckDBPyConnection, name: str, frame: pd.DataFrame) -> None:
    db.register("source_frame", frame)
    db.execute(f"create or replace table raw.{name} as select * from source_frame")
    db.unregister("source_frame")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--session", action="append", default=[], help="Riksmöte, exempelvis 2024/25")
    parser.add_argument("--refresh", action="store_true")
    args = parser.parse_args()
    sessions = list(dict.fromkeys(args.session or ["2024/25", "2025/26"]))
    RAW.mkdir(parents=True, exist_ok=True)
    points, citations, reservations, activities = [], [], [], []
    status_files = sorted((DATA / "raw" / "votes").glob("status-*.json"))
    for session in sessions:
        if not re.fullmatch(r"(?:19|20)\d{2}/\d{2}", session):
            parser.error(f"Ogiltigt riksmöte: {session}")
        for path in status_files:
            payload = json.loads(path.read_text(encoding="utf-8-sig"))["dokumentstatus"]
            if payload.get("dokument", {}).get("rm") != session:
                continue
            p, c, r = parse_committee_status(payload)
            points.extend(p)
            citations.extend(c)
            reservations.extend(r)
        for doc_type in DOC_TYPES:
            activities.extend(parse_activity(doc) for doc in listing(session, doc_type, args.refresh))
    if not points:
        raise SystemExit("No cached committee statuses; run vote_ingest.py first")
    frames = {
        "committee_points": pd.DataFrame(points).drop_duplicates("point_id"),
        "decision_citations": pd.DataFrame(citations).drop_duplicates(
            ["point_id", "document_id", "claim_number"]),
        "decision_reservations": pd.DataFrame(reservations).drop_duplicates(
            ["point_id", "reservation_number", "party"]),
        "policy_documents": pd.DataFrame(activities).drop_duplicates("document_id"),
    }
    with sqlite3.connect(DATA / "policy.sqlite") as db:
        for name, frame in frames.items():
            frame.to_sql(name, db, if_exists="replace", index=False)
    with duckdb.connect(str(DATA / "analytics.duckdb")) as db:
        db.execute("create schema if not exists raw")
        for name, frame in frames.items():
            write_table(db, name, frame)
    coverage = {"generated_at": datetime.now(timezone.utc).isoformat(), "sessions": sessions,
                "committee_points": len(frames["committee_points"]),
                "points_without_vote": int((frames["committee_points"].vote_id == "").sum()),
                "explicit_document_claim_citations": len(frames["decision_citations"]),
                "reservations_by_party": len(frames["decision_reservations"]),
                "policy_documents": len(frames["policy_documents"]),
                "note": "Citations are exact document/claim references, not automatic agreement. "
                        "Question/interpellation actors come from document-list metadata."}
    (DATA / "policy_coverage.json").write_text(json.dumps(coverage, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(coverage, ensure_ascii=False))


if __name__ == "__main__":
    main()
