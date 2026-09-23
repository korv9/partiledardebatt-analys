"""Export the dbt gold layer as small, static files for a portfolio site."""
from __future__ import annotations

import csv
import json
import re
import shutil
import sqlite3
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

`decisions/`, `activities/` och `budgets/outturn-areas.json` innehåller nya spårbara lager. Öppna `sessions/<riksmöte>/decisions/index.json` först och ladda sedan filer per utskott. En `citation` är en uttrycklig dokument- eller numrerad yrkandehänvisning i utskottets förslag; en reservation är registrerad för en beslutspunkt. Inget av detta är en automatisk bedömning av ett partis stöd. Budgetutfall är verkliga utgifter, inte ett effektmått.

`laws/index.json` och `laws/<SFS-ID>/provisions.json` innehåller full bestämmelsetext från versionsmärkta SFS-snapshots som verifierats mot Allegorias källhashar. `laws/mentions.json` är enbart lexikala träffar på lagnamn i tal; ingen paragraf eller giltig lydelse vid taldatum har verifierats och inga direction-poäng beräknas.

`debates/index.json` listar de importerade protokollen. Varje posts `path` pekar på en liten JSON-fil med samtliga anföranden och repliker i källans ordning, inklusive fulltext, `speech_id`, parti, talare, `is_reply` och länk till Riksdagen. Läs indexet först och hämta bara det protokoll användaren öppnar. `is_reply` anger källans replikkod, inte vem repliken riktas till. Alla importerade tal finns med även om de är för korta för NLP-analysen. `data/speeches.csv` är motsvarande lokal CSV men ingår inte i den statiska webbexporten.

`issues/index.json` listar riksmöten med sakdebatter. Följ respektive `index_path` för att hitta en debattsektion och hämta sedan dess `path` (ett helt protokoll). Avgränsningen bygger på Riksdagens metadata för ärende-, särskilda, aktuella, budget- och utrikespolitiska debatter; frågestunder och interpellationer ingår inte. Fulltexten har inte körts genom partiledardebattens NLP-modell. Källa: Sveriges riksdag. Denna tjänst är fristående från Riksdagen.
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


def export_issue_debates(manifest: list[dict], generated_at: str) -> None:
    issue_database = ROOT / "data" / "issue_speeches.sqlite"
    with sqlite3.connect(issue_database) as db:
        db.row_factory = sqlite3.Row
        sessions = list(db.execute(
            "select dok_rm as session,count(*) as speech_count,"
            "count(distinct dok_id) as protocol_count,"
            "sum(case when replik='Y' then 1 else 0 end) as reply_count "
            "from issue_speeches group by dok_rm order by dok_rm"
        ))
        session_index = []
        for session_row in sessions:
            session = session_row["session"]
            session_part = safe_part(session)
            protocols = list(db.execute(
                "select dok_id as protocol_id,min(substr(dok_datum,1,10)) as debate_date,"
                "count(*) as speech_count from issue_speeches where dok_rm=? "
                "group by dok_id order by debate_date,dok_id", (session,)
            ))
            debate_index = []
            for protocol in protocols:
                protocol_id = protocol["protocol_id"]
                path = f"issues/{session_part}/{safe_part(protocol_id)}.json"
                source_rows = db.execute(
                    "select dok_id,dok_rm,dok_datum,avsnittsrubrik,kammaraktivitet,"
                    "anforande_nummer,talare,parti,anforandetext,intressent_id,replik,"
                    "debate_kind,source_url from issue_speeches where dok_id=? "
                    "order by cast(anforande_nummer as integer),anforande_nummer",
                    (protocol_id,),
                )
                speeches = []
                sections = []
                for source in source_rows:
                    row = {
                        "speech_id": f"{protocol_id}-{source['anforande_nummer']}",
                        "protocol_id": protocol_id,
                        "session": session,
                        "speech_date": source["dok_datum"][:10],
                        "speech_number": int(source["anforande_nummer"]),
                        "debate_title": source["avsnittsrubrik"],
                        "debate_kind": source["debate_kind"],
                        "speaker": source["talare"],
                        "party": source["parti"],
                        "person_id": source["intressent_id"],
                        "is_reply": source["replik"] == "Y",
                        "original_reply_code": source["replik"],
                        "speech_text": source["anforandetext"],
                        "source_url": source["source_url"],
                    }
                    speeches.append(row)
                    heading = (row["debate_title"], row["debate_kind"])
                    if not sections or heading != (sections[-1]["debate_title"], sections[-1]["debate_kind"]):
                        sections.append({
                            "section_id": row["speech_id"],
                            "debate_title": row["debate_title"],
                            "debate_kind": row["debate_kind"],
                            "first_speech_number": row["speech_number"],
                            "last_speech_number": row["speech_number"],
                            "speech_count": 0,
                            "reply_count": 0,
                            "path": path,
                        })
                    sections[-1]["last_speech_number"] = row["speech_number"]
                    sections[-1]["speech_count"] += 1
                    sections[-1]["reply_count"] += row["is_reply"]
                transcript_path = OUTPUT / path
                write_json(transcript_path, speeches, generated_at)
                add_file(manifest, transcript_path, len(speeches), f"Fulltext i sakdebattprotokoll {protocol_id}")
                debate_index.extend(sections)
            index_path = OUTPUT / f"issues/{session_part}/index.json"
            write_json(index_path, debate_index, generated_at)
            add_file(manifest, index_path, len(debate_index), f"Sakdebattsektioner {session}")
            session_index.append({
                "session": session,
                "speech_count": session_row["speech_count"],
                "reply_count": session_row["reply_count"],
                "protocol_count": session_row["protocol_count"],
                "section_count": len(debate_index),
                "index_path": index_path.relative_to(OUTPUT).as_posix(),
            })
        index_path = OUTPUT / "issues/index.json"
        write_json(index_path, session_index, generated_at)
        add_file(manifest, index_path, len(session_index), "Riksmöten med sakdebatter")


