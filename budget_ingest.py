"""Hämta utgiftsramar ur finansutskottets årliga budgetbetänkande FiU1."""
from __future__ import annotations

import argparse
import csv
import json
import re
import sqlite3
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path

import duckdb
import pandas as pd

API = "https://data.riksdagen.se/dokumentlista/"
PARTIES = {"S", "M", "V", "MP", "C", "L", "FP", "KD", "KDS", "SD", "NYD"}


def download(url: str) -> bytes:
    for attempt in range(4):
        try:
            request = urllib.request.Request(url, headers={"User-Agent": "partiledardebatt-analys/1.0"})
            with urllib.request.urlopen(request, timeout=120) as response:
                return response.read()
        except (OSError, TimeoutError):
            if attempt == 3:
                raise
            time.sleep(2**attempt)


class TableParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.rows: list[list[str]] = []
        self.row: list[str] | None = None
        self.cell: list[str] | None = None

    def handle_starttag(self, tag, attrs):
        if tag == "tr":
            self.row = []
        elif tag in {"td", "th"} and self.row is not None:
            self.cell = []

    def handle_data(self, data):
        if self.cell is not None:
            self.cell.append(data)

    def handle_endtag(self, tag):
        if tag in {"td", "th"} and self.cell is not None and self.row is not None:
            self.row.append(" ".join("".join(self.cell).split()))
            self.cell = None
        elif tag == "tr" and self.row is not None:
            if any(self.row):
                self.rows.append(self.row)
            self.row = None


def number(value: str) -> int | None:
    value = value.replace("−", "-").replace("–", "-").replace("±", "")
    value = re.sub(r"[\s\u00a0]", "", value)
    if not value or value in {"..", ".", "-"}:
        return None
    match = re.search(r"[-+]?\d+", value)
    return int(match.group()) if match else None


def budget_table(html: str) -> tuple[list[str], list[list[str]]]:
    titles = list(re.finditer(
        r"Regeringens och (?:motionärernas|oppositionspartiernas) förslag till utgiftsramar(?:\s+för)?\s+20\d{2}",
        html,
        flags=re.I,
    ))
    if not titles:
        raise ValueError("Hittade ingen jämförelsetabell för utgiftsramar")
    start_match = re.search(r"<table\b", html[titles[-1].end():], flags=re.I)
    start = titles[-1].end() + start_match.start() if start_match else -1
    end_match = re.search(r"</table\s*>", html[start:], flags=re.I) if start >= 0 else None
    end = start + end_match.end() if end_match else -1
    if start < 0 or end < 0:
        raise ValueError("Jämförelsetabellen saknar komplett HTML-tabell")
    parser = TableParser()
    parser.feed(html[start:end])
    header_index = next(
        (i for i, row in enumerate(parser.rows) if any(cell.upper() in PARTIES for cell in row)),
        None,
    )
    if header_index is None:
        raise ValueError("Kunde inte identifiera partikolumner")
    header = parser.rows[header_index]
    parties = [cell.upper().replace("FP", "L").replace("KDS", "KD")
               for cell in header if cell.upper() in PARTIES]
    data = [row for row in parser.rows[header_index + 1:]
            if len(row) >= 3 and re.fullmatch(r"\d{1,2}", row[0])]
    if len(data) < 20:
        raise ValueError(f"Bara {len(data)} utgiftsområden kunde läsas")
    return parties, data


def parse_document(html: str, session: str, document_id: str, source_url: str) -> list[dict]:
    parties, rows = budget_table(html)
    output = []
    budget_year = int("20" + session.split("/")[1])
    for row in rows:
        area = int(row[0])
        government = number(row[2])
        if government is None:
            continue
        common = {
            "session": session,
            "budget_year": budget_year,
            "expenditure_area": area,
            "expenditure_area_name": row[1],
            "government_amount_msek": government,
            "document_id": document_id,
            "source_url": source_url,
        }
        output.append({**common, "actor": "GOV", "proposal_type": "government",
                       "deviation_msek": 0, "amount_msek": government})
        for party, raw in zip(parties, row[3:3 + len(parties)]):
            deviation = number(raw)
            if deviation is not None:
                output.append({**common, "actor": party, "proposal_type": "party_motion",
                               "deviation_msek": deviation, "amount_msek": government + deviation})
    return output


