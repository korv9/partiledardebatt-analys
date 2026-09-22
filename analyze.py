"""Snabb översikt över importerade anföranden."""
import argparse
import sqlite3

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--db', default='data/debates.sqlite')
parser.add_argument('--search', help='Sök ett ord eller en fras i anförandena')
args = parser.parse_args()
db = sqlite3.connect(f'file:{args.db}?mode=ro', uri=True)
if args.search:
    rows = db.execute('SELECT dok_datum,talare,avsnittsrubrik,source_url FROM speeches '
                      'WHERE instr(lower(anforandetext),lower(?))>0 ORDER BY dok_datum DESC', (args.search,))
else:
    rows = db.execute('SELECT dok_rm,upper(parti),count(*),sum(length(anforandetext)) FROM speeches '
                      'GROUP BY dok_rm,upper(parti) ORDER BY dok_rm DESC,count(*) DESC')
for row in rows:
    print(' | '.join(str(x) for x in row))
db.close()
