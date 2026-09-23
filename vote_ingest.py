"""Import member votes and the exact committee decision points they concern."""
from __future__ import annotations

import argparse
import csv
import html
import io
import json
import re
import sqlite3
import time
import urllib.parse
import urllib.request
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

import duckdb
import pandas as pd

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
RAW = DATA / "raw" / "votes"
API = "https://data.riksdagen.se"
VOTE_COLUMNS = (
    "session", "designation", "vote_id", "point", "member_name", "member_id",
    "party", "constituency", "vote", "subject", "seat", "gender", "birth_year", "vote_date",
)


def fetch(url: str) -> bytes:
    for attempt in range(4):
        try:
            request = urllib.request.Request(url, headers={"User-Agent": "partiledardebatt-analys/1.0"})
            with urllib.request.urlopen(request, timeout=120) as response:
                return response.read()
        except (OSError, TimeoutError):
            if attempt == 3:
                raise
            time.sleep(2 ** attempt)
    raise RuntimeError("Download failed")


def rows(value):
    if not value:
        return []
    return value if isinstance(value, list) else [value]


def plain(value: str | None) -> str:
    return " ".join(re.sub(r"<[^>]+>", " ", html.unescape(value or "")).split())


def read_votes(session: str, refresh: bool) -> list[dict]:
    code = session.replace("/", "")
    path = RAW / f"votering-{code}.csv.zip"
    if refresh or not path.exists():
        path.write_bytes(fetch(f"{API}/dataset/votering/votering-{code}.csv.zip"))
    with zipfile.ZipFile(path) as archive:
        csv_name = next(name for name in archive.namelist() if name.endswith(".csv"))
        reader = csv.reader(io.TextIOWrapper(archive.open(csv_name), encoding="utf-8-sig", newline=""))
        data = [dict(zip(VOTE_COLUMNS, row, strict=True)) for row in reader]
    if any(row["session"] != session for row in data):
        raise ValueError(f"Unexpected session in {path}")
    return data


def documents(session: str) -> dict[str, dict]:
    found = {}
    page = 1
    while True:
        query = urllib.parse.urlencode({"doktyp": "bet", "rm": session, "sz": 500,
                                        "p": page, "utformat": "json"})
        result = json.loads(fetch(f"{API}/dokumentlista/?{query}").decode("utf-8-sig"))["dokumentlista"]
        for doc in rows(result.get("dokument")):
            found[doc["beteckning"].casefold()] = doc
        if page >= int(result.get("@sidor") or 1):
            break
        page += 1
    return found


def status(document_id: str, refresh: bool) -> dict:
    path = RAW / f"status-{document_id}.json"
    if refresh or not path.exists():
        path.write_bytes(fetch(f"{API}/dokumentstatus/{urllib.parse.quote(document_id)}.json"))
    return json.loads(path.read_text(encoding="utf-8-sig"))["dokumentstatus"]


