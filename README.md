# Partiledardebatt – analysunderlag

Import av Riksdagens publicerade partiledardebatter till SQLite och CSV. Grundimporten kräver Python 3.10+ utan API-nyckel. Budget-, voterings- och analysstegen använder paketen i `requirements-analysis.txt`.

För ämnesmodell, UMAP-karta, ordstatistik, omnämnanden och liknande tal finns nu ett separat **dbt + DuckDB-projekt**. Se [ANALYSIS.md](ANALYSIS.md) för installation, modeller och körning. Den genererade interaktiva rapporten ligger i `reports/analys.html`.

Webboptimerade filer för en portfolio genereras till `portfolio-data/`. Börja med `portfolio-data/manifest.json`.

För en klickbar debattvy: läs `portfolio-data/debates/index.json` och hämta sedan filen i postens `path`, till exempel `debates/2025-26/hd09136.json`. Den innehåller **alla** importerade anföranden och repliker i protokollordning med hela taltexten, talare, parti och källänk. `is_reply` är Riksdagens replikkod; den anger inte säkert vilken tidigare talare som besvaras. Webbexporten omfattar även korta tal som inte ingick i ämnesanalysen.

Sakdebatter importeras separat med `python issue_ingest.py` från samma lokala Riksdagsarkiv. `portfolio-data/issues/index.json` listar riksmöten; varje `index_path` listar ämnessektioner och ett `path` till hela protokollets tal och repliker. Urvalet omfattar källans kategorier *ärendedebatt*, *föredragning av utskottsärende med eventuell debatt*, *särskild debatt*, *aktuell debatt*, *budgetdebatt* och *utrikespolitisk debatt*, plus rubriker som börjar med *Särskild debatt* eller *Aktuell debatt*. Frågestunder och interpellationsdebatter ingår inte. Äldre riksmöten saknar ofta enhetlig kategorisering, så detta är inte ett fullständigt register över alla tänkbara sakdebatter. Sakdebatterna ingår inte i partiledardebattens ämnesmodell eller UMAP.

För ett annat repo kan du läsa `portfolio-data/issues/index.json` eller `portfolio-data/debates/index.json` från de publicerade GitHub-filerna. Ladda bara den valda protokollfilen när användaren klickar. Källa: Sveriges riksdag. Portfoliosidan bör tydligt ange att tjänsten är fristående från Riksdagen och återge källänkarna på varje tal.

```powershell
python ingest.py
python issue_ingest.py
python budget_ingest.py --from-session 2014/15 --to-session 2025/26
python vote_ingest.py --session 2024/25 --session 2025/26
python policy_ingest.py --session 2024/25 --session 2025/26
python outturn_ingest.py
python sfs_bridge.py --allegoria-root ..\allegoria --document-id sfs-1982-80
python run_analysis.py
python analyze.py
python analyze.py --search klimat
python -m unittest -v
```

`python ingest.py --session 2025/26` begränsar importen. `--refresh` hämtar nya versioner av originalfilerna. Utan flaggan återanvänds nedladdade filer. Kör med `--refresh` för att få uppdateringar av redan hämtade riksmöten. Återkörning ger inga dubbletter.

## Resultat

- `data/debates.sqlite`: tabellen `speeches`, en rad per anförande/replik.
- `data/speeches.csv`: samma data i UTF-8 med BOM, lämplig för analysverktyg.
- `data/issue_speeches.sqlite` och `data/issue_coverage.json`: separat lokal sakdebattimport, vars fulltext exporteras som uppdelad JSON under `portfolio-data/issues/`.
- `data/coverage.json`: körningens källor, kontrollsummor, radantal, tomma texter och fel.
- `data/budgets.sqlite` och `data/budget_frames.csv`: regeringens och partiernas utgiftsramar.
- `data/budget_coverage.json`: vilka FiU1-betänkanden som kunde läsas maskinellt.
- `data/votes.sqlite`: ledamotsröster, voterade beslutspunkter och uttryckligen citerade motioner.
- `data/vote_coverage.json`: importerade riksmöten, antal matchade beslut och luckor.
- `data/policy.sqlite` och `data/policy_coverage.json`: beslutspunkter, uttryckliga dokument-/yrkandehänvisningar, reservationer och parlamentarisk aktivitet.
- `data/outturn.sqlite` och `data/outturn_coverage.json`: Statskontorets årsutfall per anslag, 1997–2025.
- `data/sfs.sqlite` och `data/sfs_coverage.json`: utvalda SFS-paragrafer via Allegorias verifierade källsnapshot.
- `data/raw/`: Riksdagens originalarkiv samt hämtad katalog.

Data är lokala och ignoreras av Git. Databasen kan innehålla tidigare importerade riksmöten; rapportens `datasets` gäller endast aktuell körning och `database_totals` hela databasen. Vid fel avslutas programmet med felkod och behåller tidigare data för den berörda källan. Övriga källor importeras färdigt.

## Datakällor och avgränsning

