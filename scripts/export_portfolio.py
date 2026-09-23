"""Export the dbt gold layer as small, static files for a portfolio site."""
from __future__ import annotations

import csv
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[1]
DATABASE = ROOT / "data" / "analytics.duckdb"
OUTPUT = ROOT / "portfolio-data"
SCHEMA_VERSION = 1
README = """# Portfolio-data

Den här katalogen genereras av `python scripts/export_portfolio.py` efter `dbt build`.

Börja med `manifest.json` eller `overview.json`. JSON är avsett för webbsidan och CSV för nedladdning och kontroll.

```javascript
const topics = await fetch('/data/partiledardebatter/topics/summary.json')
  .then(response => response.json());

console.log(topics.data);
```

Alla JSON-filer innehåller `schema_version`, `generated_at` och `data`. UMAP är uppdelad per riksmöte under `sessions/<riksmöte>/umap.json`, med högst 400 deterministiskt valda punkter per fil.

Budgetramar finns i `budgets/summary.json` och per riksmöte i `sessions/<riksmöte>/budgets.json`. `GOV` är regeringens samlade förslag; övriga aktörer är partiernas budgetmotioner.

Budgeten kan visas intill UMAP-kartan med samma filter för parti och riksmöte. Beloppen är inte koordinater i den semantiska kartan.

`votes/summary.json` och `sessions/<riksmöte>/votes.json` visar registrerade röster per parti och beslutspunkt. `decision-motions.json` innehåller bara motioner som uttryckligen nämns i just den beslutspunkten. En röst gäller beslutspunkten, inte varje motion var för sig.

`decision-speech-links.json` kopplar beslut till tidigare tal från samma parti via textlikhet. Länken säger inget om talarens ståndpunkt i sakfrågan.
"""


def safe_part(value: str) -> str:
    return value.replace("/", "-").replace(" ", "-").lower()


def json_value(value):
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return value


def records(db: duckdb.DuckDBPyConnection, query: str, params=None) -> list[dict]:
    cursor = db.execute(query, params or [])
    columns = [item[0] for item in cursor.description]
    return [dict(zip(columns, map(json_value, row))) for row in cursor.fetchall()]


