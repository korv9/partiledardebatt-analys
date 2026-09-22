"""Importera Riksdagens publicerade partiledardebatter, utan externa paket."""
import argparse
import csv
import hashlib
import json
import re
import sqlite3
import time
import urllib.request
import zipfile
from html.parser import HTMLParser
from datetime import datetime, timezone
from pathlib import Path

CATALOG = 'https://www.riksdagen.se/sv/dokument-och-lagar/riksdagens-oppna-data/anforanden/'
FIELDS = ['dok_id', 'dok_rm', 'dok_nummer', 'dok_datum', 'avsnittsrubrik',
          'kammaraktivitet', 'anforande_nummer', 'talare', 'parti',
          'anforandetext', 'intressent_id', 'rel_dok_id', 'replik']


class PlainText(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []

    def handle_data(self, data):
        self.parts.append(data)

    def handle_endtag(self, tag):
        if tag in ('p', 'div'):
            self.parts.append('\n')

    def handle_starttag(self, tag, attrs):
        if tag == 'br':
            self.parts.append('\n')


def download(url):
    for attempt in range(4):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'partiledardebatt-analys/1.0'})
            with urllib.request.urlopen(req, timeout=120) as response:
                return response.read()
        except (OSError, TimeoutError):
            if attempt == 3:
                raise
            time.sleep(2 ** attempt)


def discover(html):
    return sorted(set(re.findall(
        r'https://data\.riksdagen\.se/dataset/anforande/anforande-\d+\.json\.zip', html)))


def is_debate(row):
    # Matcha metadata, aldrig omnämnanden i själva talet.
    return any('partiledardebatt' in (row.get(k) or '').casefold()
               and not (row.get(k) or '').strip().casefold().startswith('meddelande')
               for k in ('avsnittsrubrik', 'kammaraktivitet'))


def read_rows(path):
    with zipfile.ZipFile(path) as archive:
        members = [n for n in archive.namelist() if n.endswith('.json')]
        if not members:
            raise ValueError('Arkivet saknar JSON-filer')
        for member in members:
            source = json.loads(archive.read(member).decode('utf-8-sig'))['anforande']
            if not set(FIELDS).issubset(source):
                raise ValueError(f'Saknade fält i {member}')
            row = {key: str(source[key]) if source[key] is not None else '' for key in FIELDS}
            if is_debate(row):
                parsed = PlainText()
                parsed.feed(row['anforandetext'])
                row['anforandetext'] = ''.join(parsed.parts).strip()
            yield row

def import_file(db, path, url):
    total = matched = missing = 0
    with db:
        # Ersätt bara denna källas poster, atomärt efter lyckad parsning.
        db.execute('DELETE FROM speeches WHERE dataset_url=?', (url,))
        for row in read_rows(path):
            total += 1
            if not is_debate(row):
                continue
            if not row['dok_id'] or not row['anforande_nummer'].isdigit():
                raise ValueError('Anförandet saknar giltigt ID')
            matched += 1
            missing += not bool(row['anforandetext'].strip())
            source = f"https://data.riksdagen.se/anforande/{row['dok_id']}-{row['anforande_nummer']}/html"
            db.execute('INSERT OR REPLACE INTO speeches VALUES (' + ','.join('?' for _ in range(15)) + ')',
                       [row[k] for k in FIELDS] + [source, url])
    return {'rows_scanned': total, 'speeches': matched, 'empty_texts': missing}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--session', help='Begränsa till exempelvis 2025/26')
    parser.add_argument('--refresh', action='store_true', help='Hämta originalfiler på nytt')
    parser.add_argument('--data-dir', default='data')
    args = parser.parse_args()
    root = Path(args.data_dir)
    raw = root / 'raw'
    raw.mkdir(parents=True, exist_ok=True)
    catalog = download(CATALOG).decode('utf-8')
    (raw / 'catalog.html').write_text(catalog, encoding='utf-8')
    urls = discover(catalog)
    if args.session:
        urls = [u for u in urls if u.endswith(f"anforande-{args.session.replace('/', '')}.json.zip")]
    if not urls:
        raise RuntimeError('Inga dataset hittades; kontrollera katalogen/riksmötet')
    db = sqlite3.connect(root / 'debates.sqlite')
    db.execute('CREATE TABLE IF NOT EXISTS speeches (' +
               ','.join(k + ' TEXT NOT NULL' for k in FIELDS) +
               ', source_url TEXT NOT NULL, dataset_url TEXT NOT NULL, PRIMARY KEY(dok_id, anforande_nummer))')
    db.execute('CREATE INDEX IF NOT EXISTS party_date ON speeches(parti, dok_datum)')
    report = {'started_at': datetime.now(timezone.utc).isoformat(),
              'scope': 'Riksdagens publicerade JSON-dataset; metadata innehåller partiledardebatt',
              'session_filter': args.session, 'datasets': [], 'errors': []}
    for url in urls:
        path = raw / url.rsplit('/', 1)[1]
        try:
            if args.refresh or not path.exists():
                content = download(url)
                temp = path.with_suffix('.tmp')
                temp.write_bytes(content)
                with zipfile.ZipFile(temp) as archive:
                    if archive.testzip() is not None:
                        raise ValueError('Skadat ZIP-arkiv')
                temp.replace(path)
            stats = import_file(db, path, url)
            report['datasets'].append(dict(url=url, sha256=hashlib.sha256(path.read_bytes()).hexdigest(), **stats))
            print(f"{path.name}: {stats['speeches']} anföranden ({stats['rows_scanned']} granskade)", flush=True)
        except Exception as exc:
            report['errors'].append({'url': url, 'error': str(exc)})
            print(f'FEL {url}: {exc}', flush=True)
    cursor = db.execute('SELECT * FROM speeches ORDER BY dok_datum, dok_id, CAST(anforande_nummer AS INTEGER)')
    with (root / 'speeches.csv').open('w', encoding='utf-8-sig', newline='') as file:
        writer = csv.writer(file)
        writer.writerow([d[0] for d in cursor.description])
        writer.writerows(cursor)
    report['database_totals'] = dict(zip(['speeches', 'protocols', 'first_date', 'last_date'], db.execute(
        'SELECT COUNT(*),COUNT(DISTINCT dok_id),MIN(dok_datum),MAX(dok_datum) FROM speeches').fetchone()))
    report['finished_at'] = datetime.now(timezone.utc).isoformat()
    (root / 'coverage.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    db.close()
    print(json.dumps(report['database_totals'], ensure_ascii=False))
    if report['errors']:
        raise SystemExit('Importen är ofullständig. Se data/coverage.json och kör igen.')


if __name__ == '__main__':
    main()