Primär källa: [Riksdagens anföranden och nedladdningsbara dataset](https://www.riksdagen.se/sv/dokument-och-lagar/riksdagens-oppna-data/anforanden/). Officiell täckning börjar 1993/94. Importen upptäcker alla publicerade JSON-arkiv i katalogen, inklusive den avvikande beteckningen 1999/2000. Dessa innehåller fulltext. List-API:et ger metadata och kan lämna textfältet tomt.

Budgetimporten använder finansutskottets årliga FiU1-betänkande via Riksdagens dokument-API. Den läser jämförelsetabellen med regeringens ram och partiernas avvikelse för vart och ett av de 27 utgiftsområdena. `amount_msek` är regeringens belopp plus partiets redovisade avvikelse och anges i miljoner kronor. `GOV` betyder regeringens samlade budgetförslag, inte ett enskilt regeringsparti. Vissa år finns betänkandet endast som PDF eller utan en maskinläsbar jämförelsetabell; de redovisas som luckor i `budget_coverage.json` och fylls inte med uppskattningar.

Voteringsimporten använder [Riksdagens dataset per ledamotsröst](https://data.riksdagen.se/dataset/katalog/dataset-votering.html), [dokument-API:et](https://www.riksdagen.se/sv/dokument-och-lagar/riksdagens-oppna-data/dokument/) och betänkandets dokumentstatus. Den sparar även `Ja`, `Nej`, `Avstår` och `Frånvarande`; partiets position i guldlagret är den vanligaste avgivna rösten bland dess ledamöter för en beslutspunkt. Ja och nej avser utskottets förslag i punkten och kan därför exempelvis betyda ja till avslag på en proposition. En röst gäller betänkandets punkt, inte varje motion som behandlas där. Endast motioner som uttryckligen nämns i punktens förslag får en direkt motionslänk. `vote_ingest.py` tar valfria `--session` och ersätter vid varje körning voteringslagret med de angivna riksmötena. I nuläget är 2024/25 och 2025/26 importerade; äldre riksmöten är inte ännu med i resultatet.

`run_analysis.py` kopplar beslutspunkter till tidigare debattal från samma parti med semantisk textlikhet (minst 0,60 i cosinuslikhet). Om talarens person-ID också finns bland rösterna visas talarens egen registrerade röst; annars visas bara partiets röstfördelning. Detta är en sökhjälp, inte en automatisk bedömning av om ord och handling stämmer överens. Titta på talet, den exakta beslutspunkten, eventuella reservationer och varje ledamots röst innan du drar en sådan slutsats. Partiledaren kan sakna egen registrerad röst, och vissa beslut fattas utan namnupprop.

`policy_ingest.py` läser de betänkanden som `vote_ingest.py` har cachelagrat och kompletterar med Riksdagens öppna dokumentlistor för skriftliga frågor (`fr`), interpellationer (`ip`) och propositioner (`prop`). Beslutspunkter utan namnupprop tas med **inom dessa betänkanden**; detta är ännu inte alla riksdagsbeslut. En `point_id` är betänkandets dokument-ID plus punktnummer. `decision_citations` innehåller bara motioner och propositioner som uttryckligen står i punktens förslag, med numrerat yrkande när numret framgår. Själva yrkandetexten är inte importerad; originaldokumentet länkas. Reservationerna har partier och nummer från dokumentstatus, men inte full reservationstext. En uttrycklig hänvisning betyder att förslaget behandlas, inte att utskottet eller ett visst parti stöder det.

`outturn_ingest.py` läser [Statskontorets definitiva årsutfall för utgifter](https://www.statskontoret.se/analys-och-statistik/oppna-data/arsutfall/) från det officiella CSV-arkivet. Snapshoten innehåller 1997–2025 och beloppen är miljoner kronor. `gold_budget_execution` jämför FiU1-förslag med beslutad budget, ändringsbudgetar och faktiskt utfall per utgiftsområde. Skillnaden är deskriptiv; den mäter inte effekten av en åtgärd eller ansvaret för en enskild politiker. Använd `--archive` för en lokalt nedladdad ZIP eller `--refresh` när den angivna officiella arkivversionen uppdateras.

`sfs_bridge.py` använder [Allegorias SFS-parser](https://github.com/korv9/allegoria) och kontrollerar varje bestämmelse mot ursprunglig XML och bronzesnapshot innan texten importeras. Det första exemplet är lagen (1982:80) om anställningsskydd: 70 paragrafer och 22 övergångsbestämmelser i snapshoten `t.o.m. SFS 2022:836`. `gold_sfs_law_mentions` hittar uttryckliga lagnamn i tal, men identifierar **inte** en viss paragraf eller ett rättsligt påstående. Denna snapshot får inte användas som 2020 års laglydelse utan separat versionskontroll. Ingen `direction`-poäng beräknas. Se [LAW_LINKING.md](LAW_LINKING.md) för det saknade granskningssteget.

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