def main() -> None:
    if not DATABASE.exists():
        raise SystemExit("Kör först features.py och dbt build; analytics.duckdb saknas.")
    if not (ROOT / "data" / "issue_speeches.sqlite").exists():
        raise SystemExit("Kör först python issue_ingest.py; sakdebattdatabasen saknas.")
    if OUTPUT.exists():
        # The directory is generated in full; remove only this explicit project path.
        shutil.rmtree(OUTPUT)
    OUTPUT.mkdir()
    (OUTPUT / "README.md").write_text(README, encoding="utf-8")
    generated_at = datetime.now(timezone.utc).isoformat()
    cluster_metrics = json.loads((ROOT / "data" / "features" / "metrics.json").read_text(encoding="utf-8"))
    manifest: list[dict] = []
    with sqlite3.connect(ROOT / "data" / "issue_speeches.sqlite") as issue_db:
        issue_speeches, issue_protocols, issue_replies = issue_db.execute(
            "select count(*),count(distinct dok_id),"
            "sum(case when replik='Y' then 1 else 0 end) from issue_speeches"
        ).fetchone()

    with duckdb.connect(str(DATABASE), read_only=True) as db:
        overview = {
            "imported_speeches": db.execute("select count(*) from raw.speeches").fetchone()[0],
            "imported_replies": db.execute("select count(*) from gold_debate_speeches where is_reply").fetchone()[0],
            "debate_protocols": db.execute("select count(distinct protocol_id) from gold_debate_speeches").fetchone()[0],
            "issue_speeches": issue_speeches,
            "issue_protocols": issue_protocols,
            "issue_replies": issue_replies,
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
            "committee_points": db.execute("select count(*) from gold_decision_points").fetchone()[0],
            "policy_documents": db.execute("select count(*) from gold_policy_documents").fetchone()[0],
            "outturn_last_year": db.execute("select max(budget_year) from gold_budget_outturn_areas").fetchone()[0],
            "sfs_provisions": db.execute("select count(*) from gold_sfs_provisions").fetchone()[0],
        }
        overview_path = OUTPUT / "overview.json"
        write_json(overview_path, overview, generated_at)
        add_file(manifest, overview_path, 1, "Översikt och metodmetadata")

        debate_index = records(
            db,
            "select protocol_id, session, min(speech_date) as debate_date, "
            "min(debate_title) as debate_title, count(*) as speech_count, "
            "count(*) filter (where is_reply) as reply_count "
            "from gold_debate_speeches group by protocol_id,session "
            "order by debate_date,protocol_id",
        )
        for debate in debate_index:
            protocol_id = debate["protocol_id"]
            path = f"debates/{safe_part(debate['session'])}/{safe_part(protocol_id)}.json"
            debate["path"] = path
            speeches = records(
                db,
                "select * from gold_debate_speeches where protocol_id=? "
                "order by speech_number,speech_id",
                [protocol_id],
            )
            debate_path = OUTPUT / path
            write_json(debate_path, speeches, generated_at)
            add_file(manifest, debate_path, len(speeches), f"Fulltext och repliker i protokoll {protocol_id}")
        index_path = OUTPUT / "debates/index.json"
        write_json(index_path, debate_index, generated_at)
        add_file(manifest, index_path, len(debate_index), "Index över debattprotokoll och fulltextfiler")
        export_issue_debates(manifest, generated_at)

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
            db, manifest, "budgets/outturn-areas",
            "select * from gold_budget_outturn_areas order by budget_year, expenditure_area",
            generated_at, "Beslutad budget, ändringsbudget och faktiskt utfall per år och utgiftsområde",
        )
        export_pair(
            db, manifest, "budgets/execution",
            "select * from gold_budget_execution order by budget_year, actor, expenditure_area",
            generated_at, "Budgetförslag jämförda med beslutad budget och utfall",
        )
        export_pair(
            db, manifest, "activities/summary",
            "select * from gold_party_activity_summary order by session,party",
            generated_at, "Partiers debattal, skriftliga frågor och interpellationer",
        )
        law_index = records(
            db, "select sfs_document_id, max(document_title) as document_title, "
                "max(snapshot_version) as snapshot_version, count(*) as provisions, "
                "max(temporal_status) as temporal_status "
                "from gold_sfs_provisions group by sfs_document_id order by sfs_document_id",
        )
        law_index_path = OUTPUT / "laws/index.json"
        write_json(law_index_path, law_index, generated_at)
        add_file(manifest, law_index_path, len(law_index), "Versionsmärkta SFS-snapshots")
        for law in law_index:
            law_id = law["sfs_document_id"]
            provisions = records(
                db, "select * from gold_sfs_provisions where sfs_document_id=? order by provision_order",
                [law_id],
            )
            law_path = OUTPUT / f"laws/{law_id}/provisions.json"
            write_json(law_path, provisions, generated_at)
            add_file(manifest, law_path, len(provisions), f"Full bestämmelsetext och källhash: {law_id}")
        export_pair(
            db, manifest, "laws/mentions",
            "select * from gold_sfs_law_mentions order by speech_date,speech_id,sfs_document_id",
            generated_at, "Lexikala talträffar på lagnamn, utan paragraf- eller direction-slutsats",
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
            decision_rows = records(
                db, "select * from gold_decision_points where session=? "
                    "order by decision_date,designation,point", [session],
            )
            if decision_rows:
                committee_index = []
                committee_codes = sorted({re.match(r"[A-Za-z]+", row["designation"]).group()
                                          for row in decision_rows})
                for committee_code in committee_codes:
                    committee_part = safe_part(committee_code)
                    committee = {"committee": committee_code}
                    for name, query, description in (
                        ("points", "select * from gold_decision_points where session=? "
                         "and regexp_extract(designation, '^[A-Za-z]+')=? "
                         "order by decision_date,point", "Utskottspunkter"),
                        ("citations", "select * from gold_decision_citations where session=? "
                         "and regexp_extract(designation, '^[A-Za-z]+')=? "
                         "order by point_id,document_id,claim_number", "Dokument- och yrkandehänvisningar"),
                        ("reservations", "select * from gold_decision_reservations where session=? "
                         "and regexp_extract(designation, '^[A-Za-z]+')=? "
                         "order by point_id,reservation_number,party", "Reservationer"),
                    ):
                        path = OUTPUT / f"sessions/{part}/decisions/{committee_part}/{name}.json"
                        rows = records(db, query, [session, committee_code])
                        write_json(path, rows, generated_at)
                        add_file(manifest, path, len(rows), f"{description} {committee_code} {session}")
                        committee[name] = {"path": path.relative_to(OUTPUT).as_posix(), "rows": len(rows)}
                    committee_index.append(committee)
                index_path = OUTPUT / f"sessions/{part}/decisions/index.json"
                write_json(index_path, committee_index, generated_at)
                add_file(manifest, index_path, len(committee_index), f"Utskottens små beslutsfiler {session}")
                trace_rows = records(db, "select * from gold_debate_decision_traces where session=? "
                                        "order by decision_date,point_id,party", [session])
                trace_path = OUTPUT / f"sessions/{part}/decisions/debate-traces.json"
                write_json(trace_path, trace_rows, generated_at)
                add_file(manifest, trace_path, len(trace_rows),
                         f"Tal → beslut med tematiskt länkbevis {session}")
                for doc_type, name in (("fr", "questions"), ("ip", "interpellations"),
                                       ("prop", "propositions")):
                    rows = records(db, "select * from gold_policy_documents where session=? "
                                        "and document_type=? order by document_date,document_id",
                                   [session, doc_type])
                    path = OUTPUT / f"sessions/{part}/activities/{name}.json"
                    write_json(path, rows, generated_at)
                    add_file(manifest, path, len(rows), f"{name} för riksmöte {session}")

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
