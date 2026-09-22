# Partiledardebatt – analysunderlag

Import av Riksdagens publicerade partiledardebatter till SQLite och CSV. Python 3.10+ räcker; inga API-nycklar eller externa paket behövs.

För ämnesmodell, UMAP-karta, ordstatistik, omnämnanden och liknande tal finns nu ett separat **dbt + DuckDB-projekt**. Se [ANALYSIS.md](ANALYSIS.md) för installation, modeller och körning. Den genererade interaktiva rapporten ligger i `reports/analys.html`.

```powershell
python ingest.py
python analyze.py
python analyze.py --search klimat
python -m unittest -v
```

`python ingest.py --session 2025/26` begränsar importen. `--refresh` hämtar nya versioner av originalfilerna. Utan flaggan återanvänds nedladdade filer. Kör med `--refresh` för att få uppdateringar av redan hämtade riksmöten. Återkörning ger inga dubbletter.

## Resultat

- `data/debates.sqlite`: tabellen `speeches`, en rad per anförande/replik.
- `data/speeches.csv`: samma data i UTF-8 med BOM, lämplig för analysverktyg.
- `data/coverage.json`: körningens källor, kontrollsummor, radantal, tomma texter och fel.
- `data/raw/`: Riksdagens originalarkiv samt hämtad katalog.

Data är lokala och ignoreras av Git. Databasen kan innehålla tidigare importerade riksmöten; rapportens `datasets` gäller endast aktuell körning och `database_totals` hela databasen. Vid fel avslutas programmet med felkod och behåller tidigare data för den berörda källan. Övriga källor importeras färdigt.

## Datakällor och avgränsning

Primär källa: [Riksdagens anföranden och nedladdningsbara dataset](https://www.riksdagen.se/sv/dokument-och-lagar/riksdagens-oppna-data/anforanden/). Officiell täckning börjar 1993/94. Importen upptäcker alla publicerade JSON-arkiv i katalogen, inklusive den avvikande beteckningen 1999/2000. Dessa innehåller fulltext. List-API:et ger metadata och kan lämna textfältet tomt.

Verifierade adresser:

- Metadata: `https://data.riksdagen.se/anforandelista/?utformat=json&sz=100&rm=2025%2F26`
- Detalj/fulltext: `https://data.riksdagen.se/anforande/HD09136-109.json`
- Historik med text: `https://data.riksdagen.se/dataset/anforande/anforande-202526.json.zip`

Urvalet görs på att `avsnittsrubrik` eller `kammaraktivitet` innehåller **partiledardebatt**, oberoende av stora/små bokstäver. Det omfattar även exempelvis EU-politiska partiledardebatter. Ett omnämnande i själva taltexten räcker inte. Administrativa rubriker som börjar med Meddelande utesluts. Alla talare och repliker i matchande avsnitt behålls; det betyder att materialet inte enbart innehåller partiledare. JSON används eftersom äldre CSVT-exporter har felaktigt escapade citattecken. HTML-markering tas bort från texten; originalet finns kvar i ZIP-arkivet.

Fullständighet gäller detta metadataurval i publicerade dataset, inte samtliga svenska partiledardebatter. Saknade eller felklassificerade källposter kan inte upptäckas automatiskt. Originalens datum, stavning och partibeteckningar bevaras; äldre källdatum kan vara felaktiga. Använd `dok_rm` för jämförelser mellan riksmöten och granska källprotokoll vid historiska datumavvikelser. Riksdagens text är ett protokoll, inte ordagrann ljudtranskription med tidskoder. `protocols` räknar unika protokoll, inte verifierat antal separata debatter.

## TV och radio – kartlagda, inte importerade

| Källa | Tillgång | Begränsning |
| --- | --- | --- |
| [SVT Tablåtjänsten](https://api.svt.se/tablatjansten/docs) | Dokumenterat API för tablå och aktiva SVT Play-program | Inte ett komplett historiskt API för debattutskrifter |
| [Sveriges Radio API v2](https://www.sverigesradio.se/artikel/dokumentation-for-api-version-2) | Program- och avsnittsdata | Ingen verifierad komplett samling debattutskrifter; [villkoren](https://www.sverigesradio.se/artikel/this-is-swedish-radios-open-api) begränsar lagring av material |
| TV4, Expressen/DI | Separata publiceringar | Inget fullständigt öppet transkript-API har verifierats i denna undersökning |

För dessa källor behövs en separat insamling av tillgängliga, tillåtna transkript eller undertexter och eventuellt transkribering av ljud.

## Exempel på SQL

```sql
SELECT dok_rm, upper(parti) AS parti, count(*) AS anforanden,
       sum(length(anforandetext)) AS tecken
FROM speeches
GROUP BY dok_rm, upper(parti)
ORDER BY dok_rm, parti;

SELECT dok_datum, talare, replik, anforandetext, source_url
FROM speeches
WHERE avsnittsrubrik LIKE '%Partiledardebatt%'
ORDER BY dok_datum, dok_id, CAST(anforande_nummer AS INTEGER);
```

Antal tecken är textmängd, inte talartid. `replik` bevarar källans kod (vanligen Y/N). `intressent_id` är text så att inledande nollor bevaras. Unik nyckel är `dok_id` + `anforande_nummer`. Källänkar finns på varje rad. Visa text som text, inte körbar HTML, i eventuella framtida gränssnitt.
