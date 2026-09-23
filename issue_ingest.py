"""Importera Riksdagens ärende- och särskilda sakdebatter från JSON-arkiven.

Källurvalet hålls separat från partiledardebattens analyskorpus.
Utan --refresh återanvänds den lokala källkatalogen och nedladdade arkiv.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from ingest import CATALOG, FIELDS, PlainText, discover, download

KINDS = {
    'ärendedebatt',
    'föredragning av utskottsärende med eventuell debatt',
    'särskild debatt',
    'aktuell debatt',
    'budgetdebatt',
    'utrikespolitisk debatt',
}


def issue_kind(row: dict) -> str | None:
    activity = (row.get('kammaraktivitet') or '').strip().casefold()
    heading = (row.get('avsnittsrubrik') or '').strip().casefold()
    if 'partiledardebatt' in activity or 'partiledardebatt' in heading:
        return None
    if heading.startswith('meddelande'):
        return None
    if activity in KINDS:
        return activity
    if heading.startswith('särskild debatt'):
        return 'särskild debatt'
    if heading.startswith('aktuell debatt'):
        return 'aktuell debatt'
    return None


def read_issue_rows(path: Path):
    with zipfile.ZipFile(path) as archive:
        members = [name for name in archive.namelist() if name.endswith('.json')]
        if not members:
            raise ValueError('Arkivet saknar JSON-filer')
        for member in members:
            source = json.loads(archive.read(member).decode('utf-8-sig'))['anforande']
            if not set(FIELDS).issubset(source):
                raise ValueError(f'Saknade fält i {member}')
            row = {key: str(source[key]) if source[key] is not None else '' for key in FIELDS}
            kind = issue_kind(row)
            if kind is None:
                continue
            if not row['dok_id'] or not row['anforande_nummer'].isdigit():
                raise ValueError(f'Anförandet saknar giltigt ID: {member}')
            parsed = PlainText()
            parsed.feed(row['anforandetext'])
            row['anforandetext'] = ''.join(parsed.parts).strip()
            row['debate_kind'] = kind
            yield row


def import_file(db: sqlite3.Connection, path: Path, url: str) -> dict:
    count = empty = 0
    with db:
        db.execute('DELETE FROM issue_speeches WHERE dataset_url=?', (url,))
        batch = []
        for row in read_issue_rows(path):
            count += 1
            empty += not bool(row['anforandetext'])
            source_url = f"https://data.riksdagen.se/anforande/{row['dok_id']}-{row['anforande_nummer']}/html"
            batch.append([row[key] for key in FIELDS] + [row['debate_kind'], source_url, url])
            if len(batch) >= 1000:
                db.executemany('INSERT OR REPLACE INTO issue_speeches VALUES (' + ','.join('?' for _ in range(16)) + ')', batch)
                batch.clear()
        if batch:
            db.executemany('INSERT OR REPLACE INTO issue_speeches VALUES (' + ','.join('?' for _ in range(16)) + ')', batch)
    return {'speeches': count, 'empty_texts': empty}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--session', help='Begränsa till exempelvis 2025/26')
    parser.add_argument('--refresh', action='store_true', help='Hämta aktuell källkatalog och arkiv')
    parser.add_argument('--data-dir', default='data')
    args = parser.parse_args()
    root = Path(args.data_dir)
    raw = root / 'raw'
    raw.mkdir(parents=True, exist_ok=True)
    catalog_path = raw / 'catalog.html'
    if args.refresh or not catalog_path.exists():
        catalog = download(CATALOG).decode('utf-8')
        catalog_path.write_text(catalog, encoding='utf-8')
    else:
        catalog = catalog_path.read_text(encoding='utf-8')
    urls = discover(catalog)
    if args.session:
        urls = [url for url in urls if url.endswith(f"anforande-{args.session.replace('/', '')}.json.zip")]
    if not urls:
        raise RuntimeError('Inga dataset hittades för valt riksmöte')
    db = sqlite3.connect(root / 'issue_speeches.sqlite')
    db.execute('CREATE TABLE IF NOT EXISTS issue_speeches (' +
               ','.join(key + ' TEXT NOT NULL' for key in FIELDS) +
               ', debate_kind TEXT NOT NULL, source_url TEXT NOT NULL, dataset_url TEXT NOT NULL, '
               'PRIMARY KEY(dok_id, anforande_nummer))')
    db.execute('CREATE INDEX IF NOT EXISTS issue_session ON issue_speeches(dok_rm,dok_id)')
    report = {'started_at': datetime.now(timezone.utc).isoformat(),
              'scope': 'Ärende-, särskilda, aktuella, budget- och utrikespolitiska debatter enligt källmetadata',
              'session_filter': args.session, 'datasets': [], 'errors': []}
    for url in urls:
        path = raw / url.rsplit('/', 1)[1]
        try:
            if args.refresh or not path.exists():
                content = download(url)
                temporary = path.with_suffix('.tmp')
                temporary.write_bytes(content)
                with zipfile.ZipFile(temporary) as archive:
                    if archive.testzip() is not None:
                        raise ValueError('Skadat ZIP-arkiv')
                temporary.replace(path)
            stats = import_file(db, path, url)
            report['datasets'].append({'url': url, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(), **stats})
            print(f"{path.name}: {stats['speeches']} sakdebattanföranden", flush=True)
        except Exception as exc:
            report['errors'].append({'url': url, 'error': str(exc)})
            print(f'FEL {url}: {exc}', flush=True)
    report['database_totals'] = dict(zip(['speeches', 'protocols', 'first_date', 'last_date'], db.execute(
        'SELECT COUNT(*),COUNT(DISTINCT dok_id),MIN(dok_datum),MAX(dok_datum) FROM issue_speeches').fetchone()))
    report['finished_at'] = datetime.now(timezone.utc).isoformat()
    (root / 'issue_coverage.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    db.close()
    if report['errors']:
        raise SystemExit('Importen är ofullständig. Se data/issue_coverage.json')


if __name__ == '__main__':
    main()