def discover(session: str | None) -> list[dict]:
    query = {"doktyp": "bet", "org": "FiU", "bet": "FiU1", "sz": 100,
             "sort": "datum", "sortorder": "desc", "utformat": "json"}
    if session:
        query["rm"] = session
    payload = json.loads(download(API + "?" + urllib.parse.urlencode(query)).decode("utf-8"))
    documents = payload["dokumentlista"]["dokument"]
    if isinstance(documents, dict):
        documents = [documents]
    return [doc for doc in documents if doc.get("beteckning", "").casefold() == "fiu1"
            and (not session or doc.get("rm") == session)]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--session", help="Begränsa till exempelvis 2025/26")
    parser.add_argument("--from-session", default="2014/15", help="Äldsta riksmöte utan --session")
    parser.add_argument("--to-session", help="Senaste riksmöte utan --session")
    parser.add_argument("--refresh", action="store_true")
    parser.add_argument("--data-dir", default="data")
    args = parser.parse_args()
    root = Path(args.data_dir)
    raw = root / "raw" / "budgets"
    raw.mkdir(parents=True, exist_ok=True)
    frames, documents, errors = [], [], []
    grouped: dict[str, list[dict]] = {}
    for doc in discover(args.session):
        session = doc["rm"]
        if not args.session and session < args.from_session:
            continue
        if not args.session and args.to_session and session > args.to_session:
            continue
        grouped.setdefault(session, []).append(doc)
    for session, candidates in grouped.items():
        candidate_errors = []
        for doc in sorted(candidates, key=lambda item: (item["dok_id"].casefold().endswith("d2"), item["dok_id"])):
            document_id = doc["dok_id"]
            url = doc.get("dokument_url_html") or f"https://data.riksdagen.se/dokument/{document_id}"
            if url.startswith("//"):
                url = "https:" + url
            path = raw / f"{session.replace('/', '-')}_{document_id}.html"
            try:
                if args.refresh or not path.exists():
                    path.write_bytes(download(url))
                rows = parse_document(path.read_text(encoding="utf-8-sig"), session, document_id, url)
                frames.extend(rows)
                documents.append({"session": session, "document_id": document_id, "source_url": url,
                                  "rows": len(rows)})
                print(f"{session} {document_id}: {len(rows)} budgetrader", flush=True)
                break
            except Exception as exc:
                candidate_errors.append({"document_id": document_id, "error": str(exc)})
        else:
            errors.append({"session": session, "candidates": candidate_errors})
            print(f"SAKNAS {session}: ingen maskinläsbar jämförelsetabell", flush=True)
    if not frames:
        raise SystemExit("Inga budgetramar kunde importeras")
    columns = list(frames[0])
    csv_path = root / "budget_frames.csv"
    with csv_path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=columns)
        writer.writeheader()
        writer.writerows(frames)
    sqlite_path = root / "budgets.sqlite"
    with sqlite3.connect(sqlite_path) as db:
        db.execute("drop table if exists budget_frames")
        db.execute("create table budget_frames (session text, budget_year integer, expenditure_area integer, "
                   "expenditure_area_name text, government_amount_msek integer, document_id text, "
                   "source_url text, actor text, proposal_type text, deviation_msek integer, amount_msek integer, "
                   "primary key(session, expenditure_area, actor))")
        db.executemany("insert into budget_frames values (?,?,?,?,?,?,?,?,?,?,?)",
                       [[row[col] for col in columns] for row in frames])
    analytics = root / "analytics.duckdb"
    if analytics.exists():
        frame = pd.DataFrame(frames)
        with duckdb.connect(str(analytics)) as db:
            db.execute("create schema if not exists raw")
            db.register("budget_frame", frame)
            db.execute("create or replace table raw.budget_frames as select * from budget_frame")
    coverage = {"generated_at": datetime.now(timezone.utc).isoformat(), "documents": documents,
                "rows": len(frames), "errors": errors,
                "note": "Partikolumner är avvikelser från regeringens förslag; amount_msek är omräknat totalförslag."}
    (root / "budget_coverage.json").write_text(
        json.dumps(coverage, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"documents": len(documents), "rows": len(frames), "errors": len(errors)}))


if __name__ == "__main__":
    main()