def parse_status(session: str, doc: dict, payload: dict) -> tuple[list[dict], list[dict]]:
    document_id = doc["dok_id"]
    ref_rows = rows((payload.get("dokreferens") or {}).get("referens"))
    motions = {
        f'{r.get("ref_dok_rm")}:{r.get("ref_dok_bet")}': r
        for r in ref_rows if r.get("referenstyp") == "behandlar" and r.get("ref_dok_typ") == "mot"
    }
    decisions, links = [], []
    for item in rows((payload.get("dokutskottsforslag") or {}).get("utskottsforslag")):
        vote_id = str(item.get("votering_id") or "").upper()
        if not vote_id:
            continue  # A decision without a recorded roll-call is not an individual vote.
        proposal = plain(item.get("forslag"))
        decisions.append({
            "vote_id": vote_id, "session": session, "document_id": document_id,
            "designation": doc["beteckning"], "point": str(item.get("punkt") or ""),
            "title": plain(doc.get("titel")), "point_heading": plain(item.get("rubrik")),
            "proposal_text": proposal, "winning_side": item.get("vinnare") or "",
            "decision_date": (doc.get("beslutsdag") or "")[:10],
            "source_url": f"{API}/dokument/{urllib.parse.quote(document_id)}",
            "status_url": f"{API}/dokumentstatus/{urllib.parse.quote(document_id)}.json",
        })
        # Only a motion explicitly cited within this point is attached to this vote.
        for citation in sorted(set(re.findall(r"\b20\d{2}/\d{2}:\d+\b", proposal))):
            ref = motions.get(citation)
            if ref:
                links.append({
                    "vote_id": vote_id, "motion_id": ref["ref_dok_id"],
                    "motion_reference": citation, "motion_title": plain(ref.get("ref_dok_titel")),
                    "motion_author": plain(ref.get("ref_dok_subtitel")),
                    "motion_url": f'{API}/dokument/{ref["ref_dok_id"]}',
                })
    return decisions, links


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--session", action="append", default=[], help="Riksmöte, exempelvis 2024/25")
    parser.add_argument("--refresh", action="store_true")
    args = parser.parse_args()
    sessions = list(dict.fromkeys(args.session or ["2024/25"]))
    RAW.mkdir(parents=True, exist_ok=True)
    votes, decisions, links, errors = [], [], [], []
    for session in sessions:
        if not re.fullmatch(r"(?:19|20)\d{2}/\d{2}", session):
            parser.error(f"Ogiltigt riksmöte: {session}")
        session_votes = read_votes(session, args.refresh)
        votes.extend(session_votes)
        by_designation = documents(session)
        voted_designations = sorted({row["designation"] for row in session_votes})
        before = len(decisions)
        with ThreadPoolExecutor(max_workers=6) as pool:
            jobs = {}
            for designation in voted_designations:
                doc = by_designation.get(designation.casefold())
                if doc:
                    jobs[pool.submit(status, doc["dok_id"], args.refresh)] = (designation, doc)
                else:
                    errors.append({"session": session, "designation": designation, "error": "missing document"})
            for job in as_completed(jobs):
                designation, doc = jobs[job]
                try:
                    d, m = parse_status(session, doc, job.result())
                    decisions.extend(d)
                    links.extend(m)
                except (OSError, ValueError, KeyError, TypeError) as exc:
                    errors.append({"session": session, "designation": designation, "error": str(exc)})
        print(f"{session}: {len(session_votes)} ledamotsröster, {len(decisions)-before} beslutspunkter", flush=True)
    if not votes or not decisions:
        raise SystemExit("Inga röstdata eller beslutspunkter kunde importeras")
    frames = {"votes": pd.DataFrame(votes), "decisions": pd.DataFrame(decisions),
              "decision_motions": pd.DataFrame(links, columns=["vote_id", "motion_id", "motion_reference",
                                                              "motion_title", "motion_author", "motion_url"])}
    with sqlite3.connect(DATA / "votes.sqlite") as db:
        for table, frame in frames.items():
            frame.to_sql(table, db, if_exists="replace", index=False)
    with duckdb.connect(str(DATA / "analytics.duckdb")) as db:
        db.execute("create schema if not exists raw")
        for table, frame in frames.items():
            db.register("source_frame", frame)
            db.execute(f"create or replace table raw.{table} as select * from source_frame")
            db.unregister("source_frame")
    coverage = {
        "generated_at": datetime.now(timezone.utc).isoformat(), "sessions": sessions,
        "member_votes": len(votes), "voted_points": len(decisions), "motion_point_links": len(links),
        "unmatched_vote_ids": len({v["vote_id"] for v in votes} - {d["vote_id"] for d in decisions}),
        "errors": errors,
        "note": "En votering gäller en betänkandepunkt, inte automatiskt varje behandlad motion."
    }
    (DATA / "vote_coverage.json").write_text(json.dumps(coverage, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in coverage.items() if k != "errors"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
