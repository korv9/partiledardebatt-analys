"""Import Statskontoret's annual state-budget expenditure outturn CSV archive."""
from __future__ import annotations

import argparse
import csv
import io
import json
import sqlite3
import urllib.request
import zipfile
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path

import duckdb
import pandas as pd

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
RAW = DATA / "raw" / "outturn"
SOURCE_PAGE = "https://www.statskontoret.se/analys-och-statistik/oppna-data/arsutfall/"
SOURCE_URL = (
    "https://www.statskontoret.se/OpenDataArsUtfallPage/GetFile?Year=2025"
    "&documentType=Utgift&fileName=%C3%85rsutfall+utgifter+1997+-+2025%2C+definitivt.zip"
    "&fileType=Zip&month=0&status=Definitiv"
)


def amount(value: str) -> float | None:
    value = value.strip().replace("\u00a0", "").replace(" ", "").replace(",", ".")
    if not value:
        return None
    try:
        return float(Decimal(value))
    except InvalidOperation as exc:
        raise ValueError(f"Invalid budget amount: {value!r}") from exc


def parse_archive(path: Path) -> list[dict]:
    with zipfile.ZipFile(path) as archive:
        names = [name for name in archive.namelist() if name.lower().endswith(".csv")]
        if len(names) != 1:
            raise ValueError(f"Expected one CSV in {path}, found {len(names)}")
        with archive.open(names[0]) as stream:
            reader = csv.DictReader(io.TextIOWrapper(stream, encoding="utf-8-sig"), delimiter=";")
            required = {"Utgiftsområde", "Utgiftsområdesnamn", "Anslag", "Anslagsnamn", "År",
                        "Statens budget", "Ändringsbudgetar", "Utfall"}
            if not required.issubset(reader.fieldnames or []):
                raise ValueError(f"Missing columns: {required - set(reader.fieldnames or [])}")
            output = []
            for row in reader:
                area = row["Utgiftsområde"].strip()
                if not area.isdigit() or not 1 <= int(area) <= 27:
                    continue  # Totals, expenditure ceiling and other non-area lines.
                year = int(row["År"])
                output.append({
                    "budget_year": year,
                    "expenditure_area": int(area),
                    "expenditure_area_name": row["Utgiftsområdesnamn"].strip(),
                    "appropriation_code": row["Anslag"].strip(),
                    "appropriation_name": row["Anslagsnamn"].strip(),
                    "approved_budget_msek": amount(row["Statens budget"]),
                    "amendments_msek": amount(row["Ändringsbudgetar"]),
                    "outturn_msek": amount(row["Utfall"]),
                    "source_url": SOURCE_PAGE,
                })
    if not output:
        raise ValueError("No expenditure-area appropriations found")
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, help="Local Statskontoret ZIP; defaults to cached 2025 archive")
    parser.add_argument("--refresh", action="store_true")
    args = parser.parse_args()
    RAW.mkdir(parents=True, exist_ok=True)
    path = args.archive or RAW / "arsutfall-utgifter-2025.zip"
    if args.refresh or not path.exists():
        request = urllib.request.Request(SOURCE_URL, headers={"User-Agent": "partiledardebatt-analys/1.0"})
        with urllib.request.urlopen(request, timeout=120) as response:
            path.write_bytes(response.read())
    rows = parse_archive(path)
    frame = pd.DataFrame(rows)
    if frame.duplicated(["budget_year", "expenditure_area", "appropriation_code"]).any():
        raise ValueError("Duplicate appropriation/year/area in source archive")
    with sqlite3.connect(DATA / "outturn.sqlite") as db:
        frame.to_sql("budget_outturn_appropriations", db, if_exists="replace", index=False)
    with duckdb.connect(str(DATA / "analytics.duckdb")) as db:
        db.execute("create schema if not exists raw")
        db.register("source_frame", frame)
        db.execute("create or replace table raw.budget_outturn_appropriations as select * from source_frame")
    coverage = {"generated_at": datetime.now(timezone.utc).isoformat(),
                "source_url": SOURCE_PAGE, "archive": path.name, "rows": len(rows),
                "first_year": int(frame.budget_year.min()), "last_year": int(frame.budget_year.max()),
                "note": "Amounts in millions of SEK. Outturn is spending, not policy effectiveness."}
    (DATA / "outturn_coverage.json").write_text(json.dumps(coverage, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(coverage, ensure_ascii=False))


if __name__ == "__main__":
    main()