def write_json(path: Path, data, generated_at: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    document = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": generated_at,
        "data": data,
    }
    path.write_text(
        json.dumps(document, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )


def write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def add_file(manifest: list[dict], path: Path, rows: int, description: str) -> None:
    manifest.append(
        {
            "path": path.relative_to(OUTPUT).as_posix(),
            "rows": rows,
            "bytes": path.stat().st_size,
            "description": description,
        }
    )


def export_pair(db, manifest, stem, query, generated_at, description, params=None):
    rows = records(db, query, params)
    json_path = OUTPUT / f"{stem}.json"
    csv_path = OUTPUT / f"{stem}.csv"
    write_json(json_path, rows, generated_at)
    write_csv(csv_path, rows)
    add_file(manifest, json_path, len(rows), description)
    add_file(manifest, csv_path, len(rows), description + " (CSV)")
    return rows


def main() -> None:
    if not DATABASE.exists():
        raise SystemExit("Kör först features.py och dbt build; analytics.duckdb saknas.")
    if OUTPUT.exists():
        # The directory is generated in full; remove only this explicit project path.
        shutil.rmtree(OUTPUT)
    OUTPUT.mkdir()
    (OUTPUT / "README.md").write_text(README, encoding="utf-8")
    generated_at = datetime.now(timezone.utc).isoformat()
    cluster_metrics = json.loads((ROOT / "data" / "features" / "metrics.json").read_text(encoding="utf-8"))
    manifest: list[dict] = []

    with duckdb.connect(str(DATABASE), read_only=True) as db:
        overview = {
            "imported_speeches": db.execute("select count(*) from raw.speeches").fetchone()[0],
            "analyzed_speeches": db.execute("select count(*) from stg_speeches where eligible").fetchone()[0],
            "analyzed_segments": db.execute("select count(*) from int_segments").fetchone()[0],
            "sessions": db.execute("select count(distinct session) from stg_speeches where eligible").fetchone()[0],
            "first_date": json_value(db.execute("select min(speech_date) from stg_speeches where eligible").fetchone()[0]),
            "last_date": json_value(db.execute("select max(speech_date) from stg_speeches where eligible").fetchone()[0]),
            "topic_method": cluster_metrics["clustering"] + "; 2D UMAP for display",
            "cluster_silhouette_cosine_sample": cluster_metrics.get("silhouette_cosine_original_sample"),
            "cluster_unclustered_share": cluster_metrics["unclustered_share"],
            "umap_note": "Deterministic sample of at most 400 segments per session",
            "budget_frame_rows": db.execute("select count(*) from gold_budget_frames").fetchone()[0],
            "vote_sessions": db.execute("select count(distinct session) from gold_party_vote_decisions").fetchone()[0],
        }
        overview_path = OUTPUT / "overview.json"
        write_json(overview_path, overview, generated_at)
        add_file(manifest, overview_path, 1, "Översikt och metodmetadata")

        export_pair(
            db, manifest, "topics/summary",
            "select * from gold_topic_summary",
            generated_at, "Ämnesstorlek för hela materialet",
        )
        export_pair(
            db, manifest, "speakers/summary",
            "select * from gold_speakers",
            generated_at, "Talare, parti, tal och textmängd",
        )
        export_pair(
            db, manifest, "similarity/top",
            "select * from gold_similar_speeches",
            generated_at, "Liknande tal över partigränser",
        )
        export_pair(
            db, manifest, "budgets/summary",
            "select * from gold_budget_frames order by session, actor, expenditure_area",
            generated_at, "Föreslagna budgetramar per aktör och utgiftsområde",
        )
        export_pair(
            db, manifest, "budgets/speech-alignment",
            "select * from gold_budget_speech_alignment order by session, party, expenditure_area",
            generated_at, "Jämförelse mellan budgetandel och debattens språkliga uppmärksamhet",
        )
        export_pair(
            db, manifest, "votes/summary",
            "select session,party,count(*) as decision_points,"
            "sum(case when party_position='Ja' then 1 else 0 end) as party_yes,"
            "sum(case when party_position='Nej' then 1 else 0 end) as party_no,"
            "sum(case when party_position='Avstår' then 1 else 0 end) as party_abstain,"
            "sum(yes_votes) as member_yes,sum(no_votes) as member_no,"
            "sum(abstain_votes) as member_abstain,sum(absent_votes) as member_absent "
            "from gold_party_vote_decisions group by session,party order by session,party",
            generated_at, "Röstsammanfattning per parti och riksmöte",
        )

        sessions = [row[0] for row in db.execute(
            "select distinct session from gold_topic_by_session_party order by session"
        ).fetchall()]
        for session in sessions:
            part = safe_part(session)
            export_pair(
                db, manifest, f"sessions/{part}/topics",
                "select * from gold_topic_by_session_party where session=? order by party, words desc",
                generated_at, f"Ämnen per parti under riksmöte {session}", [session],
            )
            points = records(
                db,
                "select * from gold_umap_points where session=? order by chunk_id",
                [session],
            )
            path = OUTPUT / f"sessions/{part}/umap.json"
            write_json(path, points, generated_at)
            add_file(manifest, path, len(points), f"UMAP-punkter för riksmöte {session}")
            budget_rows = records(
                db,
                "select * from gold_budget_frames where session=? order by actor, expenditure_area",
                [session],
            )
            if budget_rows:
                budget_path = OUTPUT / f"sessions/{part}/budgets.json"
                write_json(budget_path, budget_rows, generated_at)
                add_file(manifest, budget_path, len(budget_rows), f"Budgetramar för riksmöte {session}")
            alignment_rows = records(
                db,
                "select * from gold_budget_speech_alignment where session=? order by party, expenditure_area",
                [session],
            )
            if alignment_rows:
                alignment_path = OUTPUT / f"sessions/{part}/budget-speech-alignment.json"
                write_json(alignment_path, alignment_rows, generated_at)
                add_file(manifest, alignment_path, len(alignment_rows),
                         f"Budget–debatt-jämförelse för riksmöte {session}")
            vote_rows = records(
                db,
                "select vote_id,session,designation,point,party,vote_date,title,point_heading,"
                "winning_side,cited_motion_count,yes_votes,no_votes,abstain_votes,absent_votes,"
                "party_position,source_url from gold_party_vote_decisions "
                "where session=? order by vote_date,designation,point,party",
                [session],
            )
            if vote_rows:
                vote_path = OUTPUT / f"sessions/{part}/votes.json"
                write_json(vote_path, vote_rows, generated_at)
                add_file(manifest, vote_path, len(vote_rows), f"Partiröster per beslutspunkt {session}")
                motion_rows = records(
                    db,
                    "select m.* from raw.decision_motions m join stg_decisions d "
                    "on upper(m.vote_id)=d.vote_id where d.session=? order by m.vote_id,m.motion_id",
                    [session],
                )
                motion_path = OUTPUT / f"sessions/{part}/decision-motions.json"
                write_json(motion_path, motion_rows, generated_at)
                add_file(manifest, motion_path, len(motion_rows),
                         f"Uttryckligen citerade motioner i voterade beslutspunkter {session}")
                speech_link_rows = records(
                    db,
                    "select * from gold_decision_speech_links where session=? "
                    "order by vote_date, vote_id, party", [session],
                )
                speech_link_path = OUTPUT / f"sessions/{part}/decision-speech-links.json"
                write_json(speech_link_path, speech_link_rows, generated_at)
                add_file(manifest, speech_link_path, len(speech_link_rows),
                         f"Tematiska länkar mellan beslut och tidigare tal {session}")

        parties = [row[0] for row in db.execute(
            "select distinct party from gold_speakers order by party"
        ).fetchall()]
        for party in parties:
            part = safe_part(party)
            export_pair(
                db, manifest, f"parties/{part}/words",
                "select * from gold_party_words where party=? order by least(common_rank, distinctive_rank), word",
                generated_at, f"Vanliga och särskiljande ord för {party}", [party],
            )
            export_pair(
                db, manifest, f"parties/{part}/mentions",
                "select * from gold_mentions where speaker_party=? order by mentions desc",
                generated_at, f"Omnämnandekopplingar från {party}", [party],
            )
            export_pair(
                db, manifest, f"parties/{part}/topics",
                "select * from gold_topic_by_session_party where party=? order by session_year, words desc",
                generated_at, f"Ämnesutveckling för {party}", [party],
            )

    manifest_path = OUTPUT / "manifest.json"
    write_json(
        manifest_path,
        {
            "dataset": "partiledardebatter",
            "description": "Webboptimerat guldlager för portfolio",
            "files": manifest,
        },
        generated_at,
    )
    print(f"Skrev {len(manifest)} datafiler till {OUTPUT}")


if __name__ == "__main__":
    main()
